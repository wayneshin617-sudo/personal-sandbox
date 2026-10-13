"""공개 목록 페이지만 2초마다 확인하고, 새 글 제목만 쌓는다."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass

import httpx

from .db import Store, to_public, utc_now
from .parsers import parse_blind, parse_dc

log = logging.getLogger("solo.crawl")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

DC_URL = "https://gall.dcinside.com/board/lists/?id=iamsolo"
BLIND_URL = "https://www.teamblind.com/kr/topics/Im%EC%86%94%EB%A1%9C"

SOURCES = {
    "dc": {
        "url": DC_URL,
        "headers": {"Referer": "https://gall.dcinside.com/"},
        "parse": parse_dc,
    },
    "blind": {
        "url": BLIND_URL,
        "headers": {"Referer": "https://www.teamblind.com/"},
        "parse": parse_blind,
    },
}


class Hub:
    def __init__(self) -> None:
        self.queues: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=400)
        self.queues.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self.queues.discard(queue)

    def publish(self, event: str, data: dict) -> None:
        stale: list[asyncio.Queue] = []
        for queue in self.queues:
            try:
                queue.put_nowait((event, data))
            except asyncio.QueueFull:
                stale.append(queue)
        for queue in stale:
            self.queues.discard(queue)


@dataclass
class SourceState:
    ok: bool = False
    last_ok_at: str | None = None
    message: str = ""
    last_new: int = 0
    failures: int = 0
    backoff_until: float = 0.0

    def retry_in(self) -> int:
        remain = self.backoff_until - time.monotonic()
        return max(0, int(remain + 0.999))


def clean_title(value: str) -> str:
    return " ".join(value.replace("\n", " ").split())


def friendly_error(exc: Exception) -> str:
    text = str(exc)
    if "글을 찾지 못했습니다" in text:
        return "목록에서 글을 읽지 못했습니다. 잠시 후 다시 확인합니다."
    if any(code in text for code in ("403", "429", "503")):
        return "게시판이 요청을 잠시 막았습니다. 간격을 두고 다시 시도합니다."
    if "timeout" in text.lower() or "timed out" in text.lower():
        return "응답이 지연되고 있습니다."
    return "목록을 가져오지 못했습니다."


class Crawler:
    def __init__(self, store: Store, hub: Hub):
        self.store = store
        self.hub = hub
        self.interval = max(2.0, float(os.environ.get("POLL_INTERVAL", "2")))
        self.states = {name: SourceState() for name in SOURCES}

    def snapshot(self) -> dict:
        since = utc_now_minus(60)
        return {
            "total": self.store.count(),
            "bySource": {
                "dc": self.store.count(source="dc"),
                "blind": self.store.count(source="blind"),
            },
            "lastMinute": self.store.count(since=since, live_only=True),
            "startedAt": self.store.get_meta("started_at"),
            "intervalSec": self.interval,
            "sources": {
                name: {
                    "ok": state.ok,
                    "lastOkAt": state.last_ok_at,
                    "message": state.message,
                    "lastNew": state.last_new,
                    "retryInSec": state.retry_in(),
                }
                for name, state in self.states.items()
            },
        }

    async def run(self) -> None:
        if os.environ.get("CRAWL_ENABLED", "1") == "0":
            return
        self.store.set_meta_once("started_at", utc_now())
        timeout = httpx.Timeout(8.0, connect=5.0)
        headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
        }
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout, headers=headers) as client:
            while True:
                started = time.monotonic()
                try:
                    await asyncio.gather(*(self._tick(client, name) for name in SOURCES))
                    self.hub.publish("status", self.snapshot())
                except asyncio.CancelledError:
                    raise
                except Exception:
                    log.exception("수집 루프 오류")
                delay = self.interval - (time.monotonic() - started)
                if delay > 0:
                    await asyncio.sleep(delay)

    async def _tick(self, client: httpx.AsyncClient, name: str) -> None:
        state = self.states[name]
        if time.monotonic() < state.backoff_until:
            return
        spec = SOURCES[name]
        try:
            response = await client.get(spec["url"], headers=spec["headers"])
            response.raise_for_status()
            html = response.content.decode("utf-8", errors="replace")
            posts = spec["parse"](html)
            if not posts:
                title = ""
                start = html.find("<title>")
                if start >= 0:
                    title = clean_title(html[start:start + 120])
                raise RuntimeError(
                    f"목록에서 글을 찾지 못했습니다 ({response.status_code}, {len(html)} bytes, {title})"
                )
            posts.reverse()
            is_seed = self.store.count(source=name) == 0
            inserted = self.store.insert_new(posts, is_seed=is_seed)
            state.ok = True
            state.message = ""
            state.failures = 0
            state.backoff_until = 0.0
            state.last_ok_at = utc_now()
            state.last_new = 0 if is_seed else len(inserted)
            if inserted:
                log.info("%s 새 글 %s건", name, len(inserted))
            for row in inserted:
                self.hub.publish("post", to_public(row))
        except Exception as exc:
            state.ok = False
            state.failures += 1
            state.message = friendly_error(exc)
            delay = min(60.0, float(2 ** min(state.failures, 6)))
            state.backoff_until = time.monotonic() + delay
            log.warning("%s 수집 실패: %s (%.0f초 후 재시도)", name, exc, delay)


def utc_now_minus(seconds: int) -> str:
    from datetime import timedelta

    moment = datetime_now() - timedelta(seconds=seconds)
    return moment.replace(microsecond=0).isoformat()


def datetime_now():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)

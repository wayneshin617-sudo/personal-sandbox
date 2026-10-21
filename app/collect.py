"""게시판 목록을 읽어 docs/data/posts.json 에 쌓는다.

모으기 시작 시각은 2026-10-07 22:30 KST 다.
이미 그 시각까지 들어가 있으면 첫 페이지만 보고, 없으면 그 시각까지 페이지를 넘긴다.
"""

from __future__ import annotations

import json
import re
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from .filters import drop_reason, should_keep, skip_youtube_video

from .parsers import (
    jina_markdown,
    load_youtube_data,
    parse_blind,
    parse_blind_comments,
    parse_dc,
    parse_dc_comments,
    parse_social_replies,
    parse_social_search,
    parse_theqoo,
    parse_theqoo_comments,
    parse_youtube_comments,
    parse_youtube_search,
    parse_youtube_watch_meta,
    youtube_newest_token,
)

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "docs" / "data" / "posts.json"
META_PATH = ROOT / "docs" / "data" / "meta.json"
YT_PATH = ROOT / "docs" / "data" / "youtube.json"

KST = timezone(timedelta(hours=9))
CUTOFF = datetime(2026, 10, 7, 22, 30, tzinfo=KST)
MAX_DC_PAGES = 400
MAX_DC_REPLY_THREADS = 24
MAX_QOO_REPLY_THREADS = 16
MAX_BLIND_REPLY_THREADS = 8
MAX_DC_STORED_REPLY = 10
MAX_QOO_STORED_REPLY = 8
MAX_BLIND_STORED_REPLY = 6
MAX_DC_COMMENT_PAGES = 8
REPLY_LOOKBACK = timedelta(hours=10)
_DC_TOKEN = re.compile(r'id="e_s_n_o"[^>]*value="([^"]+)"')

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

DC_URL = "https://gall.dcinside.com/board/lists/?id=iamsolo&page={page}"
BLIND_URL = "https://www.teamblind.com/kr/topics/Im%EC%86%94%EB%A1%9C"
QOO_URL = "https://theqoo.net/iamsolo?page={page}"
MAX_QOO_PAGES = 80
YT_SEARCH_URL = "https://www.youtube.com/results?search_query=%EB%82%98%EB%8A%94%EC%86%94%EB%A1%9C&sp=CAI%3D"
MAX_YT_SEARCH_PAGES = 4
MAX_YT_COMMENT_PAGES = 20
COLLECT_SECS = 38
DDG_URL = "https://html.duckduckgo.com/html/"
BING_URL = "https://www.bing.com/search"
MAX_SOCIAL_PAGES = 8
LIVE_SOCIAL_PAGES = 1
DDG_PAGE_SIZE = 10
BING_PAGE_SIZE = 10
MAX_SOCIAL_REPLY_THREADS = 8
JINA_URL = "https://r.jina.ai/"
JINA_TIMEOUT = httpx.Timeout(8.0, connect=4.0)
SOCIAL_QUERIES = {
    "threads": (
        "site:threads.com 나는솔로",
        "site:threads.com 나솔 34기",
        "site:threads.net 나는솔로",
    ),
    "ig": (
        "site:instagram.com 나는솔로",
        "site:instagram.com 나솔 34기",
        "site:instagram.com 나는solo",
    ),
    "fb": (
        "site:facebook.com 나는솔로 34기",
        "site:facebook.com 나는솔로",
    ),
}
SOCIAL_BACKFILL_QUERIES = {
    "threads": ("site:threads.com 나는솔로 10월", "site:threads.com 나솔 34기 10월"),
    "ig": ("site:instagram.com 나는솔로 10월", "site:instagram.com 나솔 34기 10월"),
    "fb": ("site:facebook.com 나는솔로 10월", "site:facebook.com 나솔 34기 10월"),
}
_YT_KEY = re.compile(r'INNERTUBE_API_KEY":"([^"]+)"')
_YT_VER = re.compile(r'INNERTUBE_CLIENT_VERSION":"([^"]+)"')


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def empty_board() -> dict:
    return {"startedAt": CUTOFF.isoformat(), "updatedAt": None, "posts": []}


def load_board(path: Path) -> dict:
    if not path.exists():
        return empty_board()
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("posts", [])
    data["startedAt"] = CUTOFF.isoformat()
    return data


def save_board(path: Path, board: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    board["startedAt"] = CUTOFF.isoformat()
    path.write_text(json.dumps(board, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    posts = board["posts"]
    times = [item for item in (parse_instant(post.get("postedAt") or "") for post in posts) if item]
    meta = {
        "startedAt": CUTOFF.isoformat(),
        "updatedAt": board.get("updatedAt"),
        "count": len(posts),
        "oldestAt": min(times).isoformat() if times else None,
        "newestAt": max(times).isoformat() if times else None,
    }
    META_PATH.parent.mkdir(parents=True, exist_ok=True)
    META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_instant(value: str) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=KST)
    return parsed


def as_kst_iso(value: datetime) -> str:
    return value.astimezone(KST).replace(microsecond=0).isoformat()


def normalize_dc_time(value: str) -> str:
    parsed = parse_instant(value.replace(" ", "T") if value else "")
    if parsed is None:
        return ""
    return as_kst_iso(parsed)


def label_to_time(label: str, now: datetime) -> datetime:
    text = (label or "").strip().replace("작성시간", "").strip()
    text = re.sub(r"\([^)]*\)$", "", text).strip()
    if text.endswith("전"):
        text = text[:-1].strip()
    if text in ("", "방금", "조금"):
        return now
    if text == "어제":
        return now - timedelta(days=1)
    if text == "그저께":
        return now - timedelta(days=2)
    for suffix, unit in (("분", "minutes"), ("시간", "hours"), ("일", "days"), ("주", "weeks")):
        if text.endswith(suffix) and text[: -len(suffix)].isdigit():
            return now - timedelta(**{unit: int(text[: -len(suffix)])})
    if text.endswith("개월") and text[:-2].isdigit():
        return now - timedelta(days=30 * int(text[:-2]))
    if text.endswith("년") and text[:-1].isdigit():
        return now - timedelta(days=365 * int(text[:-1]))
    for fmt in ("%Y.%m.%d", "%Y-%m-%d", "%m.%d"):
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        if fmt == "%m.%d":
            parsed = parsed.replace(year=now.year)
            if parsed.date() > now.date():
                parsed = parsed.replace(year=now.year - 1)
        stamp = datetime.combine(parsed.date(), datetime.min.time(), tzinfo=KST).replace(hour=23, minute=59)
        if stamp.date() == CUTOFF.date() and stamp < CUTOFF:
            return CUTOFF
        return stamp
    return now


def assign_blind_times(items: list[dict], now: datetime) -> None:
    """최신순 목록이다. 같은 상대시각은 위에 있는 글이 더 최근이 되게 1초씩 벌린다."""
    used: dict[datetime, int] = {}
    for item in items:
        label = (item.get("posted_label") or "").strip()
        if label in {"", "undefined"}:
            stamp = now
        else:
            stamp = label_to_time(label, now)
        offset = used.get(stamp, 0)
        used[stamp] = offset + 1
        item["posted_at"] = as_kst_iso(stamp - timedelta(seconds=offset))


def on_or_after_cutoff(value: str) -> bool:
    parsed = parse_instant(value)
    if parsed is None:
        return True
    return parsed >= CUTOFF


def to_public(post: dict, *, post_id: int, seen_at: str) -> dict:
    posted_at = post.get("posted_at") or ""
    if post["source"] == "dc":
        posted_at = normalize_dc_time(posted_at)
    public = {
        "id": post_id,
        "source": post["source"],
        "externalId": post["external_id"],
        "title": post["title"],
        "excerpt": post.get("excerpt") or "",
        "author": post.get("author") or "익명",
        "company": post.get("company") or "",
        "ip": post.get("ip") or "",
        "badge": post.get("badge") or "",
        "url": post["url"],
        "postedLabel": post.get("posted_label") or "",
        "postedAt": posted_at,
        "views": post.get("views"),
        "recommends": post.get("recommends"),
        "comments": post.get("comments"),
        "firstSeenAt": seen_at,
        "isSeed": False,
    }
    if post.get("kind"):
        public["kind"] = post["kind"]
    return public


def time_key(item: dict) -> datetime:
    parsed = parse_instant(item.get("posted_at") or item.get("postedAt") or "")
    return parsed or datetime.max.replace(tzinfo=KST)


def merge(board: dict, fetched: dict[str, list[dict]], *, now: str | None = None) -> int:
    """없던 글만 시간순으로 붙인다. 시작 시각보다 이전 글·사계 글은 넣지 않는다."""
    seen_at = now or utc_now()
    posts: list[dict] = board.setdefault("posts", [])
    posts[:] = [
        post
        for post in posts
        if on_or_after_cutoff(post.get("postedAt") or "") and should_keep(post)
    ]
    known = {(post["source"], post["externalId"]) for post in posts}
    next_id = max((post["id"] for post in posts), default=0)
    fresh: list[dict] = []
    for items in fetched.values():
        for item in items:
            if not on_or_after_cutoff(item.get("posted_at") or ""):
                continue
            key = (item["source"], item["external_id"])
            if key in known:
                continue
            known.add(key)
            fresh.append(item)
    fresh.sort(key=lambda item: (time_key(item), item["source"], item["external_id"]))
    reasons: Counter[str] = Counter()
    added = 0
    for item in fresh:
        reason = drop_reason(item)
        if reason:
            reasons[reason] += 1
            if sum(reasons.values()) <= 40:
                print(f"drop [{reason}] {(item.get('title') or '')[:70]}", flush=True)
            continue
        next_id += 1
        posts.append(to_public(item, post_id=next_id, seen_at=seen_at))
        added += 1
    board["startedAt"] = CUTOFF.isoformat()
    if added:
        board["updatedAt"] = seen_at
    if reasons:
        print("filtered", sum(reasons.values()), dict(reasons.most_common(12)), flush=True)
    return added


def source_needs_backfill(board: dict, source: str) -> bool:
    times = [
        item
        for item in (
            parse_instant(post.get("postedAt") or "")
            for post in board["posts"]
            if post.get("source") == source
        )
        if item
    ]
    if not times:
        return True
    return min(times) > CUTOFF + timedelta(hours=3)


def social_crawl_state(board: dict, source: str) -> dict:
    crawl = board.setdefault("socialCrawl", {})
    state = crawl.setdefault(source, {})
    state.setdefault("pages", {})
    state.setdefault("doneQueries", [])
    state.setdefault("done", False)
    return state


def social_needs_backfill(board: dict, source: str) -> bool:
    """아직 안 읽은 검색 페이지만 이어서 본다. 다 돈 소스는 첫 장만 본다."""
    return not social_crawl_state(board, source).get("done")


def comments_need_backfill(posts: list[dict], crawl: dict | None = None) -> bool:
    """2주치 댓글을 아직 안 연 글이 있으면 다음 분에 이어서 본다."""
    crawl = crawl or {}
    sources = ("dc", "qoo", "blind", "threads", "ig", "fb")
    done_by = {source: set((crawl.get(source) or {}).get("doneIds") or []) for source in sources}
    for post in posts:
        source = post.get("source") or ""
        if source not in done_by or post.get("kind") == "reply":
            continue
        eid = post.get("externalId") or post.get("external_id") or ""
        if not eid or eid in done_by[source]:
            continue
        if source in {"dc", "qoo", "blind"} and not (post.get("comments") or 0):
            continue
        return True
    return False


def as_internal(post: dict) -> dict:
    if "external_id" in post:
        return post
    return {
        "source": post.get("source") or "",
        "external_id": post.get("externalId") or post.get("external_id") or "",
        "title": post.get("title") or "",
        "excerpt": post.get("excerpt") or "",
        "url": post.get("url") or "",
        "author": post.get("author") or "",
        "posted_at": post.get("postedAt") or post.get("posted_at") or "",
        "posted_label": post.get("postedLabel") or post.get("posted_label") or "",
        "comments": post.get("comments"),
        "kind": post.get("kind"),
    }


def past_deadline(deadline: float | None) -> bool:
    return deadline is not None and time.monotonic() >= deadline


def _get_text(client: httpx.Client, url: str, headers: dict[str, str]) -> str:
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            response = client.get(url, headers=headers)
            if response.status_code in {429, 500, 502, 503, 504}:
                time.sleep(0.4 * (attempt + 1))
                continue
            response.raise_for_status()
            return response.text
        except httpx.HTTPError as exc:
            last_error = exc
            time.sleep(0.4 * (attempt + 1))
    raise RuntimeError(f"목록을 읽지 못했습니다: {url}") from last_error


def _spread_targets(posts: list[dict], limit: int, now: datetime) -> list[dict]:
    """댓글이 있는 글을 시간대마다 나눠 고른다. 맨 앞만 열면 방금 쓴 글의 댓글만 집계된다."""
    buckets: list[list[dict]] = [[] for _ in range(int(REPLY_LOOKBACK.total_seconds() // 3600))]
    for post in posts:
        if post.get("kind") == "reply" or not (post.get("comments") or 0):
            continue
        stamp = parse_instant(post.get("posted_at") or "")
        if stamp is None:
            continue
        age = (now - stamp).total_seconds() / 3600
        if age < 0 or age >= len(buckets):
            continue
        buckets[int(age)].append(post)
    picked: list[dict] = []
    while len(picked) < limit and any(buckets):
        for bucket in buckets:
            if bucket and len(picked) < limit:
                picked.append(bucket.pop(0))
    if len(picked) < limit:
        seen = {id(post) for post in picked}
        for post in posts:
            if len(picked) >= limit:
                break
            if id(post) in seen or post.get("kind") == "reply" or not (post.get("comments") or 0):
                continue
            picked.append(post)
    return picked


def _read_once(client: httpx.Client, url: str, headers: dict[str, str]) -> str:
    response = client.get(url, headers=headers)
    if response.status_code in {404, 410}:
        return ""
    response.raise_for_status()
    return response.text


def fetch_dc_replies(
    client: httpx.Client,
    posts: list[dict],
    now: datetime | None = None,
    *,
    deadline: float | None = None,
    stored: list[dict] | None = None,
    crawl: dict | None = None,
) -> list[dict]:
    """최근 글과 아직 안 연 2주치 글의 댓글을 읽는다."""
    current = now or datetime.now(KST)
    crawl = crawl if crawl is not None else {}
    done = _mark_zero_comment_done(stored, crawl)
    live_limit = MAX_DC_REPLY_THREADS
    stored_limit = MAX_DC_STORED_REPLY
    if comments_need_backfill(list(stored or []) + list(posts or []), {"dc": crawl}):
        live_limit = 8
    found: list[dict] = []
    for post in _pick_reply_parents(
        posts,
        stored,
        crawl,
        current,
        source="dc",
        live_limit=live_limit,
        stored_limit=stored_limit,
        require_count=True,
    ):
        if past_deadline(deadline):
            print("dc comments budget", flush=True)
            break
        no = post.get("external_id") or ""
        try:
            html = _read_once(client, post["url"], {"Referer": "https://gall.dcinside.com/"})
            if not html:
                continue
            token = _DC_TOKEN.search(html)
            if not token:
                print(f"dc comments {no} no token", flush=True)
                continue
            page_found: list[dict] = []
            for page in range(1, MAX_DC_COMMENT_PAGES + 1):
                response = client.post(
                    "https://gall.dcinside.com/board/comment/",
                    data={
                        "id": "iamsolo",
                        "no": no,
                        "cmt_id": "iamsolo",
                        "cmt_no": no,
                        "focus_cno": "",
                        "focus_pno": "-1",
                        "e_s_n_o": token.group(1),
                        "comment_page": str(page),
                        "sort": "D",
                        "prevCnt": "",
                        "board_type": "",
                        "_GALLTYPE_": "G",
                    },
                    headers={
                        "X-Requested-With": "XMLHttpRequest",
                        "Referer": post["url"],
                        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    },
                )
                if response.status_code != 200:
                    break
                payload = response.json()
                batch = parse_dc_comments(payload, post, now=current)
                if not batch:
                    break
                page_found.extend(batch)
                times = [item for item in (parse_instant(row.get("posted_at") or "") for row in batch) if item]
                oldest = min(times) if times else None
                pagination = str(payload.get("pagination") or "")
                has_next = f"viewComments({page + 1}," in pagination
                if not has_next or (oldest is not None and oldest < CUTOFF):
                    break
                time.sleep(0.06)
            found.extend(page_found)
            if no:
                done.add(no)
            print(f"dc comments {no} {len(page_found)}", flush=True)
        except Exception as exc:
            print(f"dc comments {no} failed: {exc}", flush=True)
        time.sleep(0.08)
    crawl["doneIds"] = sorted(done)
    return found


def fetch_qoo_replies(
    client: httpx.Client,
    posts: list[dict],
    now: datetime | None = None,
    *,
    deadline: float | None = None,
    stored: list[dict] | None = None,
    crawl: dict | None = None,
) -> list[dict]:
    """더쿠 댓글 목록을 읽는다. 비회원에게 가린 한 시간 안 댓글은 빠진다."""
    current = now or datetime.now(KST)
    crawl = crawl if crawl is not None else {}
    done = _mark_zero_comment_done(stored, crawl)
    live_limit = MAX_QOO_REPLY_THREADS
    stored_limit = MAX_QOO_STORED_REPLY
    if comments_need_backfill(list(stored or []) + list(posts or []), {"qoo": crawl}):
        live_limit = 6
    found: list[dict] = []
    for post in _pick_reply_parents(
        posts,
        stored,
        crawl,
        current,
        source="qoo",
        live_limit=live_limit,
        stored_limit=stored_limit,
        require_count=True,
    ):
        if past_deadline(deadline):
            print("qoo comments budget", flush=True)
            break
        sid = post.get("external_id") or ""
        try:
            response = client.post(
                "https://theqoo.net/index.php",
                data={
                    "act": "dispTheqooContentCommentListTheqoo",
                    "document_srl": sid,
                    "cpage": "0",
                    "mid": "iamsolo",
                },
                headers={
                    "Referer": post["url"],
                    "X-Requested-With": "XMLHttpRequest",
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                },
            )
            response.raise_for_status()
            batch = parse_theqoo_comments(response.json(), post)
            found.extend(batch)
            if sid:
                done.add(sid)
            print(f"qoo comments {sid} {len(batch)}", flush=True)
        except Exception as exc:
            print(f"qoo comments {sid} failed: {exc}", flush=True)
        time.sleep(0.08)
    crawl["doneIds"] = sorted(done)
    return found


def fetch_blind_replies(
    client: httpx.Client,
    posts: list[dict],
    now: datetime,
    *,
    deadline: float | None = None,
    stored: list[dict] | None = None,
    crawl: dict | None = None,
) -> list[dict]:
    """블라인드 글에 붙어 있는 댓글을 읽는다."""
    crawl = crawl if crawl is not None else {}
    done = _mark_zero_comment_done(stored, crawl)
    live_limit = MAX_BLIND_REPLY_THREADS
    stored_limit = MAX_BLIND_STORED_REPLY
    if comments_need_backfill(list(stored or []) + list(posts or []), {"blind": crawl}):
        live_limit = 4
    found: list[dict] = []
    for post in _pick_reply_parents(
        posts,
        stored,
        crawl,
        now,
        source="blind",
        live_limit=live_limit,
        stored_limit=stored_limit,
        require_count=True,
    ):
        if past_deadline(deadline):
            print("blind comments budget", flush=True)
            break
        sid = post.get("external_id") or ""
        try:
            html = _read_once(client, post["url"], {"Referer": "https://www.teamblind.com/"})
            if not html:
                continue
            batch = parse_blind_comments(html, post)
            found.extend(batch)
            if sid:
                done.add(sid)
            print(f"blind comments {len(batch)} {sid[-24:]}", flush=True)
        except Exception as exc:
            print(f"blind comments failed: {exc}", flush=True)
        time.sleep(0.08)
    crawl["doneIds"] = sorted(done)
    if found:
        assign_blind_times(found, now)
    return found


def fetch_dc(
    client: httpx.Client,
    known_ids: set[str],
    *,
    backfill: bool,
    deadline: float | None = None,
    stored: list[dict] | None = None,
    crawl: dict | None = None,
) -> list[dict]:
    headers = {"Referer": "https://gall.dcinside.com/"}
    found: list[dict] = []
    seen_page: set[str] = set()
    for page in range(1, MAX_DC_PAGES + 1):
        if past_deadline(deadline):
            print("dc budget", flush=True)
            break
        html = _get_text(client, DC_URL.format(page=page), headers)
        batch = parse_dc(html)
        if not batch:
            print(f"dc page {page} empty", flush=True)
            break
        first_id = batch[0]["external_id"]
        if first_id in seen_page:
            break
        seen_page.add(first_id)
        for item in batch:
            item["posted_at"] = normalize_dc_time(item.get("posted_at") or "")
        found.extend(batch)
        oldest = parse_instant(batch[-1]["posted_at"])
        print(f"dc page {page} {batch[0]['posted_at']} -> {batch[-1]['posted_at']}", flush=True)
        if oldest is not None and oldest < CUTOFF:
            break
        if not backfill and (
            page >= 8
            or (
                any(item["external_id"] in known_ids for item in batch)
                and oldest is not None
                and oldest < datetime.now(KST) - REPLY_LOOKBACK
            )
        ):
            break
        time.sleep(0.12)
    try:
        replies = fetch_dc_replies(client, found, deadline=deadline, stored=stored, crawl=crawl)
    except Exception as exc:
        print(f"dc comments failed: {exc}", flush=True)
        replies = []
    return found + replies


def qoo_label_time(label: str, now: datetime) -> datetime:
    text = (label or "").strip()
    clock = re.fullmatch(r"(\d{1,2}):(\d{2})", text)
    if clock:
        return now.replace(hour=int(clock.group(1)), minute=int(clock.group(2)), second=0, microsecond=0)
    dated = re.fullmatch(r"(\d{2})\.(\d{2})\.(\d{2})", text)
    if dated:
        return datetime(2000 + int(dated.group(1)), int(dated.group(2)), int(dated.group(3)), 23, 59, tzinfo=KST)
    month_day = re.fullmatch(r"(\d{1,2})\.(\d{1,2})", text)
    if month_day:
        year = now.year
        try:
            stamp = datetime(year, int(month_day.group(1)), int(month_day.group(2)), 23, 59, tzinfo=KST)
        except ValueError:
            return now
        if stamp.date() > now.date():
            stamp = stamp.replace(year=year - 1)
        return stamp
    return now


def stamp_newest_first(items: list[dict], now: datetime, label_time) -> None:
    used: dict[datetime, int] = {}
    for item in items:
        stamp = label_time(item.get("posted_label") or "", now)
        offset = used.get(stamp, 0)
        used[stamp] = offset + 1
        item["posted_at"] = as_kst_iso(stamp - timedelta(seconds=offset))


def fetch_qoo(
    client: httpx.Client,
    known_ids: set[str],
    *,
    backfill: bool,
    now: datetime,
    deadline: float | None = None,
    stored: list[dict] | None = None,
    crawl: dict | None = None,
) -> list[dict]:
    headers = {"Referer": "https://theqoo.net/"}
    found: list[dict] = []
    seen_page: set[str] = set()
    for page in range(1, MAX_QOO_PAGES + 1):
        if past_deadline(deadline):
            print("qoo budget", flush=True)
            break
        html = _get_text(client, QOO_URL.format(page=page), headers)
        batch = parse_theqoo(html)
        if not batch:
            print(f"qoo page {page} empty", flush=True)
            break
        first_id = batch[0]["external_id"]
        if first_id in seen_page:
            break
        seen_page.add(first_id)
        found.extend(batch)
        oldest = qoo_label_time(batch[-1].get("posted_label") or "", now)
        print(f"qoo page {page} {batch[0]['posted_label']} -> {batch[-1]['posted_label']}", flush=True)
        if oldest < CUTOFF:
            break
        if not backfill and (page >= 4 or (any(item["external_id"] in known_ids for item in batch) and oldest < now - REPLY_LOOKBACK)):
            break
        time.sleep(0.12)
    stamp_newest_first(found, now, qoo_label_time)
    if backfill and not found:
        raise RuntimeError("더쿠 목록에서 글을 찾지 못했습니다")
    try:
        replies = fetch_qoo_replies(client, found, now, deadline=deadline, stored=stored, crawl=crawl)
    except Exception as exc:
        print(f"qoo comments failed: {exc}", flush=True)
        replies = []
    return found + replies


def fetch_blind(
    client: httpx.Client,
    now: datetime,
    *,
    deadline: float | None = None,
    stored: list[dict] | None = None,
    crawl: dict | None = None,
) -> list[dict]:
    headers = {"Referer": "https://www.teamblind.com/"}
    html = _get_text(client, BLIND_URL, headers)
    posts = parse_blind(html)
    if not posts:
        raise RuntimeError("블라인드 목록에서 글을 찾지 못했습니다")
    assign_blind_times(posts, now)
    try:
        replies = fetch_blind_replies(client, posts, now, deadline=deadline, stored=stored, crawl=crawl)
    except Exception as exc:
        print(f"blind comments failed: {exc}", flush=True)
        replies = []
    return posts + replies


def _yt_client_info(html: str) -> tuple[str, str]:
    key = _YT_KEY.search(html)
    version = _YT_VER.search(html)
    if not key or not version:
        raise RuntimeError("유튜브 화면을 읽지 못했습니다")
    return key.group(1), version.group(1)


def _yt_json(client: httpx.Client, key: str, version: str, endpoint: str, continuation: str) -> dict:
    payload = {
        "context": {"client": {"clientName": "WEB", "clientVersion": version, "hl": "ko", "gl": "KR"}},
        "continuation": continuation,
    }
    response = client.post(
        f"https://www.youtube.com/youtubei/v1/{endpoint}?key={key}&prettyPrint=false",
        json=payload,
        headers={"Content-Type": "application/json", "Referer": "https://www.youtube.com/"},
    )
    response.raise_for_status()
    return response.json()


def _youtube_comments(
    client: httpx.Client,
    key: str,
    version: str,
    video: dict,
    known_ids: set[str],
    now: datetime,
    *,
    backfill: bool,
    deadline: float | None = None,
) -> list[dict]:
    html = _get_text(client, f"https://www.youtube.com/watch?v={video['video_id']}", {"Referer": "https://www.youtube.com/"})
    meta = parse_youtube_watch_meta(html)
    if meta.get("description"):
        video["description"] = meta["description"]
    if meta.get("title") and not video.get("title"):
        video["title"] = meta["title"]
    if skip_youtube_video(video):
        print(f"yt skip {video['video_id']} sagye {(video.get('title') or '')[:50]}", flush=True)
        return []
    token = youtube_newest_token(load_youtube_data(html))
    if not token:
        return []
    page_limit = MAX_YT_COMMENT_PAGES if backfill else 3
    found: list[dict] = []
    for _page in range(page_limit):
        if past_deadline(deadline):
            break
        data = _yt_json(client, key, version, "next", token)
        batch, token = parse_youtube_comments(data, video)
        if not batch:
            break
        found.extend(batch)
        oldest = label_to_time(batch[-1].get("posted_label") or "", now)
        if oldest < CUTOFF:
            break
        if not backfill and any(item["external_id"] in known_ids for item in batch):
            break
        if not token:
            break
        time.sleep(0.05)
    return found


def fetch_youtube(
    client: httpx.Client,
    known_ids: set[str],
    *,
    backfill: bool,
    now: datetime,
    deadline: float | None = None,
) -> list[dict]:
    html = _get_text(client, YT_SEARCH_URL, {"Referer": "https://www.youtube.com/"})
    key, version = _yt_client_info(html)
    data = load_youtube_data(html)
    found: list[dict] = []
    seen_videos: set[str] = set()
    page_limit = MAX_YT_SEARCH_PAGES if backfill else 1
    for _page in range(page_limit):
        if past_deadline(deadline):
            print("yt budget", flush=True)
            break
        videos, token = parse_youtube_search(data)
        if not videos:
            break
        stop_search = False
        for video in videos:
            if past_deadline(deadline):
                stop_search = True
                break
            if video["video_id"] in seen_videos:
                continue
            seen_videos.add(video["video_id"])
            if skip_youtube_video(video):
                print(f"yt skip {video['video_id']} blocked {(video.get('title') or '')[:50]}", flush=True)
                continue
            label = (video.get("published_label") or "").replace("스트리밍 시간:", "").replace("최초 공개:", "").strip()
            published = label_to_time(label, now)
            if published < CUTOFF - timedelta(hours=18):
                stop_search = True
                continue
            batch = _youtube_comments(
                client, key, version, video, known_ids, now, backfill=backfill, deadline=deadline
            )
            found.extend(batch)
            print(f"yt {video['video_id']} {video.get('published_label')} comments {len(batch)}", flush=True)
            time.sleep(0.08)
        if stop_search or not backfill or not token:
            break
        data = _yt_json(client, key, version, "search", token)
        time.sleep(0.08)
    if found:
        stamp_newest_first(found, now, label_to_time)
    return found


def _ddg_blocked(html: str, status: int | None = None) -> bool:
    if status in {202, 429, 500, 502, 503, 504}:
        return True
    text = html or ""
    return "anomaly-modal" in text or "If this persists" in text


def fetch_ddg(client: httpx.Client, query: str, *, start: int = 0) -> str:
    headers = {"Referer": "https://html.duckduckgo.com/html/", "Accept": "text/html"}
    params: dict[str, str] = {"q": query, "kl": "kr-ko"}
    if start:
        params["s"] = str(start)
    last = ""
    tries = 2 if start == 0 else 1
    for attempt in range(tries):
        try:
            response = client.get(DDG_URL, params=params, headers=headers)
            last = response.text
            if _ddg_blocked(last, response.status_code):
                if start:
                    return last
                time.sleep(0.8 * (attempt + 1))
                continue
            response.raise_for_status()
            return last
        except httpx.HTTPError:
            time.sleep(0.8 * (attempt + 1))
    return last


def fetch_bing(client: httpx.Client, query: str, *, first: int = 1) -> str:
    headers = {"Referer": "https://www.bing.com/", "Accept": "text/html"}
    params: dict[str, str] = {"q": query, "setlang": "ko-KR"}
    if first > 1:
        params["first"] = str(first)
        params["FORM"] = "PORE"
    try:
        response = client.get(BING_URL, params=params, headers=headers)
        response.raise_for_status()
        return response.text
    except httpx.HTTPError as exc:
        print(f"bing failed {query}: {exc}", flush=True)
        return ""


def _absorb_social(batch: list[dict], found: list[dict], seen: set[str], now: datetime) -> int:
    added = 0
    for item in batch:
        if item["external_id"] in seen:
            continue
        seen.add(item["external_id"])
        if not item.get("posted_at"):
            item["posted_at"] = as_kst_iso(now)
            item["posted_label"] = item["posted_at"][11:16]
        found.append(item)
        added += 1
    return added


def _mark_query_done(crawl: dict, query: str) -> None:
    done = set(crawl.get("doneQueries") or [])
    done.add(query)
    crawl["doneQueries"] = sorted(done)


def fetch_social(
    client: httpx.Client,
    source: str,
    now: datetime,
    *,
    backfill: bool = False,
    deadline: float | None = None,
    crawl: dict | None = None,
) -> list[dict]:
    found: list[dict] = []
    seen: set[str] = set()
    queries = list(SOCIAL_QUERIES[source])
    if backfill:
        queries.extend(SOCIAL_BACKFILL_QUERIES.get(source, ()))
    crawl = crawl if crawl is not None else {}
    pages = crawl.setdefault("pages", {})
    done_queries = set(crawl.get("doneQueries") or [])
    page_limit = MAX_SOCIAL_PAGES if backfill else LIVE_SOCIAL_PAGES
    ddg_alive = True
    for query in queries:
        if past_deadline(deadline):
            print(f"{source} search budget", flush=True)
            break
        if backfill and query in done_queries:
            continue
        start_page = int(pages.get(query) or 0) if backfill else 0
        if start_page >= page_limit:
            _mark_query_done(crawl, query)
            continue
        for page in range(start_page, page_limit):
            if past_deadline(deadline):
                print(f"{source} search budget", flush=True)
                return found
            added = 0
            got_html = False
            if ddg_alive:
                html = fetch_ddg(client, query, start=page * DDG_PAGE_SIZE)
                if _ddg_blocked(html):
                    ddg_alive = False
                    print(f"{source} ddg stop {query} s={page * DDG_PAGE_SIZE}", flush=True)
                else:
                    batch = parse_social_search(html, source, now)
                    got_html = bool(batch)
                    added += _absorb_social(batch, found, seen, now)
            if backfill or added == 0 or not ddg_alive:
                html = fetch_bing(client, query, first=1 + page * BING_PAGE_SIZE)
                batch = parse_social_search(html, source, now)
                got_html = got_html or bool(batch)
                added += _absorb_social(batch, found, seen, now)
            pages[query] = page + 1
            print(f"{source} search {query} p{page + 1} +{added} n={len(found)}", flush=True)
            exhausted = (added == 0 and page > 0) or (not got_html and page > 0) or page + 1 >= page_limit
            if exhausted:
                if backfill:
                    _mark_query_done(crawl, query)
                break
            time.sleep(0.35)
    if backfill:
        pending = [query for query in queries if query not in set(crawl.get("doneQueries") or [])]
        crawl["doneQueries"] = sorted(set(crawl.get("doneQueries") or []))
        crawl["pages"] = pages
        crawl["done"] = not pending
        if crawl["done"]:
            print(f"{source} search done", flush=True)
    return found


def _social_comments_finished(source: str, markdown: str, batch: list[dict]) -> bool:
    """댓글을 실제로 읽었거나, 쓰레드처럼 본문을 해석한 뒤에만 끝난 글로 본다."""
    if batch:
        return True
    if source == "threads":
        return True
    text = markdown or ""
    lowered = text.lower()
    if any(mark in lowered for mark in ("log in", "로그인", "create new account", "see more on facebook", "abusealleviation")):
        return False
    if source in {"ig", "fb"} and not re.search(r"(?i)comments?|댓글", text):
        return False
    return False


def fetch_jina(client: httpx.Client, url: str) -> str | None:
    """공개 페이지를 Jina 리더로 읽는다. 차단이면 None, 빈 본문은 ''."""
    if not url:
        return ""
    try:
        response = client.get(
            JINA_URL + url,
            headers={
                "Accept": "application/json",
                "X-Return-Format": "markdown",
                "X-Timeout": "8",
            },
            timeout=JINA_TIMEOUT,
        )
    except httpx.HTTPError as exc:
        print(f"jina failed {url}: {exc}", flush=True)
        return ""
    if response.status_code in {401, 403}:
        return None
    if response.status_code in {404, 410}:
        return ""
    try:
        payload = response.json()
    except ValueError:
        payload = response.text
    md = jina_markdown(payload)
    if md is None:
        return None
    return md


def _comment_targets(
    posts: list[dict],
    crawl: dict,
    now: datetime,
    *,
    limit: int,
    source: str,
    fresh_ids: set[str] | None = None,
    recheck: bool = False,
    require_count: bool = False,
) -> list[dict]:
    """안 읽은 글을 먼저 보고, 필요하면 최근 10시간을 다시 연다."""
    done = set(crawl.get("doneIds") or [])
    fresh_ids = fresh_ids or set()
    pending_new: list[dict] = []
    pending_old: list[dict] = []
    recent: list[dict] = []
    seen: set[str] = set()
    for post in posts:
        item = as_internal(post)
        if item.get("kind") == "reply":
            continue
        eid = item.get("external_id") or ""
        if not eid or not item.get("url") or eid in seen:
            continue
        seen.add(eid)
        if require_count and not (item.get("comments") or 0):
            continue
        if eid not in done:
            if eid in fresh_ids:
                pending_new.append(item)
            else:
                pending_old.append(item)
            continue
        if not recheck:
            continue
        stamp = parse_instant(item.get("posted_at") or "")
        if stamp is not None and now - stamp <= REPLY_LOOKBACK:
            recent.append(item)
    pending_old.sort(key=lambda item: parse_instant(item.get("posted_at") or "") or datetime.max.replace(tzinfo=KST))
    return (pending_new + pending_old + recent)[:limit]


def _social_comment_targets(
    posts: list[dict],
    crawl: dict,
    now: datetime,
    *,
    limit: int,
    source: str,
    fresh_ids: set[str] | None = None,
) -> list[dict]:
    return _comment_targets(
        posts,
        crawl,
        now,
        limit=limit,
        source=source,
        fresh_ids=fresh_ids,
        recheck=source == "threads",
        require_count=False,
    )


def _pick_reply_parents(
    found: list[dict],
    stored: list[dict] | None,
    crawl: dict,
    now: datetime,
    *,
    source: str,
    live_limit: int,
    stored_limit: int,
    require_count: bool,
) -> list[dict]:
    live = _spread_targets(found, live_limit, now)
    extra = _comment_targets(
        [as_internal(post) for post in (stored or [])] + list(found or []),
        crawl,
        now,
        limit=stored_limit,
        source=source,
        require_count=require_count,
        recheck=False,
    )
    picked: list[dict] = []
    seen: set[str] = set()
    for post in live + extra:
        item = as_internal(post)
        eid = item.get("external_id") or ""
        if not eid or eid in seen:
            continue
        seen.add(eid)
        picked.append(item)
    return picked


def _mark_zero_comment_done(stored: list[dict] | None, crawl: dict) -> set[str]:
    done = set(crawl.get("doneIds") or [])
    for post in stored or []:
        item = as_internal(post)
        eid = item.get("external_id") or ""
        if eid and not (item.get("comments") or 0):
            done.add(eid)
    crawl["doneIds"] = sorted(done)
    return done


def fetch_social_replies(
    client: httpx.Client,
    posts: list[dict],
    now: datetime,
    *,
    deadline: float | None = None,
    crawl: dict | None = None,
    fresh_ids: dict[str, set[str]] | None = None,
) -> list[dict]:
    """저장된 쓰레드·인스타·페북 글의 댓글을 이어서 읽는다."""
    found: list[dict] = []
    crawl = crawl if crawl is not None else {}
    fresh_ids = fresh_ids or {}
    remaining = MAX_SOCIAL_REPLY_THREADS
    for source in ("threads", "ig", "fb"):
        if remaining <= 0 or past_deadline(deadline):
            print("social comments budget", flush=True)
            break
        state = crawl.setdefault(source, {})
        state.setdefault("doneIds", [])
        done = set(state.get("doneIds") or [])
        parents = [post for post in posts if (post.get("source") or "") == source]
        targets = _social_comment_targets(
            parents,
            state,
            now,
            limit=remaining,
            source=source,
            fresh_ids=fresh_ids.get(source) or set(),
        )
        for parent in targets:
            if remaining <= 0 or past_deadline(deadline):
                print("social comments budget", flush=True)
                break
            remaining -= 1
            eid = parent.get("external_id") or ""
            try:
                markdown = fetch_jina(client, parent.get("url") or "")
            except Exception as exc:
                print(f"{source} comments {eid} failed: {exc}", flush=True)
                continue
            if markdown is None:
                print(f"{source} comments {eid} blocked", flush=True)
                continue
            batch = parse_social_replies(markdown, parent)
            found.extend(batch)
            if _social_comments_finished(source, markdown, batch):
                done.add(eid)
            else:
                print(f"{source} comments {eid} empty retry", flush=True)
            print(f"{source} comments {eid} {len(batch)}", flush=True)
            time.sleep(0.15)
        state["doneIds"] = sorted(done)
        crawl[source] = state
    return found


def fetch_sources(
    known_dc: set[str],
    known_qoo: set[str],
    known_yt: set[str],
    *,
    dc_backfill: bool,
    qoo_backfill: bool,
    yt_backfill: bool,
    threads_backfill: bool = False,
    ig_backfill: bool = False,
    fb_backfill: bool = False,
    deadline: float | None = None,
    social_crawl: dict | None = None,
    stored_posts: list[dict] | None = None,
    comment_crawl: dict | None = None,
) -> dict[str, list[dict]]:
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    }
    timeout = httpx.Timeout(8.0, connect=5.0)
    now = datetime.now(KST).replace(microsecond=0)
    fetched: dict[str, list[dict]] = {"dc": [], "blind": [], "qoo": [], "yt": [], "threads": [], "ig": [], "fb": []}
    stop_at = deadline if deadline is not None else time.monotonic() + COLLECT_SECS
    crawl = social_crawl if social_crawl is not None else {}
    comments = comment_crawl if comment_crawl is not None else {}
    stored = stored_posts or []
    stored_by = {
        source: [as_internal(post) for post in stored if post.get("source") == source]
        for source in ("dc", "qoo", "blind", "threads", "ig", "fb")
    }
    social_pending = threads_backfill or ig_backfill or fb_backfill
    comment_pending = comments_need_backfill(stored, comments)
    with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
        loaders: list[tuple[str, object]] = [
            ("dc", lambda: fetch_dc(
                client,
                known_dc,
                backfill=dc_backfill,
                deadline=stop_at,
                stored=None,
                crawl=comments.setdefault("dc", {}),
            )),
            ("blind", lambda: fetch_blind(
                client,
                now,
                deadline=stop_at,
                stored=None,
                crawl=comments.setdefault("blind", {}),
            )),
            ("qoo", lambda: fetch_qoo(
                client,
                known_qoo,
                backfill=qoo_backfill,
                now=now,
                deadline=stop_at,
                stored=None,
                crawl=comments.setdefault("qoo", {}),
            )),
        ]
        social_loaders = (
            ("threads", lambda: fetch_social(client, "threads", now, backfill=threads_backfill, deadline=stop_at, crawl=crawl.setdefault("threads", {}))),
            ("ig", lambda: fetch_social(client, "ig", now, backfill=ig_backfill, deadline=stop_at, crawl=crawl.setdefault("ig", {}))),
            ("fb", lambda: fetch_social(client, "fb", now, backfill=fb_backfill, deadline=stop_at, crawl=crawl.setdefault("fb", {}))),
        )
        if social_pending or comment_pending:
            loaders.extend(social_loaders)
        else:
            loaders.append(("yt", lambda: fetch_youtube(client, known_yt, backfill=yt_backfill, now=now, deadline=stop_at)))
            loaders.extend(social_loaders)
        if comment_pending:
            print("comment-backfill skip-yt", flush=True)
        started = time.monotonic()
        parents: list[dict] = []
        extra_dc: list[dict] = []
        extra_qoo: list[dict] = []
        extra_blind: list[dict] = []
        replies: list[dict] = []
        for source in ("threads", "ig", "fb"):
            parents.extend(stored_by.get(source) or [])
        try:
            extra_dc = fetch_dc_replies(
                client,
                [],
                now,
                deadline=stop_at,
                stored=stored_by["dc"],
                crawl=comments.setdefault("dc", {}),
            )
            fetched["dc"].extend(extra_dc)
            extra_qoo = fetch_qoo_replies(
                client,
                [],
                now,
                deadline=stop_at,
                stored=stored_by["qoo"],
                crawl=comments.setdefault("qoo", {}),
            )
            fetched["qoo"].extend(extra_qoo)
            extra_blind = fetch_blind_replies(
                client,
                [],
                now,
                deadline=stop_at,
                stored=stored_by["blind"],
                crawl=comments.setdefault("blind", {}),
            )
            fetched["blind"].extend(extra_blind)
            replies = fetch_social_replies(
                client,
                parents,
                now,
                deadline=stop_at,
                crawl=comments,
            )
        except Exception as exc:
            print(f"comments-first failed: {exc}", flush=True)
        for item in replies:
            fetched.setdefault(item["source"], []).append(item)
        print(
            f"comments-first dc={len(extra_dc)} qoo={len(extra_qoo)} blind={len(extra_blind)} social={len(replies)} {time.monotonic() - started:.1f}s",
            flush=True,
        )
        for name, loader in loaders:
            if past_deadline(stop_at):
                print(f"{name} skip budget", flush=True)
                continue
            started = time.monotonic()
            try:
                fetched[name] = loader() + fetched.get(name, [])
            except Exception as exc:
                print(f"{name} failed: {exc}", flush=True)
            print(f"{name} {len(fetched[name])} {time.monotonic() - started:.1f}s", flush=True)
    if not any(fetched.values()):
        raise RuntimeError("모든 게시판을 읽지 못했습니다")
    return fetched


def main() -> None:
    board = load_board(DATA_PATH)
    force = "--backfill" in sys.argv
    if force:
        board["socialCrawl"] = {}
        board["commentCrawl"] = {}
    dc_backfill = force or source_needs_backfill(board, "dc")
    qoo_backfill = force or source_needs_backfill(board, "qoo")
    yt_backfill = force or source_needs_backfill(board, "yt")
    threads_backfill = force or social_needs_backfill(board, "threads")
    ig_backfill = force or social_needs_backfill(board, "ig")
    fb_backfill = force or social_needs_backfill(board, "fb")
    if dc_backfill or qoo_backfill or yt_backfill:
        board["posts"] = [
            post
            for post in board["posts"]
            if not (
                (dc_backfill and post.get("source") == "dc")
                or (qoo_backfill and post.get("source") == "qoo")
                or (yt_backfill and post.get("source") == "yt")
            )
        ]
        print(
            "backfill",
            "dc" if dc_backfill else "",
            "qoo" if qoo_backfill else "",
            "yt" if yt_backfill else "",
            CUTOFF.isoformat(),
            flush=True,
        )
    if threads_backfill or ig_backfill or fb_backfill:
        print(
            "social-backfill",
            "threads" if threads_backfill else "",
            "ig" if ig_backfill else "",
            "fb" if fb_backfill else "",
            CUTOFF.isoformat(),
            flush=True,
        )
    crawl = board.setdefault("commentCrawl", {})
    for source in ("ig", "fb"):
        has_reply = any(post.get("source") == source and post.get("kind") == "reply" for post in board["posts"])
        if not has_reply:
            crawl.setdefault(source, {})["doneIds"] = []
    known_dc = {post["externalId"] for post in board["posts"] if post.get("source") == "dc"}
    known_qoo = {post["externalId"] for post in board["posts"] if post.get("source") == "qoo"}
    known_yt = {post["externalId"] for post in board["posts"] if post.get("source") == "yt"}
    fetched = fetch_sources(
        known_dc,
        known_qoo,
        known_yt,
        dc_backfill=dc_backfill,
        qoo_backfill=qoo_backfill,
        yt_backfill=yt_backfill,
        threads_backfill=threads_backfill,
        ig_backfill=ig_backfill,
        fb_backfill=fb_backfill,
        social_crawl=board.setdefault("socialCrawl", {}),
        stored_posts=board.get("posts") or [],
        comment_crawl=board.setdefault("commentCrawl", {}),
    )
    added = merge(board, fetched)
    save_board(DATA_PATH, board)
    print(f"added {added} total {len(board['posts'])}")


def export_youtube() -> None:
    """유튜브 댓글만 따로 저장한다. 다른 수집이 글을 쓰는 중에도 겹치지 않게."""
    board = load_board(YT_PATH) if YT_PATH.exists() else empty_board()
    board["posts"] = [post for post in board["posts"] if post.get("source") == "yt"]
    backfill = source_needs_backfill(board, "yt")
    known = {post["externalId"] for post in board["posts"]}
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    }
    now = datetime.now(KST).replace(microsecond=0)
    timeout = httpx.Timeout(25.0, connect=8.0)
    with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
        fetched = fetch_youtube(client, known, backfill=backfill, now=now)
    added = merge(board, {"yt": fetched})
    board["updatedAt"] = utc_now()
    YT_PATH.parent.mkdir(parents=True, exist_ok=True)
    YT_PATH.write_text(json.dumps(board, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"youtube added {added} total {len(board['posts'])}")


if __name__ == "__main__":
    if "--youtube-only" in sys.argv:
        export_youtube()
    else:
        main()

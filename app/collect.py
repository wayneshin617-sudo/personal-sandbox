"""게시판 목록을 읽어 docs/data/posts.json 에 쌓는다.

모으기 시작 시각은 2026-10-07 22:30 KST 다.
이미 그 시각까지 들어가 있으면 첫 페이지만 보고, 없으면 그 시각까지 페이지를 넘긴다.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from .parsers import parse_blind, parse_dc

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "docs" / "data" / "posts.json"
META_PATH = ROOT / "docs" / "data" / "meta.json"

KST = timezone(timedelta(hours=9))
CUTOFF = datetime(2026, 10, 7, 22, 30, tzinfo=KST)
MAX_DC_PAGES = 400

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

DC_URL = "https://gall.dcinside.com/board/lists/?id=iamsolo&page={page}"
BLIND_URL = "https://www.teamblind.com/kr/topics/Im%EC%86%94%EB%A1%9C"


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
    if text in ("", "방금", "조금 전"):
        return now
    if text == "어제":
        return now - timedelta(days=1)
    if text == "그저께":
        return now - timedelta(days=2)
    for suffix, unit in (("분", "minutes"), ("시간", "hours"), ("일", "days")):
        if text.endswith(suffix) and text[: -len(suffix)].isdigit():
            return now - timedelta(**{unit: int(text[: -len(suffix)])})
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
    return {
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


def time_key(item: dict) -> datetime:
    parsed = parse_instant(item.get("posted_at") or item.get("postedAt") or "")
    return parsed or datetime.max.replace(tzinfo=KST)


def merge(board: dict, fetched: dict[str, list[dict]], *, now: str | None = None) -> int:
    """없던 글만 시간순으로 붙인다. 시작 시각보다 이전 글은 넣지 않는다."""
    seen_at = now or utc_now()
    posts: list[dict] = board.setdefault("posts", [])
    posts[:] = [post for post in posts if on_or_after_cutoff(post.get("postedAt") or "")]
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
    for item in fresh:
        next_id += 1
        posts.append(to_public(item, post_id=next_id, seen_at=seen_at))
    board["startedAt"] = CUTOFF.isoformat()
    if fresh:
        board["updatedAt"] = seen_at
    return len(fresh)


def needs_backfill(board: dict) -> bool:
    times = [item for item in (parse_instant(post.get("postedAt") or "") for post in board["posts"]) if item]
    if not times:
        return True
    return min(times) > CUTOFF + timedelta(hours=3)


def _get_text(client: httpx.Client, url: str, headers: dict[str, str]) -> str:
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            response = client.get(url, headers=headers)
            if response.status_code in {429, 500, 502, 503, 504}:
                time.sleep(0.7 * (attempt + 1))
                continue
            response.raise_for_status()
            return response.text
        except httpx.HTTPError as exc:
            last_error = exc
            time.sleep(0.7 * (attempt + 1))
    raise RuntimeError(f"목록을 읽지 못했습니다: {url}") from last_error


def fetch_dc(client: httpx.Client, known_ids: set[str], *, backfill: bool) -> list[dict]:
    headers = {"Referer": "https://gall.dcinside.com/"}
    found: list[dict] = []
    seen_page: set[str] = set()
    for page in range(1, MAX_DC_PAGES + 1):
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
        if not backfill and any(item["external_id"] in known_ids for item in batch):
            break
        time.sleep(0.12)
    return found


def fetch_blind(client: httpx.Client, now: datetime) -> list[dict]:
    headers = {"Referer": "https://www.teamblind.com/"}
    html = _get_text(client, BLIND_URL, headers)
    posts = parse_blind(html)
    if not posts:
        raise RuntimeError("블라인드 목록에서 글을 찾지 못했습니다")
    assign_blind_times(posts, now)
    return posts


def fetch_sources(known_ids: set[str], *, backfill: bool) -> dict[str, list[dict]]:
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    }
    timeout = httpx.Timeout(25.0, connect=8.0)
    now = datetime.now(KST).replace(microsecond=0)
    with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
        return {
            "dc": fetch_dc(client, known_ids, backfill=backfill),
            "blind": fetch_blind(client, now),
        }


def main() -> None:
    board = load_board(DATA_PATH)
    backfill = "--backfill" in sys.argv or needs_backfill(board)
    known_ids = {post["externalId"] for post in board["posts"] if post["source"] == "dc"}
    if backfill:
        board["posts"] = []
        known_ids = set()
        print("backfill from", CUTOFF.isoformat(), flush=True)
    fetched = fetch_sources(known_ids, backfill=backfill)
    added = merge(board, fetched)
    save_board(DATA_PATH, board)
    print(f"added {added} total {len(board['posts'])}")


if __name__ == "__main__":
    main()

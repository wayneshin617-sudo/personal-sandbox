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
    load_youtube_data,
    parse_blind,
    parse_dc,
    parse_theqoo,
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


def fetch_qoo(client: httpx.Client, known_ids: set[str], *, backfill: bool, now: datetime) -> list[dict]:
    headers = {"Referer": "https://theqoo.net/"}
    found: list[dict] = []
    seen_page: set[str] = set()
    for page in range(1, MAX_QOO_PAGES + 1):
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
        if not backfill and any(item["external_id"] in known_ids for item in batch):
            break
        time.sleep(0.12)
    stamp_newest_first(found, now, qoo_label_time)
    if backfill and not found:
        raise RuntimeError("더쿠 목록에서 글을 찾지 못했습니다")
    return found


def fetch_blind(client: httpx.Client, now: datetime) -> list[dict]:
    headers = {"Referer": "https://www.teamblind.com/"}
    html = _get_text(client, BLIND_URL, headers)
    posts = parse_blind(html)
    if not posts:
        raise RuntimeError("블라인드 목록에서 글을 찾지 못했습니다")
    assign_blind_times(posts, now)
    return posts


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


def fetch_youtube(client: httpx.Client, known_ids: set[str], *, backfill: bool, now: datetime) -> list[dict]:
    html = _get_text(client, YT_SEARCH_URL, {"Referer": "https://www.youtube.com/"})
    key, version = _yt_client_info(html)
    data = load_youtube_data(html)
    found: list[dict] = []
    seen_videos: set[str] = set()
    page_limit = MAX_YT_SEARCH_PAGES if backfill else 1
    for _page in range(page_limit):
        videos, token = parse_youtube_search(data)
        if not videos:
            break
        stop_search = False
        for video in videos:
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
            batch = _youtube_comments(client, key, version, video, known_ids, now, backfill=backfill)
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


def fetch_sources(
    known_dc: set[str],
    known_qoo: set[str],
    known_yt: set[str],
    *,
    dc_backfill: bool,
    qoo_backfill: bool,
    yt_backfill: bool,
) -> dict[str, list[dict]]:
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    }
    timeout = httpx.Timeout(25.0, connect=8.0)
    now = datetime.now(KST).replace(microsecond=0)
    fetched: dict[str, list[dict]] = {"dc": [], "blind": [], "qoo": [], "yt": []}
    with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
        for name, loader in (
            ("dc", lambda: fetch_dc(client, known_dc, backfill=dc_backfill)),
            ("blind", lambda: fetch_blind(client, now)),
            ("qoo", lambda: fetch_qoo(client, known_qoo, backfill=qoo_backfill, now=now)),
            ("yt", lambda: fetch_youtube(client, known_yt, backfill=yt_backfill, now=now)),
        ):
            try:
                fetched[name] = loader()
            except Exception as exc:
                print(f"{name} failed: {exc}", flush=True)
    if not any(fetched.values()):
        raise RuntimeError("모든 게시판을 읽지 못했습니다")
    return fetched


def main() -> None:
    board = load_board(DATA_PATH)
    force = "--backfill" in sys.argv
    dc_backfill = force or source_needs_backfill(board, "dc")
    qoo_backfill = force or source_needs_backfill(board, "qoo")
    yt_backfill = force or source_needs_backfill(board, "yt")
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

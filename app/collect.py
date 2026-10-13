"""게시판 목록을 한 번 읽어 docs/data/posts.json 에 새 글만 쌓는다."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

from .parsers import parse_blind, parse_dc

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "docs" / "data" / "posts.json"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

SOURCES = {
    "dc": {
        "url": "https://gall.dcinside.com/board/lists/?id=iamsolo",
        "headers": {"Referer": "https://gall.dcinside.com/"},
        "parse": parse_dc,
    },
    "blind": {
        "url": "https://www.teamblind.com/kr/topics/Im%EC%86%94%EB%A1%9C",
        "headers": {"Referer": "https://www.teamblind.com/"},
        "parse": parse_blind,
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def empty_board() -> dict:
    return {"startedAt": None, "updatedAt": None, "posts": []}


def load_board(path: Path) -> dict:
    if not path.exists():
        return empty_board()
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("posts", [])
    return data


def save_board(path: Path, board: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(board, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def to_public(post: dict, *, post_id: int, seen_at: str, is_seed: bool) -> dict:
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
        "postedAt": post.get("posted_at") or "",
        "views": post.get("views"),
        "recommends": post.get("recommends"),
        "comments": post.get("comments"),
        "firstSeenAt": seen_at,
        "isSeed": is_seed,
    }


def merge(board: dict, fetched: dict[str, list[dict]], *, now: str | None = None) -> int:
    """최신순 목록을 받아, 없던 글만 오래된 것부터 붙인다. 추가된 개수를 돌려준다."""
    seen_at = now or utc_now()
    posts: list[dict] = board.setdefault("posts", [])
    known = {(post["source"], post["externalId"]) for post in posts}
    next_id = max((post["id"] for post in posts), default=0)
    added = 0
    if board.get("startedAt") is None and any(fetched.values()):
        board["startedAt"] = seen_at
    for source, items in fetched.items():
        is_seed = not any(post["source"] == source for post in posts)
        for item in reversed(items):
            key = (item["source"], item["external_id"])
            if key in known:
                continue
            next_id += 1
            posts.append(to_public(item, post_id=next_id, seen_at=seen_at, is_seed=is_seed))
            known.add((item["source"], item["external_id"]))
            added += 1
    if added:
        board["updatedAt"] = seen_at
    return added


def fetch_sources() -> dict[str, list[dict]]:
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    }
    timeout = httpx.Timeout(20.0, connect=8.0)
    fetched: dict[str, list[dict]] = {}
    with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
        for name, spec in SOURCES.items():
            response = client.get(spec["url"], headers=spec["headers"])
            response.raise_for_status()
            posts = spec["parse"](response.content.decode("utf-8", errors="replace"))
            if not posts:
                raise RuntimeError(f"{name} 목록에서 글을 찾지 못했습니다")
            fetched[name] = posts
    return fetched


def main() -> None:
    board = load_board(DATA_PATH)
    fetched = fetch_sources()
    added = merge(board, fetched)
    if added or not DATA_PATH.exists():
        save_board(DATA_PATH, board)
    print(f"added {added} total {len(board['posts'])}")


if __name__ == "__main__":
    main()

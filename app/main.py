"""나는솔로 댓글 몰아보기 서버."""

from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .crawler import Crawler, Hub
from .db import Store, to_public

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
DATA_PATH = Path(os.environ.get("DATA_DIR", ROOT.parent / "data")) / "posts.db"

store = Store(DATA_PATH)
hub = Hub()
crawler = Crawler(store, hub)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = asyncio.create_task(crawler.run())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="나는솔로 댓글 몰아보기", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/api/posts")
def posts(
    q: str = "",
    source: str = "",
    limit: int = 120,
    before: int | None = None,
    after: int | None = None,
):
    keyword = q.strip()[:80]
    if source not in {"dc", "blind"}:
        source = ""
    rows = store.list_posts(
        q=keyword,
        source=source,
        limit=limit,
        before_id=before,
        after_id=after,
    )
    return {
        "posts": [to_public(row) for row in rows],
        "matched": store.count_query(q=keyword, source=source),
    }


@app.get("/api/status")
def status():
    return crawler.snapshot()


@app.get("/api/stream")
async def stream():
    queue = hub.subscribe()

    async def events():
        try:
            yield _sse("status", crawler.snapshot())
            while True:
                try:
                    event, data = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield "event: ping\ndata: {}\n\n"
                    continue
                yield _sse(event, data)
        finally:
            hub.unsubscribe(queue)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

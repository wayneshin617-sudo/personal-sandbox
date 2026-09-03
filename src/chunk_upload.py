"""Chunked upload endpoint mounted on the running Streamlit Tornado app.

Streamlit's file uploader sends the whole file in one HTTP PUT. Cloudflare
quick tunnels drop that with AxiosError: Network Error. This handler accepts
small same-origin POSTs and stitches them on disk.
"""

from __future__ import annotations

import gc
import json
import re
from pathlib import Path
from urllib.parse import unquote

import tornado.web
from tornado.routing import PathMatches, Rule
from tornado.web import Application

from config import TEMP_DIR
from src.utils import LOGGER, safe_stem

CHUNK_ROOT = TEMP_DIR / "chunks"
DONE_ROOT = TEMP_DIR / "assembled"
MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024
_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{8,80}$")
_ROUTE_INSTALLED = False


def _safe_name(name: str) -> str:
    raw = Path(unquote(name or "upload.bin")).name or "upload.bin"
    stem = safe_stem(Path(raw).stem) or "upload"
    suffix = Path(raw).suffix[:12]
    return f"{stem}{suffix}"


def assemble_parts(part_dir: Path, dest: Path) -> Path:
    parts = sorted(part_dir.glob("*.part"))
    dest.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with dest.open("wb") as out:
        for part in parts:
            data = part.read_bytes()
            written += len(data)
            if written > MAX_UPLOAD_BYTES:
                raise RuntimeError("파일이 너무 큽니다.")
            out.write(data)
    return dest


class ChunkUploadHandler(tornado.web.RequestHandler):
    def set_default_headers(self) -> None:
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header(
            "Access-Control-Allow-Headers",
            "Content-Type, X-Upload-Id, X-Chunk-Index, X-Chunk-Total, X-File-Name",
        )
        self.set_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.set_header("Cache-Control", "no-store")

    def options(self) -> None:
        self.set_status(204)
        self.finish()

    def get(self) -> None:
        self.finish({"ok": True})

    def post(self) -> None:
        upload_id = (self.request.headers.get("X-Upload-Id") or "").strip()
        if not _SAFE_ID.match(upload_id):
            self.set_status(400)
            self.finish({"ok": False, "error": "bad id"})
            return
        try:
            index = int(self.request.headers.get("X-Chunk-Index", "0"))
            total = int(self.request.headers.get("X-Chunk-Total", "1"))
        except ValueError:
            self.set_status(400)
            self.finish({"ok": False, "error": "bad chunk"})
            return
        if total <= 0 or index < 0 or index >= total or total > 4096:
            self.set_status(400)
            self.finish({"ok": False, "error": "bad range"})
            return
        body = self.request.body or b""
        if len(body) > 8 * 1024 * 1024:
            self.set_status(413)
            self.finish({"ok": False, "error": "chunk too large"})
            return
        name = _safe_name(self.request.headers.get("X-File-Name") or "upload.bin")
        part_dir = CHUNK_ROOT / upload_id
        part_dir.mkdir(parents=True, exist_ok=True)
        (part_dir / f"{index:06d}.part").write_bytes(body)
        LOGGER.info("chunk %s %s/%s %s bytes", upload_id, index + 1, total, len(body))
        if index + 1 < total:
            self.finish({"ok": True, "done": False, "index": index})
            return
        DONE_ROOT.mkdir(parents=True, exist_ok=True)
        dest = DONE_ROOT / f"{upload_id}_{name}"
        try:
            assemble_parts(part_dir, dest)
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("assemble failed")
            self.set_status(500)
            self.finish({"ok": False, "error": str(exc)})
            return
        marker = DONE_ROOT / f"{upload_id}.json"
        marker.write_text(
            json.dumps({"path": str(dest), "name": name, "size": dest.stat().st_size}),
            encoding="utf-8",
        )
        for leftover in part_dir.glob("*"):
            leftover.unlink(missing_ok=True)
        part_dir.rmdir()
        self.finish({"ok": True, "done": True, "path": str(dest), "name": name, "size": dest.stat().st_size})


def _insert_route(app: Application) -> bool:
    router = getattr(app, "wildcard_router", None)
    if router is None or not getattr(router, "rules", None):
        return False
    for rule in router.rules:
        matcher = getattr(rule, "matcher", None)
        pattern = str(getattr(matcher, "regex", getattr(matcher, "path", "")) or "")
        if "_studio/chunk" in pattern:
            return True
    router.rules.insert(0, Rule(PathMatches(r"/_studio/chunk/?"), ChunkUploadHandler))
    LOGGER.info("installed /_studio/chunk upload route")
    return True


def install_chunk_route() -> bool:
    global _ROUTE_INSTALLED
    if _ROUTE_INSTALLED:
        return True
    for obj in gc.get_objects():
        try:
            if isinstance(obj, Application) and _insert_route(obj):
                _ROUTE_INSTALLED = True
                return True
        except Exception:
            continue
    return False


def patch_streamlit_server() -> None:
    from streamlit.web.server.server import Server

    original = Server._create_app
    if getattr(original, "_studio_chunk_patched", False):
        return

    def wrapped(self):
        app = original(self)
        _insert_route(app)
        return app

    wrapped._studio_chunk_patched = True  # type: ignore[attr-defined]
    Server._create_app = wrapped  # type: ignore[method-assign]

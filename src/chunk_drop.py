"""Streamlit component: chunked same-origin file drop."""

from __future__ import annotations

from pathlib import Path

import streamlit.components.v1 as components

from src.chunk_upload import install_chunk_route

_FRONTEND = Path(__file__).resolve().parent.parent / "components" / "chunk_drop"
_drop = components.declare_component("studio_chunk_drop", path=str(_FRONTEND))


def chunk_drop(label: str, *, key: str, multiple: bool = False) -> list[Path]:
    install_chunk_route()
    value = _drop(label=label, multiple=multiple, key=key, default=None)
    if not value or not isinstance(value, dict):
        return []
    files = value.get("files") or []
    out: list[Path] = []
    for item in files:
        path = Path(str(item.get("path") or ""))
        if path.exists() and path.stat().st_size > 0:
            out.append(path)
    return out

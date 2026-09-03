#!/usr/bin/env python3
"""Start Streamlit with the chunked upload route already registered."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.chunk_upload import patch_streamlit_server


def main() -> None:
    patch_streamlit_server()
    from streamlit.web.cli import main as st_main

    sys.argv = [
        "streamlit",
        "run",
        str(ROOT / "app.py"),
        *sys.argv[1:],
    ]
    st_main()


if __name__ == "__main__":
    main()

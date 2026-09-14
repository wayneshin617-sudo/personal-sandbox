#!/usr/bin/env python3
"""Detached identity-swap worker. Closing the browser does not stop this."""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.chunk_upload import remember_result
from src.job_runner import payload_to_config
from src.job_store import write_job
from src.runtime import create_runtime
from src.utils import ProgressEvent


def _progress(ev: ProgressEvent) -> None:
    write_job(
        {
            "status": "running",
            "stage": "swap",
            "detail": ev.message,
            "message": ev.message,
            "current_frame": ev.current,
            "total_frames": ev.total,
        }
    )


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: run_studio_job.py payload.json", file=sys.stderr)
        return 2
    payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    source_sig = str(payload.get("source_sig") or "")
    config = payload_to_config(payload)
    write_job(
        {
            "status": "running",
            "stage": "loading",
            "detail": "모델을 준비하는 중",
            "message": "모델을 준비하는 중",
            "source_sig": source_sig,
        }
    )
    try:
        runtime = create_runtime(load_restorer=bool(config.restore_strength > 0.01))
        runtime.engine.records.clear()
        runtime.engine.swapper.call_count = 0
        result = runtime.job.run(config, progress=_progress)
        if result.ok and result.output_path and Path(result.output_path).is_file():
            remember_result(Path(result.output_path), result.message, source_sig=source_sig)
            write_job(
                {
                    "status": "done",
                    "stage": "done",
                    "detail": result.message,
                    "message": result.message,
                    "output_path": str(result.output_path),
                    "source_sig": source_sig,
                    "frames_total": result.frames_total,
                    "frames_swapped": result.frames_swapped,
                    "frames_kept_original": result.frames_kept_original,
                    "inference_count": result.inference_count,
                    "error": "",
                }
            )
            print(f"DONE {result.output_path}", flush=True)
            return 0
        write_job(
            {
                "status": "error",
                "stage": "error",
                "detail": result.message or "결과를 저장하지 못했습니다.",
                "message": result.message or "결과를 저장하지 못했습니다.",
                "source_sig": source_sig,
                "error": result.message or "no output",
            }
        )
        return 1
    except Exception as exc:
        write_job(
            {
                "status": "error",
                "stage": "error",
                "detail": str(exc),
                "message": "생성에 실패했습니다. 다시 눌러 주세요.",
                "error": traceback.format_exc(),
                "source_sig": source_sig,
            }
        )
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

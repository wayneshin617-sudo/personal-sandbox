#!/usr/bin/env python3
"""Run an all-faces swap on the user's uploaded photo + video."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import OUTPUTS_DIR, ensure_runtime_dirs
from src.export_manager import build_export_plan, list_encoders, list_muxers
from src.media_probe import probe_and_validate_video
from src.pipeline import JobConfig
from src.runtime import create_runtime
from src.utils import LOGGER, ProgressEvent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True)
    parser.add_argument("--face", action="append", required=True)
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--end", type=float, default=None)
    parser.add_argument("--name", default="user_swap")
    args = parser.parse_args()

    ensure_runtime_dirs()
    video = Path(args.video)
    faces = [Path(p) for p in args.face]
    info = probe_and_validate_video(video)
    LOGGER.info("source duration=%.2f fps=%.2f %sx%s", info.duration or 0, info.avg_fps or 0, info.display_width, info.display_height)

    runtime = create_runtime()
    muxers = [m.name for m in list_muxers()]
    venc = [e.name for e in list_encoders("video")]
    aenc = [e.name for e in list_encoders("audio")]
    plan = build_export_plan(
        source=info,
        container="mp4",
        video_encoder="libx264",
        audio_encoder="aac",
        fps_mode="source",
        custom_fps=None,
        resolution_mode="source",
        custom_size=None,
        lossless=False,
        high_quality=True,
        output_name=args.name,
        available_video=venc,
        available_audio=aenc,
        available_muxers=muxers,
    )
    last = {"n": 0}

    def progress(ev: ProgressEvent) -> None:
        if ev.current == last["n"]:
            return
        last["n"] = ev.current
        if ev.current % 10 == 0 or ev.ratio >= 0.999:
            print(ev.message, flush=True)

    runtime.engine.records.clear()
    runtime.engine.swapper.call_count = 0
    result = runtime.job.run(
        JobConfig(
            source_video=video,
            reference_images=faces,
            plan=plan,
            start_sec=args.start,
            end_sec=args.end,
            watermark=True,
            purpose_note="user uploaded media",
            output_dir=OUTPUTS_DIR,
        ),
        progress=progress,
    )
    report = {
        "ok": result.ok,
        "message": result.message,
        "output": str(result.output_path) if result.output_path else None,
        "frames_total": result.frames_total,
        "frames_swapped": result.frames_swapped,
        "frames_kept": result.frames_kept_original,
        "inferences": result.inference_count,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return 0 if result.ok and result.inference_count > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

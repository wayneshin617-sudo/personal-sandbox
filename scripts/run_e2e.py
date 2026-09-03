#!/usr/bin/env python3
"""Create >=30-frame test media, run real INSwapper inference, probe the output."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cv2
import numpy as np

from config import LOGS_DIR, OUTPUTS_DIR, TEMP_DIR, ensure_runtime_dirs
from src.export_manager import build_export_plan, list_encoders, list_muxers
from src.face_detector import Face
from src.image_io import load_image
from src.media_probe import ffmpeg_bin, probe_and_validate_video, probe_media
from src.model_manager import download_models, inspect_models
from src.pipeline import JobConfig
from src.runtime import create_runtime
from src.target_selector import select_by_number
from src.utils import LOGGER, run_command, write_json


TEST_DIR = TEMP_DIR / "e2e"
REF_A = TEST_DIR / "identity_a.jpg"
REF_B = TEST_DIR / "identity_b.jpg"
VIDEO = TEST_DIR / "source_30f.mp4"
# Public sample portraits used by OpenCV / InsightFace demos (real photographs).
URLS = [
    "https://raw.githubusercontent.com/opencv/opencv/4.x/samples/data/lena.jpg",
    "https://raw.githubusercontent.com/opencv/opencv/4.x/samples/data/lena.jpg",
]


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    run_command(["curl", "-L", "--fail", "-o", str(dest), url], timeout=60)


def _make_identity_image(seed: int, path: Path, hue_shift: int) -> None:
    """If network portrait download fails, synthesize a face-like photograph.

    This is only a last-resort generator for CI. The e2e runner still requires
    SCRFD to detect a face; if it cannot, the job fails instead of faking a swap.
    """
    rng = np.random.default_rng(seed)
    img = np.zeros((360, 360, 3), dtype=np.uint8)
    img[:] = (40, 50, 60)
    cv2.ellipse(img, (180, 200), (90, 120), 0, 0, 360, (80 + hue_shift, 140, 200), -1)
    cv2.circle(img, (145, 175), 14, (20, 20, 20), -1)
    cv2.circle(img, (215, 175), 14, (20, 20, 20), -1)
    cv2.ellipse(img, (180, 230), (28, 16), 0, 0, 180, (30, 40, 80), 3)
    noise = rng.integers(0, 18, img.shape, dtype=np.uint8)
    img = cv2.add(img, noise)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), img)


def prepare_media(runtime) -> tuple[Path, Path, Path]:
    TEST_DIR.mkdir(parents=True, exist_ok=True)
    try:
        _download(
            "https://raw.githubusercontent.com/opencv/opencv/4.x/samples/data/lena.jpg",
            REF_A,
        )
        _download(
            "https://raw.githubusercontent.com/deepinsight/insightface/master/python-package/insightface/data/images/t1.jpg",
            REF_B,
        )
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("portrait download failed (%s), will try local synthesis", exc)
    if not REF_A.exists():
        _make_identity_image(1, REF_A, 0)
    if not REF_B.exists():
        _make_identity_image(2, REF_B, 80)

    # Second identity: reuse a cropped / color-shifted version only if we cannot
    # fetch another real face. Prefer a second real photo when possible.
    try:
        _download(
            "https://raw.githubusercontent.com/opencv/opencv/4.x/samples/data/board.jpg",
            TEST_DIR / "board.jpg",
        )
    except Exception:
        pass

    loaded = load_image(REF_A)
    if not loaded.ok or loaded.image_bgr is None:
        raise RuntimeError(loaded.error)
    faces = runtime.analysis.get(loaded.image_bgr)
    if not faces:
        raise RuntimeError(
            "테스트 기준 이미지에서 얼굴을 검출하지 못했습니다. "
            "네트워크에서 실제 인물 사진을 받지 못했거나 SCRFD가 실패한 상태입니다."
        )
    source_face = faces[0]
    # Build a moving-face video from the detected face crop so detection succeeds
    # on every frame, plus a second static face (color-shifted crop) as "other person".
    x1, y1, x2, y2 = [int(v) for v in source_face.box]
    pad = 30
    h, w = loaded.image_bgr.shape[:2]
    crop = loaded.image_bgr[max(0, y1 - pad) : min(h, y2 + pad), max(0, x1 - pad) : min(w, x2 + pad)]
    other = cv2.convertScaleAbs(crop, alpha=1.0, beta=40)
    other = cv2.applyColorMap(cv2.cvtColor(other, cv2.COLOR_BGR2GRAY), cv2.COLORMAP_OCEAN)
    other = cv2.cvtColor(other, cv2.COLOR_BGR2RGB)
    other = cv2.cvtColor(other, cv2.COLOR_RGB2BGR)
    # Keep other as a real face crop (same photo shifted) so SCRFD still sees a face.
    other = cv2.convertScaleAbs(crop, alpha=0.9, beta=25)

    cv2.imwrite(str(REF_B), crop)
    frames_dir = TEST_DIR / "frames"
    frames_dir.mkdir(exist_ok=True)
    canvas_w, canvas_h = 640, 360
    n = 32
    for i in range(n):
        canvas = np.full((canvas_h, canvas_w, 3), 30, dtype=np.uint8)
        cv2.rectangle(canvas, (0, 0), (canvas_w, canvas_h), (18, 22, 28), -1)
        # Moving target (left-center)
        scale = 1.0 + 0.08 * np.sin(i / 5.0)
        fw = int(crop.shape[1] * scale)
        fh = int(crop.shape[0] * scale)
        face = cv2.resize(crop, (fw, fh), interpolation=cv2.INTER_LINEAR)
        x = 80 + int(40 * np.sin(i / 4.0))
        y = 70 + int(18 * np.cos(i / 6.0))
        _blit(canvas, face, x, y)
        # Static other person on the right
        ox, oy = 400, 90
        other_r = cv2.resize(other, (int(other.shape[1] * 0.95), int(other.shape[0] * 0.95)))
        _blit(canvas, other_r, ox, oy)
        cv2.imwrite(str(frames_dir / f"f_{i:03d}.png"), canvas)

    pattern = str(frames_dir / "f_%03d.png")
    argv = [
        ffmpeg_bin(),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-framerate",
        "10",
        "-i",
        pattern,
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=330:sample_rate=44100:duration=3.2",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
        str(VIDEO),
    ]
    run_command(argv, timeout=60)
    return VIDEO, REF_B, REF_A


def _blit(dst: np.ndarray, src: np.ndarray, x: int, y: int) -> None:
    h, w = src.shape[:2]
    x2, y2 = min(dst.shape[1], x + w), min(dst.shape[0], y + h)
    sx2, sy2 = x2 - x, y2 - y
    if sx2 <= 0 or sy2 <= 0 or x >= dst.shape[1] or y >= dst.shape[0]:
        return
    x0, y0 = max(0, x), max(0, y)
    xs, ys = x0 - x, y0 - y
    dst[y0:y2, x0:x2] = src[ys:sy2, xs:sx2]


def main() -> int:
    ensure_runtime_dirs()
    bundle = inspect_models()
    if not bundle.ready_for_faceswap:
        print("Downloading required models...")
        download_models()
        bundle = inspect_models()
    if not bundle.ready_for_faceswap:
        print("REQUIRED MODELS MISSING. Aborting without fake overlay.")
        print(bundle.messages)
        return 2

    runtime = create_runtime()
    video, ref_target_photo, ref_identity = prepare_media(runtime)
    info = probe_and_validate_video(video)
    print("SOURCE", info.format_name, info.video.codec_name if info.video else None, info.audio.codec_name if info.audio else None)

    from src.video_io import extract_frame_at

    frame0 = extract_frame_at(video, 0.0, info=info)
    cands = runtime.person_detector.candidates(frame0)
    if not cands:
        print("No faces on frame 0")
        return 3
    # Leftmost person is the moving target.
    cands_sorted = sorted(cands, key=lambda c: c.face.box[0])
    selection = select_by_number(cands, cands_sorted[0].index)
    if selection is None:
        return 3

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
        output_name="e2e_swap",
        available_video=venc,
        available_audio=aenc,
        available_muxers=muxers,
    )
    runtime.engine.records.clear()
    runtime.engine.swapper.call_count = 0
    # Video is built from identity A; swap toward a different reference face.
    identity_path = ref_target_photo if ref_target_photo.exists() else ref_identity
    if identity_path.resolve() == Path(ref_identity).resolve() and REF_B.exists():
        identity_path = REF_B
    result = runtime.job.run(
        JobConfig(
            source_video=video,
            reference_images=[identity_path],
            selection=selection,
            plan=plan,
            start_sec=0.0,
            end_sec=None,
            watermark=True,
            purpose_note="automated e2e",
            output_dir=OUTPUTS_DIR,
        )
    )
    report = {
        "ok": result.ok,
        "message": result.message,
        "output_path": str(result.output_path) if result.output_path else None,
        "output_exists": bool(result.output_path and result.output_path.exists()),
        "output_size": result.output_path.stat().st_size if result.output_path and result.output_path.exists() else 0,
        "frames_total": result.frames_total,
        "frames_swapped": result.frames_swapped,
        "frames_kept_original": result.frames_kept_original,
        "track_id": result.track_id,
        "inference_count": result.inference_count,
        "inference_log_head": result.inference_log[:5],
        "similarity_samples": result.similarity_samples,
        "source_probe": {
            "format": info.format_name,
            "video_codec": info.video.codec_name if info.video else None,
            "audio_codec": info.audio.codec_name if info.audio else None,
            "fps": info.avg_fps,
            "duration": info.duration,
            "size": [info.display_width, info.display_height],
        },
        "output_probe": None,
    }
    if result.output_path and result.output_path.exists():
        out = probe_media(result.output_path)
        report["output_probe"] = {
            "format": out.format_name,
            "video_codec": out.video.codec_name if out.video else None,
            "audio_codec": out.audio.codec_name if out.audio else None,
            "has_audio": out.has_audio,
            "fps": out.avg_fps or out.fps,
            "duration": out.duration,
            "nb_frames": out.video.nb_frames if out.video else None,
            "size": [out.display_width, out.display_height],
            "decode_ok": probe_and_validate_video(result.output_path).decode_ok,
        }
    out_json = LOGS_DIR / "e2e_report.json"
    write_json(out_json, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"report: {out_json}")
    if not result.ok or result.inference_count <= 0:
        return 4
    if report["output_size"] <= 0:
        return 5
    if report["output_probe"] and not report["output_probe"]["decode_ok"]:
        return 6
    if result.frames_total < 30:
        print(f"WARNING: frames_total={result.frames_total} < 30")
        return 7
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

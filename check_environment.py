#!/usr/bin/env python3
"""Inspect runtime: Python, OS, GPU, CUDA, ONNX Runtime, FFmpeg, packages, models."""

from __future__ import annotations

import importlib.metadata
import json
import platform
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _pkg_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _gpu_info() -> dict:
    info = {
        "nvidia_smi": shutil.which("nvidia-smi"),
        "gpu_name": None,
        "cuda_available": False,
        "vram_gb": None,
        "nvidia_smi_error": None,
    }
    if not info["nvidia_smi"]:
        return info
    from src.utils import run_command

    try:
        proc = run_command(
            [info["nvidia_smi"], "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            timeout=15,
        )
        line = (proc.stdout or "").strip().splitlines()[0]
        name, mem = [p.strip() for p in line.split(",", 1)]
        info["gpu_name"] = name
        info["vram_gb"] = float(mem) / 1024.0
        info["cuda_available"] = True
    except Exception as exc:  # noqa: BLE001
        info["nvidia_smi_error"] = str(exc)
    return info


def _onnx_providers() -> dict:
    data = {"installed": False, "version": None, "available_providers": [], "selected_provider": None}
    try:
        import onnxruntime as ort

        data["installed"] = True
        data["version"] = ort.__version__
        data["available_providers"] = list(ort.get_available_providers())
        prefs = ["CUDAExecutionProvider", "DmlExecutionProvider", "CPUExecutionProvider"]
        data["selected_provider"] = next((p for p in prefs if p in data["available_providers"]), "CPUExecutionProvider")
    except Exception as exc:  # noqa: BLE001
        data["error"] = str(exc)
    return data


def _ffmpeg_caps() -> dict:
    from src.export_manager import list_encoders, list_muxers
    from src.media_probe import ProbeError, ffmpeg_bin, ffprobe_bin
    from src.utils import run_command

    data: dict = {"ffmpeg": None, "ffprobe": None, "ok": False}
    try:
        data["ffmpeg"] = ffmpeg_bin()
        ver = run_command([data["ffmpeg"], "-version"], timeout=10)
        data["ffmpeg_version"] = (ver.stdout or "").splitlines()[0] if ver.stdout else ""
    except ProbeError as exc:
        data["ffmpeg_error"] = str(exc)
    try:
        data["ffprobe"] = ffprobe_bin()
        ver = run_command([data["ffprobe"], "-version"], timeout=10)
        data["ffprobe_version"] = (ver.stdout or "").splitlines()[0] if ver.stdout else ""
    except ProbeError as exc:
        data["ffprobe_error"] = str(exc)
    data["ok"] = bool(data.get("ffmpeg") and data.get("ffprobe"))
    if data["ok"]:
        muxers = list_muxers()
        encoders = list_encoders()
        data["muxers"] = [m.name for m in muxers]
        data["video_encoders"] = [e.name for e in encoders if e.kind == "video"]
        data["audio_encoders"] = [e.name for e in encoders if e.kind == "audio"]
        data["sample_muxers"] = data["muxers"][:20]
        data["sample_video_encoders"] = [n for n in data["video_encoders"] if n in {
            "libx264", "libx265", "libvpx-vp9", "libaom-av1", "mpeg4", "gif", "libwebp", "h264_nvenc"
        }]
        data["sample_audio_encoders"] = [n for n in data["audio_encoders"] if n in {
            "aac", "libmp3lame", "libopus", "libvorbis", "pcm_s16le", "flac"
        }]
    return data


def collect_environment() -> dict:
    gpu = _gpu_info()
    onnx = _onnx_providers()
    ffmpeg = _ffmpeg_caps()
    from src.model_manager import inspect_models
    from src.pose_processor import person_transform_status
    from src.segmentation import capability as seg_capability

    models = inspect_models()
    advanced = person_transform_status(bool(gpu["cuda_available"]), gpu.get("gpu_name"), gpu.get("vram_gb"))
    packages = {
        name: _pkg_version(name)
        for name in [
            "numpy",
            "opencv-python-headless",
            "onnx",
            "onnxruntime",
            "onnxruntime-gpu",
            "pillow",
            "streamlit",
            "scipy",
            "scikit-image",
        ]
    }
    env = {
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
        "os": f"{platform.system()} {platform.release()}",
        "platform": platform.platform(),
        "machine": platform.machine(),
        "gpu": gpu,
        "onnxruntime": onnx,
        "ffmpeg": ffmpeg,
        "packages": packages,
        "models": {
            "ready_for_faceswap": models.ready_for_faceswap,
            "messages": models.messages,
            "files": [
                {
                    "name": item.name,
                    "path": str(item.path),
                    "present": item.present,
                    "size_bytes": item.size_bytes,
                    "required": item.required,
                    "license": item.license_name,
                    "source": item.source,
                    "error": item.error,
                }
                for item in (
                    models.detector,
                    models.recognizer,
                    models.swapper,
                    models.landmark,
                    models.restorer,
                )
            ],
        },
        "selected_provider": onnx.get("selected_provider"),
        "face_swap_available": bool(models.ready_for_faceswap and ffmpeg.get("ok")),
        "person_transform": {
            "available": advanced.available,
            "reason": advanced.reason,
            "required_vram_gb": advanced.required_vram_gb,
            "required_models": advanced.required_models,
            "required_packages": advanced.required_packages,
        },
        "segmentation": {
            "face_mask_available": seg_capability().face_mask_available,
            "person_mask_available": seg_capability().person_mask_available,
            "reason": seg_capability().reason,
        },
    }
    return env


def print_environment(env: dict | None = None) -> int:
    env = env or collect_environment()
    print(f"Python          : {env['python']} ({env['python_executable']})")
    print(f"OS              : {env['os']} / {env['machine']}")
    print(f"GPU             : {env['gpu'].get('gpu_name') or 'none'}")
    print(f"CUDA            : {env['gpu'].get('cuda_available')}")
    print(f"ONNX Runtime    : {env['onnxruntime']}")
    print(f"Selected provider: {env.get('selected_provider')}")
    ff = env["ffmpeg"]
    print(f"FFmpeg          : {ff.get('ffmpeg')} {ff.get('ffmpeg_version', '')}")
    print(f"FFprobe         : {ff.get('ffprobe')} {ff.get('ffprobe_version', '')}")
    if ff.get("ok"):
        print(f"Muxers (sample) : {', '.join(ff.get('sample_muxers', []))}")
        print(f"V encoders      : {', '.join(ff.get('sample_video_encoders', []))}")
        print(f"A encoders      : {', '.join(ff.get('sample_audio_encoders', []))}")
    else:
        print(f"FFmpeg error    : {ff.get('ffmpeg_error') or ff.get('ffprobe_error')}")
    print("Packages:")
    for name, ver in env["packages"].items():
        print(f"  {name}: {ver or 'not installed'}")
    print("Models:")
    for item in env["models"]["files"]:
        mark = "OK" if item["present"] else "MISSING"
        print(f"  [{mark}] {item['name']} ({item['size_bytes']} bytes) {item['path']}")
    for msg in env["models"]["messages"]:
        print(f"  ! {msg}")
    print(f"Face swap ready : {env['face_swap_available']}")
    print(f"Person transform: available={env['person_transform']['available']}")
    print(f"  reason: {env['person_transform']['reason']}")
    return 0 if env["ffmpeg"].get("ok") else 2


def main() -> int:
    env = collect_environment()
    code = print_environment(env)
    dump = ROOT / "logs" / "environment.json"
    dump.parent.mkdir(parents=True, exist_ok=True)
    dump.write_text(json.dumps(env, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {dump}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())

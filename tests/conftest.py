from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.media_probe import ffmpeg_bin
from src.utils import run_command


def make_test_video(
    path: Path,
    frames: int = 16,
    fps: int = 12,
    width: int = 320,
    height: int = 240,
    audio: bool = True,
    color: str = "blue",
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    argv = [
        ffmpeg_bin(),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"color=c={color}:s={width}x{height}:d={frames / fps:.4f}:r={fps}",
    ]
    if audio:
        argv += [
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:sample_rate=44100:duration={frames / fps:.4f}",
            "-c:a",
            "aac",
            "-shortest",
        ]
    else:
        argv += ["-an"]
    argv += ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)]
    run_command(argv, timeout=60)
    return path


@pytest.fixture
def silent_clip(tmp_path: Path) -> Path:
    return make_test_video(tmp_path / "silent.mp4", frames=12, fps=10, audio=False, color="green")


@pytest.fixture
def audio_clip(tmp_path: Path) -> Path:
    return make_test_video(tmp_path / "with_audio.mp4", frames=20, fps=10, audio=True, color="red")

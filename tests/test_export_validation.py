from __future__ import annotations

from pathlib import Path

from src.export_manager import build_export_plan, list_encoders, list_muxers
from src.media_probe import probe_and_validate_video
from src.validators import encoder_container_compatible, validate_output_media
from tests.conftest import make_test_video


def test_validate_output_rejects_empty(tmp_path: Path) -> None:
    empty = tmp_path / "empty.mp4"
    empty.write_bytes(b"")
    result = validate_output_media(empty)
    assert not result.ok


def test_validate_output_accepts_real_encode(tmp_path: Path) -> None:
    video = make_test_video(tmp_path / "ok.mp4", frames=10, fps=10, audio=True)
    src = probe_and_validate_video(video)
    result = validate_output_media(video, source=src, expect_audio=True, min_frames=5)
    assert result.ok, result.message


def test_runtime_muxers_include_mp4() -> None:
    names = {m.name for m in list_muxers()}
    assert "mp4" in names
    video_enc = {e.name for e in list_encoders("video")}
    assert "libx264" in video_enc


def test_gif_rejects_audio_combination() -> None:
    ok, msg = encoder_container_compatible("gif", "gif", "aac")
    assert not ok
    assert "오디오" in msg


def test_auto_plan_defaults_to_usable_combo(tmp_path: Path) -> None:
    video = make_test_video(tmp_path / "src.mp4", frames=8, fps=8, audio=True)
    info = probe_and_validate_video(video)
    muxers = [m.name for m in list_muxers()]
    venc = [e.name for e in list_encoders("video")]
    aenc = [e.name for e in list_encoders("audio")]
    plan = build_export_plan(
        source=info,
        container="auto",
        video_encoder="auto",
        audio_encoder="auto",
        fps_mode="source",
        custom_fps=None,
        resolution_mode="source",
        custom_size=None,
        lossless=False,
        high_quality=True,
        output_name="out",
        available_video=venc,
        available_audio=aenc,
        available_muxers=muxers,
    )
    assert plan.container
    assert plan.video_encoder
    assert plan.fps > 0

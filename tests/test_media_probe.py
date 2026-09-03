from __future__ import annotations

from pathlib import Path

from src.media_probe import probe_and_validate_video, probe_media
from src.validators import validate_video_input
from tests.conftest import make_test_video


def test_probe_reads_container_codec_fps(tmp_path: Path) -> None:
    video = make_test_video(tmp_path / "clip.mp4", frames=16, fps=12, audio=True)
    info = probe_and_validate_video(video)
    assert info.decode_ok
    assert info.video is not None
    assert info.video.codec_name in {"h264", "libx264", "mpeg4"}
    assert "mp4" in (info.format_name or "")
    assert info.display_width == 320
    assert info.display_height == 240
    assert info.avg_fps and abs(info.avg_fps - 12) < 0.2
    assert info.has_audio
    assert info.audio is not None
    assert info.audio.codec_name in {"aac", "mp3"}


def test_extensionless_file_is_accepted_when_decodable(tmp_path: Path) -> None:
    src = make_test_video(tmp_path / "named.mp4", frames=8, fps=10, audio=False)
    dest = tmp_path / "no_suffix"
    dest.write_bytes(src.read_bytes())
    result = validate_video_input(dest)
    assert result.ok, result.message
    info = probe_media(dest)
    assert info.video is not None


def test_random_bytes_are_rejected(tmp_path: Path) -> None:
    junk = tmp_path / "junk.mp4"
    junk.write_bytes(b"this is not a video")
    result = validate_video_input(junk)
    assert not result.ok

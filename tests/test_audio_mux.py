from __future__ import annotations

from pathlib import Path

from src.audio_muxer import mux_audio
from src.media_probe import probe_media
from src.video_io import VideoFrameReader, VideoFrameWriter
from tests.conftest import make_test_video


def test_mux_copies_audio_and_keeps_video(tmp_path: Path) -> None:
    src = make_test_video(tmp_path / "src.mp4", frames=15, fps=10, audio=True)
    silent = tmp_path / "silent.mp4"
    with VideoFrameReader(src) as reader, VideoFrameWriter(
        silent, reader.width, reader.height, reader.fps, video_encoder="libx264"
    ) as writer:
        for packet in reader.frames():
            writer.write(packet.image_bgr)
    out = tmp_path / "muxed.mp4"
    mux_audio(silent, src, out, audio_encoder="copy")
    info = probe_media(out)
    assert info.video is not None
    assert info.has_audio
    assert info.audio is not None
    assert abs((info.duration or 0) - 1.5) < 0.4


def test_mux_without_source_audio(tmp_path: Path, silent_clip: Path) -> None:
    out = tmp_path / "noaudio.mp4"
    mux_audio(silent_clip, silent_clip, out, audio_encoder="copy")
    info = probe_media(out)
    assert info.video is not None
    assert not info.has_audio

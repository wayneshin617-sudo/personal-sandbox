from __future__ import annotations

from pathlib import Path

from src.video_io import VideoFrameReader, VideoFrameWriter, count_decoded_frames
from tests.conftest import make_test_video


def test_streaming_roundtrip_frame_count(tmp_path: Path) -> None:
    src = make_test_video(tmp_path / "src.mp4", frames=18, fps=9, width=160, height=120, audio=False)
    decoded = 0
    out = tmp_path / "out.mp4"
    with VideoFrameReader(src) as reader, VideoFrameWriter(
        out, reader.width, reader.height, reader.fps, video_encoder="libx264"
    ) as writer:
        for packet in reader.frames():
            assert packet.image_bgr.shape == (120, 160, 3)
            writer.write(packet.image_bgr)
            decoded += 1
    assert decoded == 18
    assert out.exists() and out.stat().st_size > 0
    assert count_decoded_frames(out) == 18


def test_reader_does_not_require_matching_extension(tmp_path: Path) -> None:
    src = make_test_video(tmp_path / "src.mp4", frames=6, fps=8, audio=False)
    renamed = tmp_path / "video_file"
    renamed.write_bytes(src.read_bytes())
    with VideoFrameReader(renamed) as reader:
        frames = list(reader.frames())
    assert len(frames) == 6

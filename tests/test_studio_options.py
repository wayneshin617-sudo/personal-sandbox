from __future__ import annotations

from types import SimpleNamespace

from src.studio_options import duration_window, output_size


def test_output_size_keeps_source_when_original() -> None:
    info = SimpleNamespace(display_width=1920, display_height=1080)
    mode, size = output_size(info, "원본", "원본")
    assert mode == "source"
    assert size is None


def test_output_size_portrait_1080p() -> None:
    info = SimpleNamespace(display_width=1920, display_height=1080)
    mode, size = output_size(info, "9:16", "1080p")
    assert mode == "custom"
    assert size == (1080, 1920)


def test_output_size_square_720p() -> None:
    info = SimpleNamespace(display_width=1280, display_height=720)
    mode, size = output_size(info, "1:1", "720p")
    assert mode == "custom"
    assert size == (720, 720)


def test_duration_window_full_clip() -> None:
    assert duration_window("전체", 12.0, 3.0) == (0.0, None)


def test_duration_window_five_seconds_from_scene() -> None:
    start, end = duration_window("5초", 20.0, 2.0)
    assert start == 2.0
    assert end == 7.0

from __future__ import annotations

from pathlib import Path

from src.chunk_upload import assemble_parts
from src.preview_click import fit_preview_size, map_click_to_frame


def test_map_click_scales_from_displayed_quarter() -> None:
    # 1920x1080 frame shown in a 480x270 box (1/4). Click at displayed (240, 135)
    # must map to the center of the original frame, not stay in the corner.
    x, y = map_click_to_frame({"x": 240, "y": 135, "width": 480, "height": 270}, (1920, 1080))
    assert x == 960
    assert y == 540


def test_map_click_clamps_to_frame() -> None:
    x, y = map_click_to_frame({"x": 5000, "y": -3, "width": 100, "height": 100}, (200, 100))
    assert x == 199
    assert y == 0


def test_fit_preview_downscales_wide_frame() -> None:
    w, h = fit_preview_size(3840, 2160, 1280)
    assert w == 1280
    assert h == 720


def test_assemble_parts_writes_in_order(tmp_path: Path) -> None:
    part_dir = tmp_path / "parts"
    part_dir.mkdir()
    (part_dir / "000000.part").write_bytes(b"AAA")
    (part_dir / "000001.part").write_bytes(b"BBB")
    dest = tmp_path / "out.bin"
    assemble_parts(part_dir, dest)
    assert dest.read_bytes() == b"AAABBB"

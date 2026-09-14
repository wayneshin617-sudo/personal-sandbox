"""Map a displayed preview click back onto the original video frame."""

from __future__ import annotations


def map_click_to_frame(click: dict, frame_size: tuple[int, int]) -> tuple[int, int]:
    orig_w, orig_h = int(frame_size[0]), int(frame_size[1])
    disp_w = float(click.get("width") or orig_w or 1)
    disp_h = float(click.get("height") or orig_h or 1)
    x = int(round(float(click["x"]) * orig_w / max(disp_w, 1.0)))
    y = int(round(float(click["y"]) * orig_h / max(disp_h, 1.0)))
    x = max(0, min(max(orig_w - 1, 0), x))
    y = max(0, min(max(orig_h - 1, 0), y))
    return x, y


def fit_preview_size(width: int, height: int, max_width: int = 1280) -> tuple[int, int]:
    if width <= 0 or height <= 0:
        return max_width, int(max_width * 9 / 16)
    if width <= max_width:
        return int(width), int(height)
    scale = max_width / float(width)
    return max_width, max(1, int(round(height * scale)))

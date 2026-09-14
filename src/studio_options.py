"""Consumer studio output options: duration clip and aspect/resolution mapping."""

from __future__ import annotations


def output_size(info, aspect: str, resolution: str) -> tuple[str, tuple[int, int] | None]:
    src_w = int(getattr(info, "display_width", None) or 1280)
    src_h = int(getattr(info, "display_height", None) or 720)
    if aspect == "원본" and resolution == "원본":
        return "source", None

    if aspect == "16:9":
        if resolution == "1080p":
            w, h = 1920, 1080
        elif resolution == "720p":
            w, h = 1280, 720
        else:
            h = src_h
            w = int(h * 16 / 9)
    elif aspect == "9:16":
        if resolution == "1080p":
            w, h = 1080, 1920
        elif resolution == "720p":
            w, h = 720, 1280
        else:
            w = src_w
            h = int(w * 16 / 9)
    elif aspect == "1:1":
        side = {"1080p": 1080, "720p": 720}.get(resolution, min(src_w, src_h))
        w = h = side
    else:
        long_edge = {"720p": 1280, "1080p": 1920}.get(resolution)
        if long_edge is None:
            return "source", None
        if src_w >= src_h:
            w, h = long_edge, int(long_edge * src_h / src_w)
        else:
            h, w = long_edge, int(long_edge * src_w / src_h)
    w -= w % 2
    h -= h % 2
    return "custom", (max(64, w), max(64, h))


def duration_window(choice: str, media_duration: float, start_hint: float) -> tuple[float, float | None]:
    if choice == "전체" or not media_duration:
        return 0.0, None
    seconds = {"5초": 5.0, "10초": 10.0, "15초": 15.0}.get(choice, media_duration)
    start = max(0.0, min(start_hint, max(0.0, media_duration - 0.2)))
    end = min(media_duration, start + seconds)
    if end <= start:
        return 0.0, None
    return start, end

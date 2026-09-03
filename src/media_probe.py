"""Inspect media with FFprobe. Extension is never used as the source of truth."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.utils import CommandError, LOGGER, parse_fraction, run_command, which


class ProbeError(RuntimeError):
    pass


@dataclass
class StreamInfo:
    index: int
    codec_type: str
    codec_name: str | None = None
    codec_long_name: str | None = None
    profile: str | None = None
    width: int | None = None
    height: int | None = None
    pix_fmt: str | None = None
    sample_aspect_ratio: str | None = None
    avg_frame_rate: str | None = None
    r_frame_rate: str | None = None
    time_base: str | None = None
    duration: float | None = None
    nb_frames: int | None = None
    bit_rate: int | None = None
    sample_rate: int | None = None
    channels: int | None = None
    channel_layout: str | None = None
    rotation: float | None = None
    tags: dict[str, Any] = field(default_factory=dict)


@dataclass
class MediaInfo:
    path: str
    exists: bool
    size_bytes: int
    format_name: str | None = None
    format_long_name: str | None = None
    duration: float | None = None
    bit_rate: int | None = None
    probe_score: int | None = None
    start_time: float | None = None
    streams: list[StreamInfo] = field(default_factory=list)
    video: StreamInfo | None = None
    audio: StreamInfo | None = None
    fps: float | None = None
    avg_fps: float | None = None
    display_width: int | None = None
    display_height: int | None = None
    rotation: float = 0.0
    has_audio: bool = False
    decode_ok: bool = False
    decode_error: str | None = None
    warnings: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data


def ffprobe_bin() -> str:
    path = which("ffprobe")
    if not path:
        raise ProbeError(
            "FFprobe를 찾을 수 없습니다. FFmpeg 전체 패키지를 PATH에 설치하세요. "
            "Windows: https://www.gyan.dev/ffmpeg/builds/ 또는 winget install ffmpeg"
        )
    return path


def ffmpeg_bin() -> str:
    path = which("ffmpeg")
    if not path:
        raise ProbeError(
            "FFmpeg를 찾을 수 없습니다. PATH에 ffmpeg를 설치하세요. "
            "Windows: https://www.gyan.dev/ffmpeg/builds/ 또는 winget install ffmpeg"
        )
    return path


def _to_int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _rotation_from_stream(stream: dict[str, Any]) -> float:
    tags = stream.get("tags") or {}
    if "rotate" in tags:
        rot = _to_float(tags.get("rotate"))
        if rot is not None:
            return rot
    for side in stream.get("side_data_list") or []:
        if "rotation" in side:
            rot = _to_float(side.get("rotation"))
            if rot is not None:
                return rot
        matrix = side.get("displaymatrix")
        if matrix and "rotation" in str(side).lower():
            rot = _to_float(side.get("rotation"))
            if rot is not None:
                return rot
    return 0.0


def _parse_stream(raw: dict[str, Any]) -> StreamInfo:
    return StreamInfo(
        index=int(raw.get("index", 0)),
        codec_type=str(raw.get("codec_type") or "unknown"),
        codec_name=raw.get("codec_name"),
        codec_long_name=raw.get("codec_long_name"),
        profile=raw.get("profile"),
        width=_to_int(raw.get("width")),
        height=_to_int(raw.get("height")),
        pix_fmt=raw.get("pix_fmt"),
        sample_aspect_ratio=raw.get("sample_aspect_ratio"),
        avg_frame_rate=raw.get("avg_frame_rate"),
        r_frame_rate=raw.get("r_frame_rate"),
        time_base=raw.get("time_base"),
        duration=_to_float(raw.get("duration")),
        nb_frames=_to_int(raw.get("nb_frames")),
        bit_rate=_to_int(raw.get("bit_rate")),
        sample_rate=_to_int(raw.get("sample_rate")),
        channels=_to_int(raw.get("channels")),
        channel_layout=raw.get("channel_layout"),
        rotation=_rotation_from_stream(raw),
        tags=raw.get("tags") or {},
    )


def probe_media(path: str | Path) -> MediaInfo:
    path = Path(path)
    info = MediaInfo(
        path=str(path),
        exists=path.exists(),
        size_bytes=path.stat().st_size if path.exists() else 0,
    )
    if not path.exists():
        info.decode_error = f"파일이 존재하지 않습니다: {path}"
        return info
    if info.size_bytes <= 0:
        info.decode_error = "파일 크기가 0입니다."
        return info

    argv = [
        ffprobe_bin(),
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        "-show_error",
        str(path),
    ]
    try:
        proc = run_command(argv, timeout=60)
        raw = json.loads(proc.stdout or "{}")
    except (CommandError, json.JSONDecodeError) as exc:
        info.decode_error = f"FFprobe가 이 파일을 미디어로 해석하지 못했습니다: {exc}"
        LOGGER.warning("%s", info.decode_error)
        return info

    info.raw = raw
    fmt = raw.get("format") or {}
    info.format_name = fmt.get("format_name")
    info.format_long_name = fmt.get("format_long_name")
    info.duration = _to_float(fmt.get("duration"))
    info.bit_rate = _to_int(fmt.get("bit_rate"))
    info.probe_score = _to_int(fmt.get("probe_score"))
    info.start_time = _to_float(fmt.get("start_time"))

    streams = [_parse_stream(s) for s in raw.get("streams") or []]
    info.streams = streams
    videos = [s for s in streams if s.codec_type == "video"]
    audios = [s for s in streams if s.codec_type == "audio"]
    info.video = videos[0] if videos else None
    info.audio = audios[0] if audios else None
    info.has_audio = info.audio is not None
    if len(videos) > 1:
        info.warnings.append(f"비디오 스트림이 {len(videos)}개입니다. 첫 번째 스트림을 사용합니다.")

    if info.video:
        info.avg_fps = parse_fraction(info.video.avg_frame_rate, 0.0) or None
        info.fps = parse_fraction(info.video.r_frame_rate, 0.0) or info.avg_fps
        info.rotation = float(info.video.rotation or 0.0)
        width = info.video.width or 0
        height = info.video.height or 0
        swapped = abs(info.rotation) % 180 == 90
        info.display_width = height if swapped else width
        info.display_height = width if swapped else height
        if info.duration is None:
            info.duration = info.video.duration
        if (info.video.nb_frames is None or info.video.nb_frames <= 0) and info.duration and info.avg_fps:
            info.video.nb_frames = int(round(info.duration * info.avg_fps))
            info.warnings.append("컨테이너에 nb_frames가 없어 duration * avg_fps로 추정했습니다.")
        if info.avg_fps and info.fps and abs(info.avg_fps - info.fps) > 0.25:
            info.warnings.append(
                f"가변 프레임률로 보입니다 (r={info.fps:.3f}, avg={info.avg_fps:.3f})."
            )
    else:
        info.decode_error = "비디오 스트림이 없습니다. 이 파일은 영상 입력으로 사용할 수 없습니다."
    return info


def decode_smoke_test(path: str | Path, frames: int = 2) -> tuple[bool, str | None]:
    """Decode a few frames with FFmpeg. Success means the file is a usable video."""
    path = Path(path)
    argv = [
        ffmpeg_bin(),
        "-v",
        "error",
        "-i",
        str(path),
        "-map",
        "0:v:0",
        "-frames:v",
        str(max(1, frames)),
        "-f",
        "null",
        "-",
    ]
    try:
        run_command(argv, timeout=90)
        return True, None
    except CommandError as exc:
        return False, (exc.stderr or str(exc))[-1500:]


def probe_and_validate_video(path: str | Path) -> MediaInfo:
    info = probe_media(path)
    if info.decode_error:
        return info
    ok, err = decode_smoke_test(path)
    info.decode_ok = ok
    if not ok:
        info.decode_error = (
            "파일 헤더는 미디어처럼 보이지만 실제 디코딩에 실패했습니다. "
            f"원인: {err}"
        )
    return info


def summarize_media(info: MediaInfo) -> str:
    if info.decode_error and not info.video:
        return info.decode_error
    parts = [
        f"container={info.format_name or 'unknown'}",
        f"size={info.size_bytes}B",
    ]
    if info.video:
        parts.append(
            f"video={info.video.codec_name} {info.display_width}x{info.display_height} "
            f"fps={info.avg_fps or info.fps} pix={info.video.pix_fmt}"
        )
    if info.audio:
        parts.append(
            f"audio={info.audio.codec_name} {info.audio.sample_rate}Hz "
            f"ch={info.audio.channels}"
        )
    else:
        parts.append("audio=none")
    if info.duration is not None:
        parts.append(f"duration={info.duration:.3f}s")
    if info.rotation:
        parts.append(f"rotation={info.rotation}")
    if info.decode_error:
        parts.append(f"error={info.decode_error}")
    return " | ".join(parts)

"""Discover runtime FFmpeg muxers/encoders and build real encode jobs."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from src.audio_muxer import mux_audio
from src.media_probe import MediaInfo, ffmpeg_bin
from src.utils import LOGGER, run_command
from src.validators import encoder_container_compatible


@dataclass
class CodecOption:
    name: str
    description: str
    kind: str  # muxer | video | audio


@dataclass
class ExportPlan:
    container: str
    video_encoder: str
    audio_encoder: str
    fps: float
    width: int
    height: int
    lossless: bool
    high_quality: bool
    drop_audio: bool
    extra_args: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    output_name: str = "result"


_MUXER_RE = re.compile(r"^ ([D ])([E ]) (\S+)\s+(.*)$")
_ENCODER_RE = re.compile(r"^ ([VAS])([F.])([S.])([X.])([B.])([D.]) (\S+)\s+(.*)$")


def _ffmpeg_list(kind: str) -> str:
    proc = run_command([ffmpeg_bin(), "-hide_banner", f"-{kind}"], check=False, timeout=20)
    return (proc.stdout or "") + "\n" + (proc.stderr or "")


def list_muxers() -> list[CodecOption]:
    items: list[CodecOption] = []
    for line in _ffmpeg_list("muxers").splitlines():
        match = _MUXER_RE.match(line)
        if not match or match.group(2) != "E":
            continue
        name, desc = match.group(3), match.group(4)
        items.append(CodecOption(name=name, description=desc.strip(), kind="muxer"))
    seen: set[str] = set()
    unique: list[CodecOption] = []
    for item in items:
        if item.name in seen:
            continue
        seen.add(item.name)
        unique.append(item)
    return unique


def list_encoders(kind: str | None = None) -> list[CodecOption]:
    items: list[CodecOption] = []
    for line in _ffmpeg_list("encoders").splitlines():
        match = _ENCODER_RE.match(line)
        if not match:
            continue
        flags = "".join(match.group(i) for i in range(1, 7))
        name, desc = match.group(7), match.group(8)
        if kind == "video" and not flags.startswith("V"):
            continue
        if kind == "audio" and not flags.startswith("A"):
            continue
        if name.startswith("=") or name in {"Audio", "Video", "Subtitle"}:
            continue
        codec_kind = "video" if flags.startswith("V") else "audio" if flags.startswith("A") else "other"
        items.append(CodecOption(name=name, description=desc.strip(), kind=codec_kind))
    return items


def preferred_muxers(all_muxers: Iterable[CodecOption]) -> list[CodecOption]:
    names = {m.name: m for m in all_muxers}
    order = ["mp4", "mov", "matroska", "mkv", "webm", "avi", "gif", "webp"]
    picked = [names[n] for n in order if n in names]
    extras = [m for m in all_muxers if m.name not in {p.name for p in picked}]
    return picked + extras


def preferred_video_encoders(all_enc: Iterable[CodecOption]) -> list[CodecOption]:
    names = {e.name: e for e in all_enc if e.kind == "video"}
    order = [
        "libx264",
        "libx265",
        "h264_nvenc",
        "hevc_nvenc",
        "libvpx-vp9",
        "libaom-av1",
        "libsvtav1",
        "mpeg4",
        "gif",
        "libwebp",
        "libwebp_anim",
        "prores_ks",
        "ffv1",
    ]
    picked = [names[n] for n in order if n in names]
    extras = [e for e in names.values() if e.name not in {p.name for p in picked}]
    return picked + extras


def preferred_audio_encoders(all_enc: Iterable[CodecOption]) -> list[CodecOption]:
    names = {e.name: e for e in all_enc if e.kind == "audio"}
    order = ["aac", "libmp3lame", "libopus", "libvorbis", "pcm_s16le", "flac"]
    picked = [names[n] for n in order if n in names]
    extras = [e for e in names.values() if e.name not in {p.name for p in picked}]
    return picked + extras


def suggest_for_container(container: str, video_encoders: list[str], audio_encoders: list[str]) -> tuple[str, str]:
    container = container.lower().lstrip(".")
    video_pref = {
        "mp4": ["libx264", "libx265", "libsvtav1", "mpeg4"],
        "mov": ["libx264", "libx265", "prores_ks"],
        "mkv": ["libx264", "libx265", "libvpx-vp9", "ffv1"],
        "webm": ["libvpx-vp9", "libaom-av1", "libsvtav1"],
        "avi": ["mpeg4", "libxvid", "libx264"],
        "gif": ["gif"],
        "webp": ["libwebp_anim", "libwebp"],
    }.get(container, ["libx264"])
    audio_pref = {
        "mp4": ["aac", "libmp3lame"],
        "mov": ["aac"],
        "mkv": ["aac", "libopus", "flac"],
        "webm": ["libopus", "libvorbis"],
        "avi": ["libmp3lame", "pcm_s16le"],
        "gif": ["none"],
        "webp": ["none"],
    }.get(container, ["aac"])
    video = next((v for v in video_pref if v in video_encoders), video_encoders[0] if video_encoders else "libx264")
    audio = next((a for a in audio_pref if a in audio_encoders or a == "none"), "none")
    return video, audio


def build_export_plan(
    *,
    source: MediaInfo,
    container: str,
    video_encoder: str,
    audio_encoder: str,
    fps_mode: str,
    custom_fps: float | None,
    resolution_mode: str,
    custom_size: tuple[int, int] | None,
    lossless: bool,
    high_quality: bool,
    output_name: str,
    available_video: list[str],
    available_audio: list[str],
    available_muxers: list[str],
) -> ExportPlan:
    container = (container or "auto").lower().lstrip(".")
    warnings: list[str] = []
    if container in {"auto", ""}:
        src_fmt = (source.format_name or "mp4").split(",")[0]
        container = src_fmt if src_fmt in available_muxers else "mp4"
        if src_fmt not in available_muxers:
            warnings.append(f"원본 컨테이너 {src_fmt} muxer를 쓸 수 없어 mp4로 대체합니다.")

    if video_encoder in {"auto", "", None}:
        video_encoder, _ = suggest_for_container(container, available_video, available_audio)
        warnings.append(f"비디오 인코더 자동 선택: {video_encoder}")
    if audio_encoder in {"auto", "", None}:
        _, audio_encoder = suggest_for_container(container, available_video, available_audio)

    drop_audio = container in {"gif", "webp", "apng"} or audio_encoder in {"none", "an"}
    if drop_audio:
        audio_encoder = "none"
        warnings.append("선택한 출력은 오디오를 포함하지 않습니다.")

    ok, reason = encoder_container_compatible(container, video_encoder, None if drop_audio else audio_encoder)
    if not ok:
        alt_v, alt_a = suggest_for_container(container, available_video, available_audio)
        warnings.append(f"{reason} 대체 제안: video={alt_v}, audio={alt_a}")
        video_encoder, audio_encoder = alt_v, alt_a
        drop_audio = audio_encoder == "none"

    fps = float(source.avg_fps or source.fps or 25.0)
    if fps_mode == "custom" and custom_fps and custom_fps > 0:
        fps = float(custom_fps)
    width = int(source.display_width or (source.video.width if source.video else 1280) or 1280)
    height = int(source.display_height or (source.video.height if source.video else 720) or 720)
    if resolution_mode == "custom" and custom_size:
        width, height = int(custom_size[0]), int(custom_size[1])
        width -= width % 2
        height -= height % 2

    pix_extra: list[str] = []
    if video_encoder in {"libx264", "libx265", "h264_nvenc", "hevc_nvenc"}:
        pix_extra += ["-movflags", "+faststart"]
    return ExportPlan(
        container=container,
        video_encoder=video_encoder,
        audio_encoder="none" if drop_audio else audio_encoder,
        fps=fps,
        width=width,
        height=height,
        lossless=lossless,
        high_quality=high_quality,
        drop_audio=drop_audio,
        extra_args=pix_extra,
        warnings=warnings,
        output_name=output_name or "result",
    )


def finalize_output(
    silent_video: Path,
    source_path: Path,
    dest_path: Path,
    plan: ExportPlan,
    source_info: MediaInfo,
) -> Path:
    if plan.drop_audio or not source_info.has_audio:
        if silent_video.resolve() != dest_path.resolve():
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            if dest_path.exists():
                dest_path.unlink()
            silent_video.replace(dest_path)
        return dest_path
    mux_audio(
        silent_video,
        source_path,
        dest_path,
        audio_encoder=plan.audio_encoder,
        source_info=source_info,
        shortest=True,
    )
    return dest_path


def suffix_for_container(container: str) -> str:
    mapping = {
        "matroska": ".mkv",
        "mpegts": ".ts",
        "ipod": ".m4a",
        "mp4": ".mp4",
        "mov": ".mov",
        "webm": ".webm",
        "avi": ".avi",
        "gif": ".gif",
        "webp": ".webp",
    }
    return mapping.get(container, f".{container}")

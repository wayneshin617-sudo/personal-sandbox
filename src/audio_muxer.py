"""Recombine original audio with processed video. Never shell-interpolate paths."""

from __future__ import annotations

from pathlib import Path

from src.media_probe import MediaInfo, ffmpeg_bin, probe_media
from src.utils import CommandError, LOGGER, run_command


class MuxError(RuntimeError):
    pass


def mux_audio(
    video_path: str | Path,
    source_media: str | Path,
    output_path: str | Path,
    *,
    audio_encoder: str = "copy",
    source_info: MediaInfo | None = None,
    shortest: bool = False,
) -> Path:
    video_path = Path(video_path)
    source_media = Path(source_media)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    info = source_info or probe_media(source_media)
    if not info.has_audio:
        LOGGER.info("원본에 오디오가 없어 비디오만 복사합니다: %s -> %s", video_path, output_path)
        argv = [
            ffmpeg_bin(),
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video_path),
            "-an",
            "-c:v",
            "copy",
            str(output_path),
        ]
        try:
            run_command(argv, timeout=180)
        except CommandError as exc:
            raise MuxError(f"오디오 없는 출력 복사 실패: {exc}") from exc
        return output_path

    audio_args: list[str]
    if audio_encoder in {"copy", "auto", "", None}:
        audio_args = ["-c:a", "copy"]
    elif audio_encoder in {"none", "an"}:
        audio_args = ["-an"]
    else:
        audio_args = ["-c:a", audio_encoder]

    argv = [
        ffmpeg_bin(),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-i",
        str(source_media),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0?",
        "-c:v",
        "copy",
        *audio_args,
        "-avoid_negative_ts",
        "make_zero",
    ]
    if shortest:
        argv.append("-shortest")
    else:
        argv += ["-async", "1"]
    argv.append(str(output_path))
    LOGGER.info("mux argv: %s", argv)
    try:
        run_command(argv, timeout=300)
    except CommandError as exc:
        if audio_encoder in {"copy", "auto", "", None}:
            LOGGER.warning("오디오 copy 실패, aac로 재인코딩합니다: %s", exc)
            return mux_audio(
                video_path,
                source_media,
                output_path,
                audio_encoder="aac",
                source_info=info,
                shortest=True,
            )
        raise MuxError(f"오디오 결합 실패: {exc}") from exc
    return output_path


def extract_audio_stream(source_media: str | Path, output_audio: str | Path) -> Path | None:
    info = probe_media(source_media)
    if not info.has_audio:
        return None
    output_audio = Path(output_audio)
    argv = [
        ffmpeg_bin(),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(source_media),
        "-vn",
        "-acodec",
        "copy",
        str(output_audio),
    ]
    try:
        run_command(argv, timeout=180)
        return output_audio
    except CommandError:
        argv = [
            ffmpeg_bin(),
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(source_media),
            "-vn",
            "-c:a",
            "aac",
            str(output_audio.with_suffix(".m4a")),
        ]
        run_command(argv, timeout=180)
        return output_audio.with_suffix(".m4a")

"""Input / output validation. File extensions are never used as the decision."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.image_io import load_image
from src.media_probe import MediaInfo, probe_and_validate_video, probe_media
from src.utils import LOGGER, file_size


@dataclass
class ValidationResult:
    ok: bool
    kind: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


def validate_video_input(path: str | Path) -> ValidationResult:
    info = probe_and_validate_video(path)
    details = info.to_dict()
    if not info.exists:
        return ValidationResult(False, "video", info.decode_error or "파일 없음", details)
    if info.size_bytes <= 0:
        return ValidationResult(False, "video", "파일 크기가 0입니다.", details)
    if not info.video:
        return ValidationResult(
            False,
            "video",
            info.decode_error or "비디오 스트림이 없어 영상 입력으로 사용할 수 없습니다.",
            details,
        )
    if not info.decode_ok:
        return ValidationResult(
            False,
            "video",
            info.decode_error or "디코딩 테스트 실패",
            details,
        )
    if not info.display_width or not info.display_height:
        return ValidationResult(False, "video", "해상도를 읽을 수 없습니다.", details)
    return ValidationResult(True, "video", "디코딩 가능한 영상입니다.", details)


def validate_image_input(path: str | Path) -> ValidationResult:
    loaded = load_image(path)
    details = {
        "path": str(path),
        "ok": loaded.ok,
        "width": loaded.width,
        "height": loaded.height,
        "backend": loaded.backend,
        "mode": loaded.mode,
        "has_alpha": loaded.has_alpha,
        "error": loaded.error,
    }
    if not loaded.ok or loaded.image_bgr is None:
        return ValidationResult(False, "image", loaded.error or "이미지 디코딩 실패", details)
    return ValidationResult(True, "image", f"이미지 디코딩 성공 ({loaded.backend})", details)


def validate_output_media(
    output_path: str | Path,
    *,
    source: MediaInfo | None = None,
    expect_audio: bool | None = None,
    min_frames: int = 1,
) -> ValidationResult:
    path = Path(output_path)
    if not path.exists():
        return ValidationResult(False, "output", f"출력 파일이 없습니다: {path}")
    if file_size(path) <= 0:
        return ValidationResult(False, "output", "출력 파일 크기가 0입니다.")
    info = probe_media(path)
    if not info.video:
        return ValidationResult(False, "output", info.decode_error or "출력에 비디오 스트림이 없습니다.", info.to_dict())
    from src.media_probe import decode_smoke_test

    ok, err = decode_smoke_test(path, frames=min(3, max(1, min_frames)))
    if not ok:
        return ValidationResult(False, "output", f"출력 파일을 다시 디코딩할 수 없습니다: {err}", info.to_dict())

    problems: list[str] = []
    frames = info.video.nb_frames
    if frames is not None and frames < min_frames:
        problems.append(f"프레임 수가 부족합니다 ({frames} < {min_frames}).")
    if expect_audio is True and not info.has_audio:
        problems.append("원본에 오디오가 있었지만 출력에 오디오 스트림이 없습니다.")
    if expect_audio is False and info.has_audio:
        LOGGER.info("출력에 예상치 않은 오디오가 있습니다.")
    if source and source.duration and info.duration:
        drift = abs(info.duration - source.duration)
        if drift > 0.35:
            problems.append(
                f"duration 차이 {drift:.3f}s (src={source.duration:.3f}, out={info.duration:.3f})"
            )
    if problems:
        return ValidationResult(False, "output", " / ".join(problems), info.to_dict())
    return ValidationResult(True, "output", "출력 파일이 유효합니다.", info.to_dict())


def encoder_container_compatible(container: str, video_encoder: str, audio_encoder: str | None) -> tuple[bool, str]:
    container = (container or "").lower().lstrip(".")
    animation = container in {"gif", "webp", "apng"}
    if animation and audio_encoder and audio_encoder not in {"none", "an", ""}:
        return False, f"{container}는 애니메이션 이미지라 오디오를 담을 수 없습니다. 오디오를 제외하세요."
    known = {
        "mp4": {"libx264", "libx265", "h264", "hevc", "mpeg4", "libaom-av1", "libsvtav1", "av1"},
        "mov": {"libx264", "libx265", "h264", "hevc", "prores", "prores_ks", "mjpeg"},
        "mkv": None,
        "webm": {"libvpx", "libvpx-vp9", "libaom-av1", "libsvtav1", "vp8", "vp9", "av1"},
        "avi": {"mpeg4", "libxvid", "mjpeg", "rawvideo", "libx264"},
        "gif": {"gif"},
        "webp": {"libwebp", "libwebp_anim"},
    }
    allowed = known.get(container)
    if allowed is not None and video_encoder not in allowed and video_encoder != "auto":
        return False, (
            f"컨테이너 {container}와 비디오 코덱 {video_encoder} 조합은 일반적이지 않습니다. "
            f"권장: {sorted(allowed)}"
        )
    return True, "조합이 사용 가능합니다."

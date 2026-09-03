"""Decode images by content, not by file extension."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from src.utils import LOGGER


@dataclass
class ImageLoadResult:
    image_bgr: np.ndarray | None
    ok: bool
    width: int = 0
    height: int = 0
    channels: int = 0
    mode: str | None = None
    backend: str | None = None
    error: str | None = None
    has_alpha: bool = False


def _from_pillow(path: Path) -> ImageLoadResult:
    from PIL import Image, ImageOps, UnidentifiedImageError

    try:
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img)
            mode = img.mode
            has_alpha = mode in {"RGBA", "LA", "PA"} or (mode == "P" and "transparency" in img.info)
            if mode == "RGBA":
                background = Image.new("RGB", img.size, (0, 0, 0))
                background.paste(img, mask=img.split()[-1])
                rgb = background
            else:
                rgb = img.convert("RGB")
            arr = np.asarray(rgb)
    except UnidentifiedImageError as exc:
        return ImageLoadResult(None, False, error=f"Pillow가 이미지로 인식하지 못했습니다: {exc}")
    except OSError as exc:
        return ImageLoadResult(None, False, error=f"Pillow 디코딩 실패: {exc}")
    if arr.ndim != 3 or arr.shape[2] != 3:
        return ImageLoadResult(None, False, error=f"예상과 다른 배열 shape: {arr.shape}")
    bgr = arr[:, :, ::-1].copy()
    h, w = bgr.shape[:2]
    return ImageLoadResult(
        bgr,
        True,
        width=w,
        height=h,
        channels=3,
        mode=mode,
        backend="pillow",
        has_alpha=has_alpha,
    )


def _from_opencv(path: Path) -> ImageLoadResult:
    import cv2

    data = np.fromfile(str(path), dtype=np.uint8)
    if data.size == 0:
        return ImageLoadResult(None, False, error="빈 파일입니다.")
    bgr = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if bgr is None:
        return ImageLoadResult(None, False, error="OpenCV가 이 바이트를 이미지로 디코딩하지 못했습니다.")
    has_alpha = bgr.ndim == 3 and bgr.shape[2] == 4
    if bgr.ndim == 2:
        bgr = cv2.cvtColor(bgr, cv2.COLOR_GRAY2BGR)
    elif bgr.shape[2] == 4:
        bgr = cv2.cvtColor(bgr, cv2.COLOR_BGRA2BGR)
    h, w = bgr.shape[:2]
    return ImageLoadResult(
        bgr,
        True,
        width=w,
        height=h,
        channels=3,
        mode="BGR",
        backend="opencv",
        has_alpha=has_alpha,
    )


def load_image(path: str | Path) -> ImageLoadResult:
    path = Path(path)
    if not path.exists():
        return ImageLoadResult(None, False, error=f"파일이 없습니다: {path}")
    if path.stat().st_size <= 0:
        return ImageLoadResult(None, False, error="파일 크기가 0입니다.")

    pillow_result = _from_pillow(path)
    if pillow_result.ok:
        return pillow_result
    LOGGER.info("Pillow 실패, OpenCV로 재시도: %s", pillow_result.error)
    cv_result = _from_opencv(path)
    if cv_result.ok:
        cv_result.error = None
        return cv_result
    return ImageLoadResult(
        None,
        False,
        error=(
            "이미지로 디코딩할 수 없습니다. "
            f"Pillow: {pillow_result.error} / OpenCV: {cv_result.error}"
        ),
    )


def bgr_to_rgb(image_bgr: np.ndarray) -> np.ndarray:
    return image_bgr[:, :, ::-1].copy()

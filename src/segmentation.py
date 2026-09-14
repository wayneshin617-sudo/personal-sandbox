"""Face-region masks from landmarks. Full-body person segmentation is Advanced-only."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from src.face_detector import Face
from src.face_swapper import build_face_mask


@dataclass
class SegmentationCapability:
    face_mask_available: bool
    person_mask_available: bool
    reason: str


def capability() -> SegmentationCapability:
    return SegmentationCapability(
        face_mask_available=True,
        person_mask_available=False,
        reason=(
            "전신 인물 변환에 필요한 person segmentation 모델(예: SAM / Mask2Former / SCHP)과 "
            "GPU 메모리가 없습니다. 얼굴 교체는 랜드마크 convex hull + 페더링 마스크를 사용합니다. "
            "이 마스크를 전신 의상 변환용 segmentation이라고 표시하지 않습니다."
        ),
    )


def face_mask(image_shape: tuple[int, int], face: Face, mask_range: float) -> np.ndarray:
    return build_face_mask(image_shape, face.kps, face.landmarks106, mask_range)


def apply_mask_preview(image_bgr: np.ndarray, mask: np.ndarray) -> np.ndarray:
    color = image_bgr.copy()
    overlay = image_bgr.copy()
    overlay[mask > 32] = (0, 220, 180)
    alpha = (mask.astype(np.float32) / 255.0)[..., None] * 0.45
    return np.clip(alpha * overlay + (1 - alpha) * color, 0, 255).astype(np.uint8)

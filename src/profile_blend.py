"""Side-face (yaw) helpers so profile swaps do not paste a frontal blob."""

from __future__ import annotations

import cv2
import numpy as np


def estimate_yaw(kps: np.ndarray | None) -> float:
    """Nose offset vs eye midpoint, normalized by eye width. + = nose to the right."""
    if kps is None or len(kps) < 3:
        return 0.0
    pts = np.asarray(kps, dtype=np.float32)
    left_eye, right_eye, nose = pts[0], pts[1], pts[2]
    mid_x = (float(left_eye[0]) + float(right_eye[0])) * 0.5
    eye_w = abs(float(right_eye[0]) - float(left_eye[0])) + 1e-6
    return float((float(nose[0]) - mid_x) / eye_w)


def is_profile(yaw: float, thresh: float = 0.32) -> bool:
    return abs(float(yaw)) >= thresh


def profile_restore(yaw: float, base: float) -> float:
    # Speed path: restore_strength 0 means skip GFPGAN entirely, including profiles.
    if float(base) <= 0.01:
        return 0.0
    extra = 0.22 if is_profile(yaw, 0.45) else 0.12 if is_profile(yaw) else 0.0
    return float(min(0.65, max(base, 0.28) + extra))


def profile_mask_range(yaw: float, base: float) -> float:
    if is_profile(yaw, 0.45):
        return float(min(base, 0.52))
    if is_profile(yaw):
        return float(min(base, 0.62))
    return float(base)


def fade_occluded_side(mask: np.ndarray, box: list[float], yaw: float) -> np.ndarray:
    """Keep the visible cheek, fade the hidden side so a frontal swap does not smear."""
    if mask.size == 0 or not is_profile(yaw, 0.28):
        return mask
    x1, _y1, x2, _y2 = [float(v) for v in box[:4]]
    width = max(1.0, x2 - x1)
    xs = np.arange(mask.shape[1], dtype=np.float32)
    t = np.clip((xs - x1) / width, 0.0, 1.0)
    if yaw > 0:
        # Nose toward the right: left side is turning away.
        fade = np.clip((t - 0.08) / 0.42, 0.0, 1.0)
    else:
        fade = np.clip((0.92 - t) / 0.42, 0.0, 1.0)
    fade = np.power(fade, 0.85)
    out = mask.astype(np.float32) * fade[None, :]
    return np.clip(out, 0, 255).astype(np.uint8)


def soften_profile_edge(mask: np.ndarray, yaw: float) -> np.ndarray:
    if not is_profile(yaw):
        return mask
    k = 21 if is_profile(yaw, 0.45) else 13
    k |= 1
    return cv2.GaussianBlur(mask, (k, k), 0)

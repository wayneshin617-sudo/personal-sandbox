from __future__ import annotations

import numpy as np

from src.profile_blend import estimate_yaw, fade_occluded_side, is_profile, profile_restore


def test_yaw_positive_when_nose_is_right_of_eyes() -> None:
    kps = np.array([[10, 10], [30, 10], [28, 18], [12, 28], [26, 28]], dtype=np.float32)
    yaw = estimate_yaw(kps)
    assert yaw > 0.3
    assert is_profile(yaw)


def test_yaw_negative_when_nose_is_left_of_eyes() -> None:
    kps = np.array([[10, 10], [30, 10], [12, 18], [12, 28], [26, 28]], dtype=np.float32)
    yaw = estimate_yaw(kps)
    assert yaw < -0.3
    assert is_profile(yaw)


def test_frontal_face_is_not_profile() -> None:
    kps = np.array([[10, 10], [30, 10], [20, 18], [12, 28], [28, 28]], dtype=np.float32)
    assert not is_profile(estimate_yaw(kps))


def test_profile_mask_fades_hidden_side() -> None:
    mask = np.full((20, 40), 255, dtype=np.uint8)
    faded = fade_occluded_side(mask, [0, 0, 40, 20], yaw=0.8)
    assert faded[:, 2].mean() < faded[:, 35].mean()


def test_profile_uses_stronger_restore() -> None:
    assert profile_restore(0.7, 0.2) > profile_restore(0.0, 0.2)


def test_disabled_restore_stays_off_on_profile() -> None:
    assert profile_restore(0.8, 0.0) == 0.0
    assert profile_restore(0.8, 0.01) == 0.0

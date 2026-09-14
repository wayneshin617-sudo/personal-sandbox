"""Temporal smoothing for boxes/landmarks. Never freezes a previous swapped face."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class LandmarkSmoother:
    alpha: float = 0.35
    _state: np.ndarray | None = field(default=None, init=False)

    def reset(self) -> None:
        self._state = None

    def update(self, points: np.ndarray | None, valid: bool) -> np.ndarray | None:
        if not valid or points is None:
            # Detection failed: do not keep emitting a stale face crop.
            self._state = None
            return None
        pts = np.asarray(points, dtype=np.float32)
        if self._state is None:
            self._state = pts.copy()
            return self._state
        self._state = self.alpha * pts + (1.0 - self.alpha) * self._state
        return self._state


@dataclass
class BoxSmoother:
    alpha: float = 0.40
    _state: np.ndarray | None = field(default=None, init=False)

    def reset(self) -> None:
        self._state = None

    def update(self, box: list[float] | None, valid: bool) -> list[float] | None:
        if not valid or box is None:
            self._state = None
            return None
        arr = np.asarray(box, dtype=np.float32)
        if self._state is None:
            self._state = arr.copy()
            return [float(x) for x in self._state]
        self._state = self.alpha * arr + (1.0 - self.alpha) * self._state
        return [float(x) for x in self._state]


def blend_mask_temporal(prev: np.ndarray | None, current: np.ndarray, alpha: float = 0.45) -> np.ndarray:
    if prev is None or prev.shape != current.shape:
        return current
    return (alpha * current + (1.0 - alpha) * prev).astype(current.dtype)

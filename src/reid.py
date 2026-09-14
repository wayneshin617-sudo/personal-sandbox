"""Re-identify a lost target using face embedding, clothing histogram, and motion."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.utils import cosine_similarity, hist_similarity


@dataclass
class AppearanceState:
    embedding: np.ndarray | None
    histogram: np.ndarray | None
    last_center: tuple[float, float] | None
    last_box: list[float] | None
    last_frame_index: int
    velocity: tuple[float, float] = (0.0, 0.0)


def predicted_center(state: AppearanceState, frame_index: int) -> tuple[float, float] | None:
    if state.last_center is None:
        return None
    dt = max(0, frame_index - state.last_frame_index)
    return (
        state.last_center[0] + state.velocity[0] * dt,
        state.last_center[1] + state.velocity[1] * dt,
    )


def reid_score(
    state: AppearanceState,
    embedding: np.ndarray | None,
    histogram: np.ndarray | None,
    center: tuple[float, float],
    frame_index: int,
    frame_diag: float,
) -> float:
    """Higher is better. Embedding is the strongest cue; clothing and motion break ties."""
    emb = cosine_similarity(state.embedding, embedding)
    app = hist_similarity(state.histogram, histogram)
    pred = predicted_center(state, frame_index)
    if pred is None:
        motion = 0.5
    else:
        dist = float(np.hypot(center[0] - pred[0], center[1] - pred[1]))
        motion = float(np.exp(-dist / max(32.0, 0.25 * frame_diag)))
    # Do not let a random nearby person win just because they are large.
    return 0.62 * emb + 0.23 * app + 0.15 * motion


def update_velocity(
    prev_center: tuple[float, float] | None,
    center: tuple[float, float],
    prev_index: int,
    frame_index: int,
) -> tuple[float, float]:
    if prev_center is None:
        return (0.0, 0.0)
    dt = max(1, frame_index - prev_index)
    return ((center[0] - prev_center[0]) / dt, (center[1] - prev_center[1]) / dt)

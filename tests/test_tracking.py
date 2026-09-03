from __future__ import annotations

import numpy as np

from src.tracker import Detection, MultiObjectTracker


def _det(box, emb, score=0.9) -> Detection:
    return Detection(
        box=list(box),
        score=score,
        kps=np.array([[box[0], box[1]], [box[2], box[1]], [(box[0] + box[2]) / 2, (box[1] + box[3]) / 2],
                      [box[0], box[3]], [box[2], box[3]]], dtype=np.float32),
        embedding=np.asarray(emb, dtype=np.float32),
        histogram=np.asarray(emb, dtype=np.float32),
        person_box=list(box),
    )


def test_track_id_stays_on_identity_not_largest_box() -> None:
    tracker = MultiObjectTracker(match_thresh=0.3, reid_thresh=0.4)
    a = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    b = np.array([0.0, 1.0, 0.0], dtype=np.float32)
    tracks = tracker.update(
        [_det([10, 10, 40, 40], a), _det([80, 10, 140, 80], b)],
        0,
        (200, 120),
    )
    id_a = next(t.track_id for t in tracks if np.allclose(t.embedding[:3], a / np.linalg.norm(a), atol=0.2) or t.box[0] < 50)
    # Next frame: B becomes huge, A moves slightly. Target A must keep the same ID.
    tracks = tracker.update(
        [_det([18, 12, 48, 44], a), _det([20, 5, 190, 115], b)],
        1,
        (200, 120),
    )
    still_a = next(t for t in tracks if t.track_id == id_a)
    assert still_a.box[0] < 60


def test_low_confidence_lost_track_is_not_replaced_by_stranger() -> None:
    tracker = MultiObjectTracker(match_thresh=0.55, max_misses=2, reid_thresh=0.85)
    a = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    stranger = np.array([0.0, 0.0, 1.0], dtype=np.float32)
    tracker.update([_det([10, 10, 40, 40], a)], 0, (200, 120))
    tid = list(tracker.tracks)[0]
    tracker.update([], 1, (200, 120))
    tracker.update([], 2, (200, 120))
    tracker.update([], 3, (200, 120))
    assert tid not in tracker.tracks
    tracker.update([_det([12, 12, 42, 42], stranger)], 4, (200, 120))
    # Stranger should become a new ID, not steal the lost target.
    assert tid not in tracker.tracks
    assert list(tracker.tracks.values())[0].track_id != tid

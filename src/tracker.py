"""Multi-object tracker bound to a chosen identity. Size alone never retargets."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import linear_sum_assignment

from src.reid import AppearanceState, reid_score, update_velocity
from src.utils import box_center, cosine_similarity, hist_similarity, iou_xyxy


@dataclass
class Detection:
    box: list[float]
    score: float
    kps: np.ndarray | None
    embedding: np.ndarray | None
    histogram: np.ndarray | None
    person_box: list[float] | None = None


@dataclass
class Track:
    track_id: int
    box: list[float]
    kps: np.ndarray | None
    embedding: np.ndarray | None
    histogram: np.ndarray | None
    person_box: list[float] | None
    score: float
    hits: int = 1
    misses: int = 0
    last_frame: int = 0
    confirmed: bool = True
    velocity: tuple[float, float] = (0.0, 0.0)
    last_center: tuple[float, float] = (0.0, 0.0)
    history: list[list[float]] = field(default_factory=list)

    @property
    def confidence(self) -> float:
        hit_term = min(1.0, self.hits / 6.0)
        miss_pen = max(0.0, 1.0 - self.misses / 12.0)
        det = float(self.score)
        return float(max(0.0, min(1.0, 0.45 * hit_term + 0.25 * miss_pen + 0.30 * det)))


class MultiObjectTracker:
    def __init__(
        self,
        match_thresh: float = 0.35,
        max_misses: int = 18,
        reid_thresh: float = 0.45,
    ):
        self.match_thresh = match_thresh
        self.max_misses = max_misses
        self.reid_thresh = reid_thresh
        self.tracks: dict[int, Track] = {}
        self.lost: dict[int, Track] = {}
        self._next_id = 1
        self.frame_index = -1
        self.frame_size = (1, 1)

    def reset(self) -> None:
        self.tracks.clear()
        self.lost.clear()
        self._next_id = 1
        self.frame_index = -1

    def _new_track(self, det: Detection) -> Track:
        center = box_center(det.box)
        track = Track(
            track_id=self._next_id,
            box=list(det.box),
            kps=None if det.kps is None else np.asarray(det.kps),
            embedding=None if det.embedding is None else np.asarray(det.embedding),
            histogram=None if det.histogram is None else np.asarray(det.histogram),
            person_box=det.person_box,
            score=det.score,
            last_frame=self.frame_index,
            last_center=center,
        )
        self._next_id += 1
        self.tracks[track.track_id] = track
        return track

    def _cost(self, track: Track, det: Detection) -> float:
        iou = iou_xyxy(track.box, det.box)
        emb = cosine_similarity(track.embedding, det.embedding)
        app = hist_similarity(track.histogram, det.histogram)
        # Cost: 0 is perfect. Embedding dominates so a closer larger stranger is not chosen.
        return 0.28 * (1.0 - iou) + 0.55 * (1.0 - max(emb, 0.0)) + 0.17 * (1.0 - app)

    def update(self, detections: list[Detection], frame_index: int, frame_size: tuple[int, int]) -> list[Track]:
        self.frame_index = frame_index
        self.frame_size = frame_size
        track_ids = list(self.tracks.keys())
        if not track_ids and not detections:
            return []
        if not track_ids:
            for det in detections:
                self._new_track(det)
            return list(self.tracks.values())
        if not detections:
            for tid in list(self.tracks.keys()):
                self._mark_miss(tid)
            return list(self.tracks.values())

        cost = np.ones((len(track_ids), len(detections)), dtype=np.float32)
        for i, tid in enumerate(track_ids):
            for j, det in enumerate(detections):
                cost[i, j] = self._cost(self.tracks[tid], det)
        rows, cols = linear_sum_assignment(cost)
        assigned_tracks = set()
        assigned_dets = set()
        for r, c in zip(rows, cols):
            if cost[r, c] > (1.0 - self.match_thresh):
                continue
            self._apply(self.tracks[track_ids[r]], detections[c])
            assigned_tracks.add(track_ids[r])
            assigned_dets.add(c)

        for tid in track_ids:
            if tid not in assigned_tracks:
                self._mark_miss(tid)
        unmatched = [detections[j] for j in range(len(detections)) if j not in assigned_dets]
        still_unmatched: list[Detection] = []
        for det in unmatched:
            recovered = self._try_reid(det)
            if recovered is None:
                still_unmatched.append(det)
        for det in still_unmatched:
            self._new_track(det)
        return list(self.tracks.values())

    def _apply(self, track: Track, det: Detection) -> None:
        center = box_center(det.box)
        track.velocity = update_velocity(track.last_center, center, track.last_frame, self.frame_index)
        track.last_center = center
        track.box = list(det.box)
        track.person_box = det.person_box
        track.kps = None if det.kps is None else np.asarray(det.kps)
        if det.embedding is not None:
            if track.embedding is None:
                track.embedding = np.asarray(det.embedding)
            else:
                track.embedding = 0.75 * track.embedding + 0.25 * np.asarray(det.embedding)
                nrm = float(np.linalg.norm(track.embedding))
                if nrm > 0:
                    track.embedding = track.embedding / nrm
        if det.histogram is not None:
            track.histogram = np.asarray(det.histogram)
        track.score = det.score
        track.hits += 1
        track.misses = 0
        track.last_frame = self.frame_index
        track.history.append(list(det.box))
        if len(track.history) > 48:
            track.history = track.history[-48:]

    def _mark_miss(self, track_id: int) -> None:
        track = self.tracks.get(track_id)
        if track is None:
            return
        track.misses += 1
        track.kps = None
        if track.misses > self.max_misses:
            self.lost[track_id] = track
            del self.tracks[track_id]

    def _try_reid(self, det: Detection) -> Track | None:
        if not self.lost:
            return None
        diag = float(np.hypot(*self.frame_size))
        center = box_center(det.box)
        best_id = None
        best_score = -1.0
        for tid, track in self.lost.items():
            state = AppearanceState(
                embedding=track.embedding,
                histogram=track.histogram,
                last_center=track.last_center,
                last_box=track.box,
                last_frame_index=track.last_frame,
                velocity=track.velocity,
            )
            score = reid_score(state, det.embedding, det.histogram, center, self.frame_index, diag)
            if score > best_score:
                best_score = score
                best_id = tid
        if best_id is None or best_score < self.reid_thresh:
            return None
        track = self.lost.pop(best_id)
        self.tracks[best_id] = track
        self._apply(track, det)
        return track

    def get(self, track_id: int) -> Track | None:
        return self.tracks.get(track_id) or self.lost.get(track_id)

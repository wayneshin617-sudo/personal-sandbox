"""Select a target person by click coordinates or by displayed number."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from src.face_detector import Face
from src.person_detector import PersonCandidate
from src.utils import cosine_similarity, iou_xyxy


@dataclass
class Selection:
    person_index: int
    box: list[float]
    person_box: list[float]
    embedding: np.ndarray | None
    kps: np.ndarray | None


def draw_candidates(
    image_bgr: np.ndarray,
    candidates: list[PersonCandidate],
    selected: int | None = None,
    *,
    studio: bool = False,
    labels: dict[int, str] | None = None,
) -> np.ndarray:
    canvas = image_bgr.copy()
    for cand in candidates:
        color = (40, 220, 40) if selected == cand.index else (40, 180, 255)
        x1, y1, x2, y2 = [int(v) for v in cand.face.box]
        px1, py1, px2, py2 = [int(v) for v in cand.person_box]
        if not studio:
            cv2.rectangle(canvas, (px1, py1), (px2, py2), (80, 80, 80), 1)
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)
        if labels and cand.index in labels:
            label = labels[cand.index]
        else:
            label = "얼굴" if studio else f"#{cand.index}  score={cand.face.score:.2f}"
        cv2.putText(canvas, label, (x1, max(16, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2, cv2.LINE_AA)
        if not studio and cand.face.kps is not None:
            for pt in cand.face.kps:
                cv2.circle(canvas, (int(pt[0]), int(pt[1])), 2, (0, 0, 255), -1)
    return canvas


def select_by_number(candidates: list[PersonCandidate], number: int) -> Selection | None:
    for cand in candidates:
        if cand.index == number:
            return Selection(
                person_index=cand.index,
                box=list(cand.face.box),
                person_box=list(cand.person_box),
                embedding=cand.face.normed_embedding,
                kps=cand.face.kps,
            )
    return None


def select_by_click(candidates: list[PersonCandidate], x: int, y: int) -> Selection | None:
    hits: list[tuple[float, PersonCandidate]] = []
    for cand in candidates:
        x1, y1, x2, y2 = cand.face.box
        px1, py1, px2, py2 = cand.person_box
        if px1 <= x <= px2 and py1 <= y <= py2:
            # Prefer the face that actually contains the click; otherwise nearest face center.
            face_hit = 1.0 if x1 <= x <= x2 and y1 <= y <= y2 else 0.0
            area = max(1.0, (x2 - x1) * (y2 - y1))
            hits.append((face_hit * 10.0 + 1.0 / area, cand))
    if not hits:
        return None
    hits.sort(key=lambda t: t[0], reverse=True)
    return select_by_number(candidates, hits[0][1].index)


def seed_track_id_from_selection(
    tracks_snapshot: list,
    selection: Selection,
) -> int | None:
    """Bind the user selection to the tracker ID whose box overlaps the chosen face."""
    return bind_track_id(tracks_snapshot, selection)


def bind_track_id(
    tracks_snapshot: list,
    selection: Selection,
    current_id: int | None = None,
    emb_thresh: float = 0.35,
) -> int | None:
    """Keep the chosen person even after a cut or angle change.

    Prefer embedding match so a new local #1 in the next shot does not steal
    the target. Fall back to box overlap only when embeddings are missing.
    """
    if current_id is not None:
        current = next((track for track in tracks_snapshot if getattr(track, "track_id", None) == current_id), None)
        if current is not None and getattr(current, "misses", 0) == 0 and getattr(current, "kps", None) is not None:
            return current_id

    best_id = None
    best_sim = emb_thresh
    if selection.embedding is not None:
        for track in tracks_snapshot:
            sim = cosine_similarity(getattr(track, "embedding", None), selection.embedding)
            if sim > best_sim:
                best_sim = sim
                best_id = getattr(track, "track_id", None)
        if best_id is not None:
            return best_id

    best_id = None
    best_iou = 0.1
    for track in tracks_snapshot:
        overlap = iou_xyxy(track.box, selection.box)
        if overlap > best_iou:
            best_iou = overlap
            best_id = track.track_id
    return best_id


def face_from_selection(faces: list[Face], selection: Selection, thresh: float = 0.35) -> Face | None:
    """Pick the current-frame face that matches the chosen identity."""
    if not faces:
        return None
    best = None
    best_sim = thresh
    if selection.embedding is not None:
        for face in faces:
            sim = cosine_similarity(face.normed_embedding, selection.embedding)
            if sim > best_sim:
                best_sim = sim
                best = face
        if best is not None:
            return best
    best_iou = 0.15
    for face in faces:
        overlap = iou_xyxy(face.box, selection.box)
        if overlap > best_iou:
            best_iou = overlap
            best = face
    return best

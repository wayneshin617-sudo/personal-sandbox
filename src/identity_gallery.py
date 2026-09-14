"""Cluster faces sampled across a video into stable person identities."""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from src.utils import LOGGER, clip_box, cosine_similarity


IDENTITY_THRESH = 0.42
MAX_SAMPLES = 10
THUMB = 96


@dataclass
class IdentityHit:
    time_sec: float
    box: list[float]
    person_box: list[float]
    crop_rgb: np.ndarray
    kps: np.ndarray | None
    embedding: np.ndarray
    local_index: int


@dataclass
class Identity:
    id: int
    embedding: np.ndarray
    hits: list[IdentityHit] = field(default_factory=list)

    @property
    def times(self) -> list[float]:
        return [h.time_sec for h in self.hits]

    @property
    def thumb_rgb(self) -> np.ndarray:
        return self.hits[0].crop_rgb


def sample_times(duration: float, count: int = MAX_SAMPLES) -> list[float]:
    if duration <= 0.05:
        return [0.0]
    usable = max(1, min(count, int(duration / 1.5) + 1))
    lo = min(0.2, duration * 0.05)
    hi = max(lo, duration * 0.92)
    if usable == 1:
        return [round(lo, 3)]
    step = (hi - lo) / (usable - 1)
    return [round(lo + i * step, 3) for i in range(usable)]


def crop_face_rgb(frame_bgr: np.ndarray, box: list[float], size: int = THUMB) -> np.ndarray:
    h, w = frame_bgr.shape[:2]
    x1, y1, x2, y2 = box
    bw, bh = max(1.0, x2 - x1), max(1.0, y2 - y1)
    pad = clip_box([x1 - 0.2 * bw, y1 - 0.25 * bh, x2 + 0.2 * bw, y2 + 0.2 * bh], w, h)
    xa, ya, xb, yb = [int(v) for v in pad]
    xb, yb = max(xa + 1, xb), max(ya + 1, yb)
    crop = frame_bgr[ya:yb, xa:xb]
    if crop.size == 0:
        crop = np.zeros((size, size, 3), dtype=np.uint8)
    rgb = cv2.cvtColor(cv2.resize(crop, (size, size), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)
    return rgb


def assign_identities(hits: list[IdentityHit], thresh: float = IDENTITY_THRESH) -> list[Identity]:
    identities: list[Identity] = []
    for hit in hits:
        best_i = -1
        best_sim = thresh
        for i, ident in enumerate(identities):
            sim = cosine_similarity(hit.embedding, ident.embedding)
            if sim > best_sim:
                best_sim = sim
                best_i = i
        if best_i < 0:
            ident = Identity(id=len(identities) + 1, embedding=np.asarray(hit.embedding, dtype=np.float32), hits=[hit])
            identities.append(ident)
            continue
        ident = identities[best_i]
        ident.hits.append(hit)
        stacked = np.vstack([ident.embedding, np.asarray(hit.embedding, dtype=np.float32)])
        mean = stacked.mean(axis=0)
        nrm = float(np.linalg.norm(mean))
        ident.embedding = mean / nrm if nrm > 1e-8 else mean
    identities.sort(key=lambda ident: (-len(ident.hits), ident.hits[0].time_sec))
    for i, ident in enumerate(identities, start=1):
        ident.id = i
    return identities


def match_identity(embedding: np.ndarray | None, identities: list[Identity], thresh: float = IDENTITY_THRESH) -> Identity | None:
    if embedding is None or not identities:
        return None
    best = None
    best_sim = thresh
    for ident in identities:
        sim = cosine_similarity(embedding, ident.embedding)
        if sim > best_sim:
            best_sim = sim
            best = ident
    return best


def build_gallery(video_path, info, detector, extract_frame) -> list[Identity]:
    duration = float(getattr(info, "duration", 0.0) or 0.0)
    times = sample_times(duration)
    raw: list[IdentityHit] = []
    for ts in times:
        try:
            frame = extract_frame(video_path, ts, info)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("gallery frame %.2fs failed: %s", ts, exc)
            continue
        candidates = detector.candidates(frame)
        for cand in candidates:
            emb = cand.face.normed_embedding
            if emb is None:
                continue
            raw.append(
                IdentityHit(
                    time_sec=float(ts),
                    box=list(cand.face.box),
                    person_box=list(cand.person_box),
                    crop_rgb=crop_face_rgb(frame, list(cand.face.box)),
                    kps=cand.face.kps,
                    embedding=np.asarray(emb, dtype=np.float32),
                    local_index=int(cand.index),
                )
            )
    identities = assign_identities(raw)
    LOGGER.info("gallery identities=%s hits=%s samples=%s", len(identities), len(raw), len(times))
    return identities


def format_times(times: list[float]) -> str:
    if not times:
        return ""
    shown = []
    last = None
    for t in times:
        key = round(t, 1)
        if last is not None and abs(key - last) < 0.15:
            continue
        shown.append(f"{t:.1f}초")
        last = key
        if len(shown) >= 5:
            break
    return " · ".join(shown)

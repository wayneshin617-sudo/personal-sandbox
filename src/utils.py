"""Shared helpers: logging, subprocess, temp cleanup, geometry."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from config import LOGS_DIR, TEMP_DIR, TEMP_MAX_AGE_HOURS, ensure_runtime_dirs


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def setup_logger(name: str = "faceswap", log_file: Path | None = None) -> logging.Logger:
    ensure_runtime_dirs()
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(formatter)
    logger.addHandler(stream)
    if log_file is None:
        log_file = LOGS_DIR / f"app_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger


LOGGER = setup_logger()


class CommandError(RuntimeError):
    def __init__(self, message: str, argv: Sequence[str], returncode: int, stderr: str):
        super().__init__(message)
        self.argv = list(argv)
        self.returncode = returncode
        self.stderr = stderr


def run_command(
    argv: Sequence[str],
    *,
    timeout: int | None = None,
    check: bool = True,
    capture: bool = True,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess with an argument array. Never uses shell=True."""
    if not argv:
        raise ValueError("command argv is empty")
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    LOGGER.debug("exec: %s", " ".join(str(a) for a in argv))
    try:
        proc = subprocess.run(
            [str(a) for a in argv],
            check=False,
            capture_output=capture,
            text=True,
            timeout=timeout,
            cwd=str(cwd) if cwd else None,
            env=merged_env,
        )
    except FileNotFoundError as exc:
        raise CommandError(f"executable not found: {argv[0]}", argv, 127, str(exc)) from exc
    except subprocess.TimeoutExpired as exc:
        raise CommandError(f"command timed out: {argv[0]}", argv, 124, str(exc)) from exc
    if check and proc.returncode != 0:
        stderr = (proc.stderr or "")[-4000:]
        raise CommandError(
            f"command failed ({proc.returncode}): {argv[0]}\n{stderr}",
            argv,
            proc.returncode,
            proc.stderr or "",
        )
    return proc


def which(name: str) -> str | None:
    return shutil.which(name)


def sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            data = handle.read(chunk)
            if not data:
                break
            digest.update(data)
    return digest.hexdigest()


def file_size(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


def safe_stem(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-._()[] " else "_" for ch in name)
    cleaned = cleaned.strip() or "output"
    return cleaned[:180]


def unique_path(directory: Path, stem: str, suffix: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    candidate = directory / f"{stem}{suffix}"
    if not candidate.exists():
        return candidate
    return directory / f"{stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}{suffix}"


def make_work_dir(prefix: str = "job") -> Path:
    ensure_runtime_dirs()
    path = TEMP_DIR / f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cleanup_work_dir(path: Path | None) -> None:
    if path is None:
        return
    try:
        if path.exists() and path.is_dir() and TEMP_DIR in path.resolve().parents:
            shutil.rmtree(path, ignore_errors=True)
    except OSError as exc:
        LOGGER.warning("temp cleanup failed for %s: %s", path, exc)


def cleanup_old_temps(max_age_hours: float = TEMP_MAX_AGE_HOURS) -> int:
    ensure_runtime_dirs()
    removed = 0
    cutoff = time.time() - max_age_hours * 3600
    for child in TEMP_DIR.iterdir():
        try:
            if child.stat().st_mtime < cutoff:
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                else:
                    child.unlink(missing_ok=True)
                removed += 1
        except OSError:
            continue
    return removed


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def cosine_similarity(a: np.ndarray | None, b: np.ndarray | None) -> float:
    if a is None or b is None:
        return 0.0
    va = np.asarray(a, dtype=np.float32).ravel()
    vb = np.asarray(b, dtype=np.float32).ravel()
    na = float(np.linalg.norm(va))
    nb = float(np.linalg.norm(vb))
    if na < 1e-8 or nb < 1e-8:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


def iou_xyxy(a: Sequence[float], b: Sequence[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    denom = area_a + area_b - inter
    return float(inter / denom) if denom > 0 else 0.0


def clip_box(box: Sequence[float], width: int, height: int) -> list[float]:
    x1, y1, x2, y2 = box
    return [
        float(max(0, min(width - 1, x1))),
        float(max(0, min(height - 1, y1))),
        float(max(0, min(width, x2))),
        float(max(0, min(height, y2))),
    ]


def box_center(box: Sequence[float]) -> tuple[float, float]:
    return (float(box[0] + box[2]) * 0.5, float(box[1] + box[3]) * 0.5)


def expand_face_to_person_box(box: Sequence[float], width: int, height: int) -> list[float]:
    x1, y1, x2, y2 = box
    bw, bh = max(1.0, x2 - x1), max(1.0, y2 - y1)
    nx1 = x1 - 0.45 * bw
    nx2 = x2 + 0.45 * bw
    ny1 = y1 - 0.55 * bh
    ny2 = y2 + 3.2 * bh
    return clip_box([nx1, ny1, nx2, ny2], width, height)


def hsv_histogram(image_bgr: np.ndarray, box: Sequence[float] | None = None) -> np.ndarray:
    crop = image_bgr
    if box is not None:
        x1, y1, x2, y2 = [int(v) for v in box]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = max(x1 + 1, x2), max(y1 + 1, y2)
        crop = image_bgr[y1:y2, x1:x2]
    if crop.size == 0:
        return np.zeros(48, dtype=np.float32)
    hsv = __import__("cv2").cvtColor(crop, __import__("cv2").COLOR_BGR2HSV)
    hist = __import__("cv2").calcHist([hsv], [0, 1], None, [8, 6], [0, 180, 0, 256])
    hist = hist.astype(np.float32).ravel()
    norm = float(np.linalg.norm(hist))
    return hist / norm if norm > 0 else hist


def hist_similarity(a: np.ndarray | None, b: np.ndarray | None) -> float:
    if a is None or b is None or a.size == 0 or b.size == 0:
        return 0.0
    return float(np.clip(np.dot(a.ravel(), b.ravel()), 0.0, 1.0))


def parse_fraction(value: str | None, default: float = 0.0) -> float:
    if not value or value in {"0/0", "N/A"}:
        return default
    if "/" in value:
        num, den = value.split("/", 1)
        try:
            den_f = float(den)
            return float(num) / den_f if den_f else default
        except ValueError:
            return default
    try:
        return float(value)
    except ValueError:
        return default


@dataclass
class ProgressEvent:
    current: int
    total: int
    message: str
    extra: dict[str, Any] | None = None

    @property
    def ratio(self) -> float:
        if self.total <= 0:
            return 0.0
        return min(1.0, self.current / self.total)


def iter_chunks(items: Iterable[Any], size: int) -> Iterable[list[Any]]:
    batch: list[Any] = []
    for item in items:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch

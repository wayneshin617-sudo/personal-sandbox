"""Locate, download, and checksum InsightFace / GFPGAN model files."""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from urllib.request import Request, urlopen

from config import (
    BUFFALO_DIRNAME,
    GFPGAN_FILENAME,
    INSWAPPER_FILENAME,
    LANDMARK_FILENAME,
    MODEL_CHECKSUMS,
    MODEL_URLS,
    MODELS_DIR,
    SCRFD_FILENAME,
    ARCFACE_FILENAME,
    ensure_runtime_dirs,
)
from src.utils import LOGGER, sha256_file


ProgressCb = Callable[[str, int, int], None]


@dataclass
class ModelStatus:
    name: str
    path: Path
    present: bool
    size_bytes: int = 0
    sha256: str | None = None
    required: bool = True
    license_name: str = ""
    source: str = ""
    error: str | None = None


@dataclass
class ModelBundle:
    ready_for_faceswap: bool
    detector: ModelStatus
    recognizer: ModelStatus
    swapper: ModelStatus
    landmark: ModelStatus
    restorer: ModelStatus
    messages: list[str] = field(default_factory=list)

    def missing_required(self) -> list[str]:
        missing = []
        for item in (self.detector, self.recognizer, self.swapper):
            if item.required and not item.present:
                missing.append(item.name)
        return missing


def _status(name: str, path: Path, required: bool, license_name: str, source: str) -> ModelStatus:
    present = path.exists() and path.stat().st_size > 0
    return ModelStatus(
        name=name,
        path=path,
        present=present,
        size_bytes=path.stat().st_size if present else 0,
        required=required,
        license_name=license_name,
        source=source,
        error=None if present else f"{path.name} 없음",
    )


def buffalo_dir() -> Path:
    return MODELS_DIR / BUFFALO_DIRNAME


def model_paths() -> dict[str, Path]:
    bdir = buffalo_dir()
    return {
        "scrfd": bdir / SCRFD_FILENAME,
        "arcface": bdir / ARCFACE_FILENAME,
        "landmark": bdir / LANDMARK_FILENAME,
        "inswapper": MODELS_DIR / INSWAPPER_FILENAME,
        "gfpgan": MODELS_DIR / GFPGAN_FILENAME,
    }


def inspect_models() -> ModelBundle:
    ensure_runtime_dirs()
    paths = model_paths()
    license_if = "InsightFace model license (non-commercial research; see models/README.md)"
    detector = _status("SCRFD det_10g", paths["scrfd"], True, license_if, "InsightFace buffalo_l")
    recognizer = _status("ArcFace w600k_r50", paths["arcface"], True, license_if, "InsightFace buffalo_l")
    swapper = _status("INSwapper 128", paths["inswapper"], True, license_if, "InsightFace inswapper_128.onnx")
    landmark = _status("2D-106 landmark", paths["landmark"], False, license_if, "InsightFace buffalo_l")
    restorer = _status(
        "GFPGAN 1.4",
        paths["gfpgan"],
        False,
        "Apache-2.0 (Tencent ARC GFPGAN)",
        "https://github.com/TencentARC/GFPGAN",
    )
    messages = []
    missing = [m.name for m in (detector, recognizer, swapper) if not m.present]
    if missing:
        messages.append(
            "필수 얼굴 교체 모델이 없습니다: "
            + ", ".join(missing)
            + ". 단순 합성으로 대체하지 않습니다. 모델 다운로드 후 다시 실행하세요."
        )
    if not restorer.present:
        messages.append("GFPGAN 모델이 없어 얼굴 복원은 비활성화됩니다.")
    return ModelBundle(
        ready_for_faceswap=not missing,
        detector=detector,
        recognizer=recognizer,
        swapper=swapper,
        landmark=landmark,
        restorer=restorer,
        messages=messages,
    )


def _download(url: str, dest: Path, progress: ProgressCb | None = None) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    LOGGER.info("downloading %s -> %s", url, dest)
    req = Request(url, headers={"User-Agent": "identity-face-swap-studio/1.0"})
    with urlopen(req, timeout=120) as resp, tmp.open("wb") as handle:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
            done += len(chunk)
            if progress:
                progress(dest.name, done, total)
    tmp.replace(dest)


def _verify(path: Path, expected: str | None) -> None:
    if not expected:
        return
    digest = sha256_file(path)
    if digest.lower() != expected.lower():
        path.unlink(missing_ok=True)
        raise RuntimeError(f"{path.name} checksum mismatch: got {digest}, expected {expected}")
    LOGGER.info("checksum ok %s %s", path.name, digest)


def download_models(progress: ProgressCb | None = None, include_gfpgan: bool = True) -> ModelBundle:
    ensure_runtime_dirs()
    bdir = buffalo_dir()
    bdir.mkdir(parents=True, exist_ok=True)
    needed_buffalo = not (bdir / SCRFD_FILENAME).exists() or not (bdir / ARCFACE_FILENAME).exists()
    if needed_buffalo:
        zip_path = MODELS_DIR / "buffalo_l.zip"
        last_err: Exception | None = None
        for url in MODEL_URLS["buffalo_l.zip"]:
            try:
                _download(url, zip_path, progress)
                last_err = None
                break
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                LOGGER.warning("buffalo_l download failed from %s: %s", url, exc)
        if last_err and not zip_path.exists():
            raise RuntimeError(f"buffalo_l.zip 다운로드 실패: {last_err}")
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(bdir)
        LOGGER.info("extracted buffalo_l to %s", bdir)

    swap_path = MODELS_DIR / INSWAPPER_FILENAME
    if not swap_path.exists():
        last_err = None
        for url in MODEL_URLS[INSWAPPER_FILENAME]:
            try:
                _download(url, swap_path, progress)
                _verify(swap_path, MODEL_CHECKSUMS.get(INSWAPPER_FILENAME))
                last_err = None
                break
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                LOGGER.warning("inswapper download failed from %s: %s", url, exc)
                swap_path.unlink(missing_ok=True)
        if last_err and not swap_path.exists():
            raise RuntimeError(f"inswapper_128.onnx 다운로드 실패: {last_err}")

    if include_gfpgan:
        gfp = MODELS_DIR / GFPGAN_FILENAME
        if not gfp.exists():
            for url in MODEL_URLS[GFPGAN_FILENAME]:
                try:
                    _download(url, gfp, progress)
                    break
                except Exception as exc:  # noqa: BLE001
                    LOGGER.warning("GFPGAN download failed: %s", exc)

    bundle = inspect_models()
    if not bundle.ready_for_faceswap:
        raise RuntimeError("; ".join(bundle.messages))
    return bundle

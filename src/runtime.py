"""Load ONNX sessions and engines once per process."""

from __future__ import annotations

from dataclasses import dataclass

import onnxruntime as ort

from src.face_detector import FaceAnalysis, build_face_analysis
from src.face_swapper import FaceSwapEngine, ModelUnavailable, load_swap_engine
from src.model_manager import inspect_models, model_paths
from src.person_detector import PersonDetector
from src.pipeline import FaceSwapJob
from src.utils import LOGGER


def select_providers() -> list[str]:
    available = list(ort.get_available_providers())
    ordered = []
    for name in ("CUDAExecutionProvider", "DmlExecutionProvider", "CPUExecutionProvider"):
        if name in available:
            ordered.append(name)
    if "CPUExecutionProvider" not in ordered:
        ordered.append("CPUExecutionProvider")
    LOGGER.info("ORT providers available=%s selected=%s", available, ordered)
    return ordered


@dataclass
class RuntimeBundle:
    providers: list[str]
    analysis: FaceAnalysis
    engine: FaceSwapEngine
    person_detector: PersonDetector
    job: FaceSwapJob
    restorer_ready: bool


def create_runtime(det_size: tuple[int, int] = (640, 640), det_thresh: float = 0.42) -> RuntimeBundle:
    bundle = inspect_models()
    if not bundle.ready_for_faceswap:
        raise ModelUnavailable(" ".join(bundle.messages))
    paths = model_paths()
    providers = select_providers()
    analysis = build_face_analysis(
        paths["scrfd"],
        paths["arcface"],
        paths["landmark"] if paths["landmark"].exists() else None,
        providers,
        det_size=det_size,
        det_thresh=det_thresh,
    )
    engine = load_swap_engine(
        paths["inswapper"],
        analysis,
        paths["gfpgan"] if paths["gfpgan"].exists() else None,
        providers,
    )
    person_detector = PersonDetector(analysis)
    job = FaceSwapJob(analysis, engine, person_detector)
    return RuntimeBundle(
        providers=providers,
        analysis=analysis,
        engine=engine,
        person_detector=person_detector,
        job=job,
        restorer_ready=engine.restorer is not None,
    )

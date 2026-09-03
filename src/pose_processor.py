"""Pose conditioning for full-person transform. Disabled unless models + GPU exist."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AdvancedPersonTransformStatus:
    available: bool
    reason: str
    required_vram_gb: float
    required_models: list[str]
    required_packages: list[str]


def person_transform_status(has_cuda: bool, gpu_name: str | None, vram_gb: float | None) -> AdvancedPersonTransformStatus:
    required_models = [
        "OpenPose / DWPose / RTMPose body-hand-face keypoints",
        "Person instance segmentation (SAM or equivalent)",
        "Identity-conditioned generator (InstantID or IP-Adapter FaceID)",
        "Pose ControlNet + temporal video module (AnimateDiff or similar)",
    ]
    required_packages = [
        "torch + torchvision with CUDA",
        "diffusers / controlnet_aux (or equivalent maintained stack)",
        "a licensed identity video model checkpoint",
    ]
    reasons = []
    if not has_cuda:
        reasons.append("현재 실행 환경에 NVIDIA CUDA GPU가 없습니다 (CPU only).")
    elif vram_gb is not None and vram_gb < 8:
        reasons.append(f"VRAM {vram_gb:.1f}GB로는 프레임 단위 확산 모델 전신 변환이 현실적이지 않습니다 (권장 >= 8GB).")
    reasons.append("전신 변환용 생성 모델 체크포인트가 설치되어 있지 않습니다.")
    reasons.append("가짜 의상/체형 필터를 만들어 전체 인물 변환이라고 부르지 않습니다.")
    if gpu_name:
        reasons.append(f"감지된 GPU: {gpu_name}")
    return AdvancedPersonTransformStatus(
        available=False,
        reason=" ".join(reasons),
        required_vram_gb=8.0,
        required_models=required_models,
        required_packages=required_packages,
    )

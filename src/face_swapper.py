"""InsightFace INSwapper inference. This is a real identity-transfer model, not an overlay."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np
import onnx
import onnxruntime as ort
from onnx import numpy_helper

from src.face_detector import Face, FaceAnalysis, norm_crop
from src.profile_blend import (
    estimate_yaw,
    fade_occluded_side,
    profile_mask_range,
    profile_restore,
    soften_profile_edge,
)
from src.utils import LOGGER


class ModelUnavailable(RuntimeError):
    pass


@dataclass
class InferenceRecord:
    frame_index: int
    track_id: int
    model: str
    provider: str
    latency_ms: float
    source_sim_before: float | None = None
    source_sim_after: float | None = None
    used_restore: bool = False


class INSwapper:
    def __init__(self, model_file: str | Path, session: ort.InferenceSession):
        self.model_file = Path(model_file)
        self.session = session
        model = onnx.load(str(self.model_file))
        self.emap = numpy_helper.to_array(model.graph.initializer[-1])
        self.input_mean = 0.0
        self.input_std = 255.0
        inputs = self.session.get_inputs()
        self.input_names = [inp.name for inp in inputs]
        self.output_names = [out.name for out in self.session.get_outputs()]
        input_shape = inputs[0].shape
        self.input_size = tuple(input_shape[2:4][::-1])
        self.call_count = 0
        LOGGER.info("INSwapper loaded %s input=%s", self.model_file.name, self.input_size)

    def source_latent(self, source_face: Face) -> np.ndarray:
        if source_face.normed_embedding is None:
            raise ModelUnavailable("기준 얼굴 임베딩이 없습니다.")
        latent = source_face.normed_embedding.reshape((1, -1))
        latent = np.dot(latent, self.emap)
        latent /= np.linalg.norm(latent)
        return latent.astype(np.float32)

    def swap_aligned(self, aligned_bgr: np.ndarray, latent: np.ndarray) -> np.ndarray:
        blob = cv2.dnn.blobFromImage(
            aligned_bgr,
            1.0 / self.input_std,
            self.input_size,
            (self.input_mean, self.input_mean, self.input_mean),
            swapRB=True,
        )
        pred = self.session.run(self.output_names, {self.input_names[0]: blob, self.input_names[1]: latent})[0]
        self.call_count += 1
        img_fake = pred.transpose((0, 2, 3, 1))[0]
        bgr_fake = np.clip(255 * img_fake, 0, 255).astype(np.uint8)[:, :, ::-1]
        return bgr_fake


class GFPGANRestorer:
    def __init__(self, model_file: str | Path, session: ort.InferenceSession):
        self.model_file = Path(model_file)
        self.session = session
        inp = session.get_inputs()[0]
        self.input_name = inp.name
        self.output_names = [o.name for o in session.get_outputs()]
        self.input_size = 512
        self.call_count = 0
        LOGGER.info("GFPGAN loaded %s", self.model_file.name)

    def enhance(self, face_bgr: np.ndarray) -> np.ndarray:
        size = self.input_size
        resized = cv2.resize(face_bgr, (size, size), interpolation=cv2.INTER_CUBIC)
        rgb = resized[:, :, ::-1].astype(np.float32) / 255.0
        blob = np.transpose(rgb, (2, 0, 1))[None, ...]
        # FaceFusion GFPGAN 1.4 typically uses [0, 1] RGB NCHW.
        out = self.session.run(self.output_names, {self.input_name: blob})[0]
        self.call_count += 1
        if out.ndim == 4:
            out = out[0]
        if out.shape[0] == 3:
            out = np.transpose(out, (1, 2, 0))
        out = np.clip(out, 0.0, 1.0)
        bgr = (out[:, :, ::-1] * 255.0).astype(np.uint8)
        if bgr.shape[:2] != face_bgr.shape[:2]:
            bgr = cv2.resize(bgr, (face_bgr.shape[1], face_bgr.shape[0]), interpolation=cv2.INTER_CUBIC)
        return bgr


def color_match_lab(swapped: np.ndarray, original: np.ndarray, mask: np.ndarray) -> np.ndarray:
    if mask.ndim == 3:
        mask_f = mask[:, :, 0].astype(np.float32) / 255.0
    else:
        mask_f = mask.astype(np.float32)
        if mask_f.max() > 1.0:
            mask_f = mask_f / 255.0
    sel = mask_f > 0.15
    if int(sel.sum()) < 32:
        return swapped
    src = cv2.cvtColor(swapped, cv2.COLOR_BGR2LAB).astype(np.float32)
    dst = cv2.cvtColor(original, cv2.COLOR_BGR2LAB).astype(np.float32)
    for c in range(3):
        s = src[:, :, c][sel]
        d = dst[:, :, c][sel]
        s_mean, s_std = float(s.mean()), float(s.std()) + 1e-6
        d_mean, d_std = float(d.mean()), float(d.std()) + 1e-6
        src[:, :, c] = (src[:, :, c] - s_mean) * (d_std / s_std) + d_mean
    out = cv2.cvtColor(np.clip(src, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)
    mix = mask_f[..., None]
    return (mix * out + (1.0 - mix) * swapped).astype(np.uint8)


def build_face_mask(
    image_shape: tuple[int, int],
    kps: np.ndarray,
    landmarks106: np.ndarray | None,
    mask_range: float,
) -> np.ndarray:
    h, w = image_shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)
    pts = landmarks106 if landmarks106 is not None and len(landmarks106) >= 20 else kps
    hull = cv2.convexHull(pts.astype(np.int32))
    cv2.fillConvexPoly(mask, hull, 255)
    # Expand slightly so hairline / cheeks are covered according to mask_range.
    grow = int(max(3, (1.15 - mask_range) * 18 + mask_range * 28))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (grow | 1, grow | 1))
    mask = cv2.dilate(mask, kernel, iterations=1)
    blur = max(7, (grow * 2 + 1) | 1)
    mask = cv2.GaussianBlur(mask, (blur, blur), 0)
    return mask


def paste_swapped_face(
    frame: np.ndarray,
    fake_bgr: np.ndarray,
    matrix: np.ndarray,
    target_face: Face,
    mask_range: float,
    blend_strength: float,
    color_match: bool = True,
) -> np.ndarray:
    h, w = frame.shape[:2]
    inverse = cv2.invertAffineTransform(matrix)
    warped = cv2.warpAffine(fake_bgr, inverse, (w, h), borderValue=0.0)
    white = np.full(fake_bgr.shape[:2], 255, dtype=np.uint8)
    warped_white = cv2.warpAffine(white, inverse, (w, h), borderValue=0)
    model_mask = (warped_white > 20).astype(np.uint8) * 255
    k = max(int(np.sqrt(max(1, int((model_mask > 0).sum()))) // 12), 8)
    model_mask = cv2.erode(model_mask, np.ones((k, k), np.uint8), iterations=1)
    model_mask = cv2.GaussianBlur(model_mask, (k * 2 + 1, k * 2 + 1), 0)

    landmark_mask = build_face_mask(frame.shape, target_face.kps, target_face.landmarks106, mask_range)
    mask = np.minimum(model_mask, landmark_mask)
    yaw = estimate_yaw(target_face.kps)
    mask = fade_occluded_side(mask, target_face.box, yaw)
    mask = soften_profile_edge(mask, yaw)
    if color_match:
        warped = color_match_lab(warped, frame, mask)
    alpha = (mask.astype(np.float32) / 255.0) * float(np.clip(blend_strength, 0.0, 1.0))
    alpha = alpha[..., None]
    merged = alpha * warped.astype(np.float32) + (1.0 - alpha) * frame.astype(np.float32)
    return np.clip(merged, 0, 255).astype(np.uint8)


class FaceSwapEngine:
    def __init__(
        self,
        analysis: FaceAnalysis,
        swapper: INSwapper,
        restorer: GFPGANRestorer | None,
        provider: str,
    ):
        self.analysis = analysis
        self.swapper = swapper
        self.restorer = restorer
        self.provider = provider
        self.records: list[InferenceRecord] = []

    def build_source_face(self, images_bgr: list[np.ndarray]) -> Face:
        embeddings = []
        best: Face | None = None
        for image in images_bgr:
            faces = self.analysis.get(image)
            if not faces:
                continue
            faces.sort(key=lambda f: (f.box[2] - f.box[0]) * (f.box[3] - f.box[1]), reverse=True)
            chosen = faces[0]
            if chosen.normed_embedding is not None:
                embeddings.append(chosen.normed_embedding)
            if best is None:
                best = chosen
        if best is None or not embeddings:
            raise ModelUnavailable(
                "기준 이미지에서 얼굴을 검출하지 못했습니다. 정면/측면이 보이는 인물 사진을 사용하세요."
            )
        mean = np.mean(np.stack(embeddings, axis=0), axis=0)
        mean = mean / (np.linalg.norm(mean) + 1e-8)
        best.embedding = mean.astype(np.float32)
        return best

    def swap_face(
        self,
        frame: np.ndarray,
        target: Face,
        source: Face,
        *,
        frame_index: int,
        track_id: int,
        mask_range: float,
        blend_strength: float,
        restore_strength: float,
    ) -> tuple[np.ndarray, InferenceRecord]:
        t0 = time.perf_counter()
        yaw = estimate_yaw(target.kps)
        mask_range = profile_mask_range(yaw, mask_range)
        restore_strength = profile_restore(yaw, restore_strength)
        aligned, matrix = norm_crop(frame, target.kps, self.swapper.input_size[0])
        latent = self.swapper.source_latent(source)
        fake = self.swapper.swap_aligned(aligned, latent)
        used_restore = False
        if self.restorer is not None and restore_strength > 0.01:
            try:
                restored = self.restorer.enhance(fake)
                fake = cv2.addWeighted(fake, 1.0 - restore_strength, restored, restore_strength, 0)
                used_restore = True
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("GFPGAN 복원 실패, 교체 결과만 사용: %s", exc)
        result = paste_swapped_face(frame, fake, matrix, target, mask_range, blend_strength)
        latency = (time.perf_counter() - t0) * 1000.0
        rec = InferenceRecord(
            frame_index=frame_index,
            track_id=track_id,
            model=self.swapper.model_file.name,
            provider=self.provider,
            latency_ms=latency,
            used_restore=used_restore,
        )
        self.records.append(rec)
        LOGGER.info(
            "INSWAPPER_INFERENCE frame=%s track=%s model=%s provider=%s latency_ms=%.1f restore=%s",
            frame_index,
            track_id,
            rec.model,
            rec.provider,
            rec.latency_ms,
            used_restore,
        )
        return result, rec


def load_swap_engine(
    swapper_path: Path,
    analysis: FaceAnalysis,
    restorer_path: Path | None,
    providers: list[str],
) -> FaceSwapEngine:
    if not swapper_path.exists():
        raise ModelUnavailable(
            f"inswapper 모델이 없습니다: {swapper_path}. "
            "단순 오버레이로 대체하지 않습니다. 모델을 다운로드하세요."
        )
    so = ort.SessionOptions()
    so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    session = ort.InferenceSession(str(swapper_path), so, providers=providers)
    swapper = INSwapper(swapper_path, session)
    restorer = None
    if restorer_path and restorer_path.exists():
        try:
            restorer = GFPGANRestorer(
                restorer_path, ort.InferenceSession(str(restorer_path), so, providers=providers)
            )
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("GFPGAN 세션 생성 실패: %s", exc)
    provider = session.get_providers()[0] if session.get_providers() else "CPUExecutionProvider"
    return FaceSwapEngine(analysis, swapper, restorer, provider)

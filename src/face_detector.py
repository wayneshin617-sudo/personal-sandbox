"""SCRFD face detector + ArcFace embeddings. No Haar cascades."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

from src.utils import LOGGER, clip_box, expand_face_to_person_box, hsv_histogram


ARCFACE_DST = np.array(
    [
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041],
    ],
    dtype=np.float32,
)


def estimate_norm(lmk: np.ndarray, image_size: int = 112) -> np.ndarray:
    assert lmk.shape == (5, 2)
    if image_size % 112 == 0:
        ratio = float(image_size) / 112.0
        diff_x = 0.0
    else:
        ratio = float(image_size) / 128.0
        diff_x = 8.0 * ratio
    dst = ARCFACE_DST * ratio
    dst[:, 0] += diff_x
    matrix, _ = cv2.estimateAffinePartial2D(lmk.astype(np.float32), dst, method=cv2.LMEDS)
    if matrix is None:
        matrix = cv2.getAffineTransform(lmk[:3].astype(np.float32), dst[:3])
    return matrix


def norm_crop(img: np.ndarray, landmark: np.ndarray, image_size: int = 112) -> tuple[np.ndarray, np.ndarray]:
    matrix = estimate_norm(landmark, image_size)
    warped = cv2.warpAffine(img, matrix, (image_size, image_size), borderValue=0.0)
    return warped, matrix


def distance2bbox(points: np.ndarray, distance: np.ndarray) -> np.ndarray:
    x1 = points[:, 0] - distance[:, 0]
    y1 = points[:, 1] - distance[:, 1]
    x2 = points[:, 0] + distance[:, 2]
    y2 = points[:, 1] + distance[:, 3]
    return np.stack([x1, y1, x2, y2], axis=-1)


def distance2kps(points: np.ndarray, distance: np.ndarray) -> np.ndarray:
    preds = []
    for i in range(0, distance.shape[1], 2):
        px = points[:, i % 2] + distance[:, i]
        py = points[:, i % 2 + 1] + distance[:, i + 1]
        preds.append(px)
        preds.append(py)
    return np.stack(preds, axis=-1)


@dataclass
class Face:
    box: list[float]
    score: float
    kps: np.ndarray
    embedding: np.ndarray | None = None
    person_box: list[float] | None = None
    histogram: np.ndarray | None = None
    landmarks106: np.ndarray | None = None

    @property
    def normed_embedding(self) -> np.ndarray | None:
        if self.embedding is None:
            return None
        vec = np.asarray(self.embedding, dtype=np.float32).ravel()
        nrm = float(np.linalg.norm(vec))
        return vec / nrm if nrm > 0 else vec


class SCRFD:
    def __init__(self, model_file: str | Path, session: ort.InferenceSession):
        self.model_file = Path(model_file)
        self.session = session
        self.center_cache: dict[tuple[int, int, int], np.ndarray] = {}
        self.nms_thresh = 0.4
        self.det_thresh = 0.5
        self.input_size = (640, 640)
        self._init_vars()

    def _init_vars(self) -> None:
        inp = self.session.get_inputs()[0]
        self.input_name = inp.name
        self.output_names = [o.name for o in self.session.get_outputs()]
        outputs = self.session.get_outputs()
        self.batched = len(outputs[0].shape) == 3
        self.input_mean = 127.5
        self.input_std = 128.0
        self.use_kps = False
        self._num_anchors = 1
        if len(outputs) == 6:
            self.fmc = 3
            self._feat_stride_fpn = [8, 16, 32]
            self._num_anchors = 2
        elif len(outputs) == 9:
            self.fmc = 3
            self._feat_stride_fpn = [8, 16, 32]
            self._num_anchors = 2
            self.use_kps = True
        elif len(outputs) == 10:
            self.fmc = 5
            self._feat_stride_fpn = [8, 16, 32, 64, 128]
        elif len(outputs) == 15:
            self.fmc = 5
            self._feat_stride_fpn = [8, 16, 32, 64, 128]
            self.use_kps = True
        else:
            raise RuntimeError(f"지원하지 않는 SCRFD 출력 개수: {len(outputs)}")

    def nms(self, dets: np.ndarray) -> list[int]:
        thresh = self.nms_thresh
        x1, y1, x2, y2, scores = dets[:, 0], dets[:, 1], dets[:, 2], dets[:, 3], dets[:, 4]
        areas = (x2 - x1 + 1) * (y2 - y1 + 1)
        order = scores.argsort()[::-1]
        keep: list[int] = []
        while order.size > 0:
            i = int(order[0])
            keep.append(i)
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])
            w = np.maximum(0.0, xx2 - xx1 + 1)
            h = np.maximum(0.0, yy2 - yy1 + 1)
            inter = w * h
            ovr = inter / (areas[i] + areas[order[1:]] - inter)
            order = order[np.where(ovr <= thresh)[0] + 1]
        return keep

    def forward(self, img: np.ndarray, threshold: float):
        input_size = tuple(img.shape[0:2][::-1])
        blob = cv2.dnn.blobFromImage(
            img,
            1.0 / self.input_std,
            input_size,
            (self.input_mean, self.input_mean, self.input_mean),
            swapRB=True,
        )
        net_outs = self.session.run(self.output_names, {self.input_name: blob})
        input_height, input_width = blob.shape[2], blob.shape[3]
        scores_list, bboxes_list, kpss_list = [], [], []
        fmc = self.fmc
        for idx, stride in enumerate(self._feat_stride_fpn):
            if self.batched:
                scores = net_outs[idx][0]
                bbox_preds = net_outs[idx + fmc][0] * stride
                kps_preds = net_outs[idx + fmc * 2][0] * stride if self.use_kps else None
            else:
                scores = net_outs[idx]
                bbox_preds = net_outs[idx + fmc] * stride
                kps_preds = net_outs[idx + fmc * 2] * stride if self.use_kps else None
            height = input_height // stride
            width = input_width // stride
            key = (height, width, stride)
            if key in self.center_cache:
                anchor_centers = self.center_cache[key]
            else:
                anchor_centers = np.stack(np.mgrid[:height, :width][::-1], axis=-1).astype(np.float32)
                anchor_centers = (anchor_centers * stride).reshape((-1, 2))
                if self._num_anchors > 1:
                    anchor_centers = np.stack([anchor_centers] * self._num_anchors, axis=1).reshape((-1, 2))
                if len(self.center_cache) < 100:
                    self.center_cache[key] = anchor_centers
            pos_inds = np.where(scores >= threshold)[0]
            bboxes = distance2bbox(anchor_centers, bbox_preds)
            scores_list.append(scores[pos_inds])
            bboxes_list.append(bboxes[pos_inds])
            if self.use_kps and kps_preds is not None:
                kpss = distance2kps(anchor_centers, kps_preds).reshape((anchor_centers.shape[0], -1, 2))
                kpss_list.append(kpss[pos_inds])
        return scores_list, bboxes_list, kpss_list

    def detect(self, img: np.ndarray, input_size: tuple[int, int] | None = None, max_num: int = 0):
        input_size = input_size or self.input_size
        im_ratio = float(img.shape[0]) / img.shape[1]
        model_ratio = float(input_size[1]) / input_size[0]
        if im_ratio > model_ratio:
            new_height = input_size[1]
            new_width = int(new_height / im_ratio)
        else:
            new_width = input_size[0]
            new_height = int(new_width * im_ratio)
        det_scale = float(new_height) / img.shape[0]
        resized_img = cv2.resize(img, (new_width, new_height))
        det_img = np.zeros((input_size[1], input_size[0], 3), dtype=np.uint8)
        det_img[:new_height, :new_width, :] = resized_img
        scores_list, bboxes_list, kpss_list = self.forward(det_img, self.det_thresh)
        if not scores_list or sum(s.size for s in scores_list) == 0:
            return np.empty((0, 5), dtype=np.float32), np.empty((0, 5, 2), dtype=np.float32)
        scores = np.vstack(scores_list)
        order = scores.ravel().argsort()[::-1]
        bboxes = np.vstack(bboxes_list) / det_scale
        kpss = np.vstack(kpss_list) / det_scale if self.use_kps and kpss_list else None
        pre_det = np.hstack((bboxes, scores)).astype(np.float32)
        pre_det = pre_det[order, :]
        if kpss is not None:
            kpss = kpss[order, :, :]
        keep = self.nms(pre_det)
        det = pre_det[keep, :]
        if kpss is not None:
            kpss = kpss[keep, :, :]
        if max_num > 0 and det.shape[0] > max_num:
            det = det[:max_num]
            if kpss is not None:
                kpss = kpss[:max_num]
        return det, kpss


class ArcFace:
    def __init__(self, model_file: str | Path, session: ort.InferenceSession):
        self.session = session
        self.model_file = Path(model_file)
        inp = session.get_inputs()[0]
        self.input_name = inp.name
        self.input_size = tuple(inp.shape[2:4][::-1])
        self.output_names = [o.name for o in session.get_outputs()]
        self.input_mean = 127.5
        self.input_std = 127.5

    def get_feat(self, aligned_bgr: np.ndarray) -> np.ndarray:
        blob = cv2.dnn.blobFromImage(
            aligned_bgr,
            1.0 / self.input_std,
            self.input_size,
            (self.input_mean, self.input_mean, self.input_mean),
            swapRB=True,
        )
        feat = self.session.run(self.output_names, {self.input_name: blob})[0]
        return feat.flatten().astype(np.float32)


class Landmark106:
    def __init__(self, model_file: str | Path, session: ort.InferenceSession):
        self.session = session
        self.model_file = Path(model_file)
        inp = session.get_inputs()[0]
        self.input_name = inp.name
        self.input_size = tuple(inp.shape[2:4][::-1]) if len(inp.shape) >= 4 else (192, 192)
        self.output_names = [o.name for o in session.get_outputs()]

    def get(self, image_bgr: np.ndarray, box: list[float]) -> np.ndarray | None:
        x1, y1, x2, y2 = [int(v) for v in box]
        w, h = max(1, x2 - x1), max(1, y2 - y1)
        cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        scale = max(w, h) * 1.5
        half = scale / 2.0
        sx1, sy1 = int(cx - half), int(cy - half)
        sx2, sy2 = int(cx + half), int(cy + half)
        crop = np.zeros((int(scale), int(scale), 3), dtype=np.uint8)
        src = image_bgr[max(0, sy1) : max(0, sy2), max(0, sx1) : max(0, sx2)]
        dy1, dx1 = max(0, -sy1), max(0, -sx1)
        if src.size == 0:
            return None
        crop[dy1 : dy1 + src.shape[0], dx1 : dx1 + src.shape[1]] = src
        size = self.input_size[0]
        resized = cv2.resize(crop, (size, size))
        blob = cv2.dnn.blobFromImage(resized, 1.0 / 127.5, (size, size), (127.5, 127.5, 127.5), swapRB=True)
        pred = self.session.run(self.output_names, {self.input_name: blob})[0].reshape((-1, 2))
        pred = (pred + 1.0) * 0.5 * scale
        pred[:, 0] += sx1
        pred[:, 1] += sy1
        return pred.astype(np.float32)


@dataclass
class FaceAnalysis:
    detector: SCRFD
    recognizer: ArcFace
    landmark: Landmark106 | None = None
    providers: list[str] = field(default_factory=list)
    inference_calls: int = 0

    def get(self, image_bgr: np.ndarray, det_thresh: float | None = None, max_num: int = 0) -> list[Face]:
        if det_thresh is not None:
            self.detector.det_thresh = det_thresh
        h, w = image_bgr.shape[:2]
        bboxes, kpss = self.detector.detect(image_bgr, max_num=max_num)
        self.inference_calls += 1
        faces: list[Face] = []
        if bboxes is None or len(bboxes) == 0:
            return faces
        for i, bbox in enumerate(bboxes):
            box = clip_box(bbox[:4].tolist(), w, h)
            kps = kpss[i] if kpss is not None and i < len(kpss) else None
            if kps is None:
                continue
            aligned, _ = norm_crop(image_bgr, kps, 112)
            embedding = self.recognizer.get_feat(aligned)
            self.inference_calls += 1
            face = Face(
                box=box,
                score=float(bbox[4]),
                kps=np.asarray(kps, dtype=np.float32),
                embedding=embedding,
                person_box=expand_face_to_person_box(box, w, h),
                histogram=hsv_histogram(image_bgr, expand_face_to_person_box(box, w, h)),
            )
            if self.landmark is not None:
                try:
                    face.landmarks106 = self.landmark.get(image_bgr, box)
                    self.inference_calls += 1
                except Exception as exc:  # noqa: BLE001
                    LOGGER.debug("landmark failed: %s", exc)
            faces.append(face)
        return faces


def build_face_analysis(
    scrfd_path: Path,
    arcface_path: Path,
    landmark_path: Path | None,
    providers: list[str],
    det_size: tuple[int, int] = (640, 640),
    det_thresh: float = 0.5,
) -> FaceAnalysis:
    so = ort.SessionOptions()
    so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    det_sess = ort.InferenceSession(str(scrfd_path), so, providers=providers)
    rec_sess = ort.InferenceSession(str(arcface_path), so, providers=providers)
    detector = SCRFD(scrfd_path, det_sess)
    detector.input_size = det_size
    detector.det_thresh = det_thresh
    recognizer = ArcFace(arcface_path, rec_sess)
    landmark = None
    if landmark_path and landmark_path.exists():
        try:
            landmark = Landmark106(landmark_path, ort.InferenceSession(str(landmark_path), so, providers=providers))
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("2d106 landmark 로드 실패, 5점 랜드마크만 사용: %s", exc)
    LOGGER.info("FaceAnalysis providers=%s det=%s rec=%s", providers, scrfd_path.name, arcface_path.name)
    return FaceAnalysis(detector=detector, recognizer=recognizer, landmark=landmark, providers=providers)

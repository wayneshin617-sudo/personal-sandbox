"""Person candidates derived from SCRFD faces (expanded body boxes).

A dedicated YOLO/RTMDet person detector is optional. When it is not installed we
still expose every detected face as a selectable person. We do not invent a
fake full-body detector.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.face_detector import Face, FaceAnalysis
from src.tracker import Detection
from src.utils import expand_face_to_person_box, hsv_histogram


@dataclass
class PersonCandidate:
    index: int
    face: Face
    person_box: list[float]
    label: str


class PersonDetector:
    def __init__(self, analysis: FaceAnalysis):
        self.analysis = analysis
        self.backend = "insightface-scrfd-face-as-person"
        self.full_body_model_available = False
        self.unavailable_reason = (
            "전용 다중 인물 검출기(YOLO-Pose/RTMDet)는 이 환경에 설치되어 있지 않습니다. "
            "선택 UI는 SCRFD가 찾은 각 얼굴을 인물 후보로 표시하고, "
            "표시용 몸 박스는 얼굴 박스를 아래로 확장한 근사입니다. "
            "이 근사를 전신 segmentation이라고 부르지 않습니다."
        )

    def detect_faces(self, image_bgr: np.ndarray) -> list[Face]:
        return self.analysis.get(image_bgr)

    def candidates(self, image_bgr: np.ndarray) -> list[PersonCandidate]:
        h, w = image_bgr.shape[:2]
        faces = self.detect_faces(image_bgr)
        out: list[PersonCandidate] = []
        for i, face in enumerate(faces):
            pbox = face.person_box or expand_face_to_person_box(face.box, w, h)
            out.append(PersonCandidate(index=i + 1, face=face, person_box=pbox, label=f"Person {i + 1}"))
        return out

    def to_detections(self, image_bgr: np.ndarray, faces: list[Face] | None = None) -> list[Detection]:
        h, w = image_bgr.shape[:2]
        faces = faces if faces is not None else self.detect_faces(image_bgr)
        dets: list[Detection] = []
        for face in faces:
            pbox = face.person_box or expand_face_to_person_box(face.box, w, h)
            dets.append(
                Detection(
                    box=list(face.box),
                    score=face.score,
                    kps=face.kps,
                    embedding=face.normed_embedding,
                    histogram=face.histogram if face.histogram is not None else hsv_histogram(image_bgr, pbox),
                    person_box=pbox,
                )
            )
        return dets

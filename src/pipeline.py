"""End-to-end face-swap job: replace every detected face with the reference identity."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from shutil import copy2
from typing import Callable

import cv2
import numpy as np

from config import OUTPUTS_DIR, WATERMARK_TEXT
from src.export_manager import ExportPlan, finalize_output, suffix_for_container
from src.face_detector import Face, FaceAnalysis
from src.face_swapper import FaceSwapEngine, InferenceRecord
from src.media_probe import MediaInfo, probe_and_validate_video
from src.person_detector import PersonDetector
from src.target_selector import Selection
from src.utils import (
    LOGGER,
    ProgressEvent,
    cleanup_work_dir,
    cosine_similarity,
    make_work_dir,
    unique_path,
    write_json,
)
from src.validators import validate_output_media
from src.video_io import VideoFrameReader, VideoFrameWriter


ProgressCb = Callable[[ProgressEvent], None]


def draw_watermark(frame: np.ndarray, text: str = WATERMARK_TEXT) -> np.ndarray:
    out = frame.copy()
    h, w = out.shape[:2]
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = max(0.35, min(w, h) / 1400.0)
    thickness = 1
    (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
    x, y = 8, h - 8
    cv2.rectangle(out, (x - 4, y - th - 6), (x + tw + 4, y + 4), (0, 0, 0), -1)
    cv2.putText(out, text, (x, y), font, scale, (230, 230, 230), thickness, cv2.LINE_AA)
    return out


@dataclass
class JobConfig:
    source_video: Path
    reference_images: list[Path]
    plan: ExportPlan
    selection: Selection | None = None
    start_sec: float = 0.0
    end_sec: float | None = None
    track_thresh: float = 0.35
    reid_thresh: float = 0.45
    mask_range: float = 0.70
    blend_strength: float = 0.90
    restore_strength: float = 0.32
    watermark: bool = True
    purpose_note: str = ""
    output_dir: Path = OUTPUTS_DIR


@dataclass
class JobResult:
    ok: bool
    output_path: Path | None
    message: str
    frames_total: int = 0
    frames_swapped: int = 0
    frames_kept_original: int = 0
    track_id: int | None = None
    inference_count: int = 0
    inference_log: list[dict] = field(default_factory=list)
    similarity_samples: list[dict] = field(default_factory=list)
    validation: dict | None = None
    source_probe: dict | None = None
    output_probe: dict | None = None
    log_path: Path | None = None


class FaceSwapJob:
    def __init__(
        self,
        analysis: FaceAnalysis,
        engine: FaceSwapEngine,
        person_detector: PersonDetector,
    ):
        self.analysis = analysis
        self.engine = engine
        self.person_detector = person_detector

    def run(self, cfg: JobConfig, progress: ProgressCb | None = None) -> JobResult:
        from src.image_io import load_image

        work = make_work_dir("swap")
        try:
            source_info = probe_and_validate_video(cfg.source_video)
            if not source_info.decode_ok:
                return JobResult(False, None, source_info.decode_error or "원본 영상을 열 수 없습니다.")

            refs: list[np.ndarray] = []
            for path in cfg.reference_images:
                loaded = load_image(path)
                if not loaded.ok or loaded.image_bgr is None:
                    return JobResult(False, None, f"기준 이미지 거부: {loaded.error}")
                refs.append(loaded.image_bgr)
            source_face = self.engine.build_source_face(refs)
            LOGGER.info("source identity embedding norm=%.3f refs=%s", float(np.linalg.norm(source_face.embedding)), len(refs))

            out_w, out_h = cfg.plan.width, cfg.plan.height
            fps = cfg.plan.fps
            silent_path = work / f"silent{suffix_for_container(cfg.plan.container)}"
            dest = unique_path(cfg.output_dir, cfg.plan.output_name, suffix_for_container(cfg.plan.container))
            if progress:
                progress(ProgressEvent(current=0, total=1, message="준비 중"))

            frames_total = 0
            frames_swapped = 0
            frames_kept = 0
            samples: list[dict] = []
            estimated = 0
            duration = source_info.duration or 0.0
            span = (cfg.end_sec - cfg.start_sec) if cfg.end_sec else max(0.0, duration - cfg.start_sec)
            if source_info.avg_fps and span:
                estimated = int(round(span * source_info.avg_fps))

            with VideoFrameReader(
                cfg.source_video,
                info=source_info,
                start_sec=cfg.start_sec,
                end_sec=cfg.end_sec,
            ) as reader, VideoFrameWriter(
                silent_path,
                width=out_w,
                height=out_h,
                fps=fps,
                video_encoder=cfg.plan.video_encoder,
                lossless=cfg.plan.lossless,
                high_quality=cfg.plan.high_quality,
                extra_args=cfg.plan.extra_args,
            ) as writer:
                for packet in reader.frames():
                    frame = packet.image_bgr
                    faces = self.person_detector.detect_faces(frame)
                    out = frame
                    swapped_this = 0
                    for face_i, target_face in enumerate(faces, start=1):
                        if target_face.kps is None:
                            continue
                        out, rec = self.engine.swap_face(
                            out,
                            target_face,
                            source_face,
                            frame_index=packet.index,
                            track_id=face_i,
                            mask_range=cfg.mask_range,
                            blend_strength=cfg.blend_strength,
                            restore_strength=cfg.restore_strength,
                        )
                        swapped_this += 1
                        if (packet.index % 8 == 0 or packet.index < 2) and face_i == 1:
                            after_faces = self.analysis.get(out)
                            sample = _similarity_sample(
                                after_faces,
                                faces,
                                target_face,
                                source_face,
                                face_i,
                                packet.index,
                            )
                            if sample:
                                samples.append(sample)
                                rec.source_sim_before = sample.get("target_to_source_before")
                                rec.source_sim_after = sample.get("target_to_source_after")
                    if swapped_this:
                        frames_swapped += 1
                    else:
                        frames_kept += 1
                        if packet.index % 30 == 0:
                            LOGGER.info("KEEP_ORIGINAL frame=%s reason=no-face", packet.index)

                    if cfg.watermark:
                        out = draw_watermark(out)
                    if (out.shape[1], out.shape[0]) != (out_w, out_h):
                        out = cv2.resize(out, (out_w, out_h), interpolation=cv2.INTER_LINEAR)
                    writer.write(out)
                    frames_total += 1
                    if progress:
                        total = max(estimated, frames_total)
                        progress(
                            ProgressEvent(
                                current=frames_total,
                                total=total,
                                message=f"얼굴 바꾸는 중 {frames_total} / {total} · 적용 {frames_swapped}",
                                extra={"swapped_faces": swapped_this},
                            )
                        )

            if frames_total <= 0:
                return JobResult(False, None, "처리된 프레임이 없습니다.")

            if progress:
                progress(ProgressEvent(current=1, total=1, message="영상 저장 중"))
            try:
                dest = finalize_output(silent_path, cfg.source_video, dest, cfg.plan, source_info)
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("finalize failed")
                if silent_path.exists():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    copy2(silent_path, dest)
                    LOGGER.warning("saved video without remux after finalize error: %s", exc)
                else:
                    raise
            expect_audio = bool(source_info.has_audio) and not cfg.plan.drop_audio
            validation = validate_output_media(
                dest,
                source=source_info if cfg.end_sec is None and cfg.start_sec <= 0 else None,
                expect_audio=expect_audio,
                min_frames=1,
            )
            records = [
                {
                    "frame_index": r.frame_index,
                    "track_id": r.track_id,
                    "model": r.model,
                    "provider": r.provider,
                    "latency_ms": r.latency_ms,
                    "source_sim_before": r.source_sim_before,
                    "source_sim_after": r.source_sim_after,
                    "used_restore": r.used_restore,
                }
                for r in self.engine.records
            ]
            log_path = dest.with_suffix(dest.suffix + ".inference.json")
            write_json(
                log_path,
                {
                    "purpose_note": cfg.purpose_note,
                    "track_id": None,
                    "frames_total": frames_total,
                    "frames_swapped": frames_swapped,
                    "frames_kept_original": frames_kept,
                    "inswapper_calls": self.engine.swapper.call_count,
                    "records": records,
                    "similarity_samples": samples,
                },
            )
            from src.media_probe import probe_media

            out_info = probe_media(dest)
            dest_ok = bool(dest.exists() and dest.stat().st_size > 0)
            ok = dest_ok and (self.engine.swapper.call_count > 0 or frames_total > 0)
            if dest_ok and self.engine.swapper.call_count <= 0:
                message = "영상은 저장됐습니다. 이 구간에서 얼굴을 찾지 못해 원본이 남았습니다."
            elif dest_ok:
                message = (
                    f"완료. {frames_total}장 중 {frames_swapped}장에서 얼굴을 바꿨습니다. "
                    "영상 받기로 저장하세요."
                )
            else:
                message = validation.message or "결과를 저장하지 못했습니다."
            return JobResult(
                ok=ok,
                output_path=dest if dest.exists() else None,
                message=message,
                frames_total=frames_total,
                frames_swapped=frames_swapped,
                frames_kept_original=frames_kept,
                track_id=None,
                inference_count=self.engine.swapper.call_count,
                inference_log=records,
                similarity_samples=samples,
                validation=validation.details,
                source_probe=source_info.to_dict(),
                output_probe=out_info.to_dict(),
                log_path=log_path,
            )
        finally:
            cleanup_work_dir(work)


def _similarity_sample(
    after_faces: list[Face],
    before_faces: list[Face],
    target_before: Face,
    source_face: Face,
    track_id: int,
    frame_index: int,
) -> dict | None:
    if target_before.normed_embedding is None or source_face.normed_embedding is None:
        return None
    before_sim = cosine_similarity(target_before.normed_embedding, source_face.normed_embedding)
    after_sim = None
    # Match the swapped face by location, not by "largest face".
    best = None
    best_d = 1e18
    tx = (target_before.box[0] + target_before.box[2]) * 0.5
    ty = (target_before.box[1] + target_before.box[3]) * 0.5
    for face in after_faces:
        cx = (face.box[0] + face.box[2]) * 0.5
        cy = (face.box[1] + face.box[3]) * 0.5
        d = (cx - tx) ** 2 + (cy - ty) ** 2
        if d < best_d:
            best_d = d
            best = face
    if best is not None and best.normed_embedding is not None:
        after_sim = cosine_similarity(best.normed_embedding, source_face.normed_embedding)
    other_before = []
    other_after = []
    for face in before_faces:
        if face is target_before:
            continue
        other_before.append(face.normed_embedding)
    return {
        "frame_index": frame_index,
        "track_id": track_id,
        "target_to_source_before": before_sim,
        "target_to_source_after": after_sim,
        "other_faces_before": len(before_faces) - 1,
        "other_faces_after": max(0, len(after_faces) - 1),
    }

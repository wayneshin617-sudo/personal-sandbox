"""Launch identity-swap jobs in a process that survives Streamlit reloads."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from src.export_manager import ExportPlan
from src import job_store
from src.job_store import refresh_job, replace_job, write_job
from src.pipeline import JobConfig, JobResult


def config_to_payload(config: JobConfig, source_sig: str) -> dict:
    return {
        "source_video": str(Path(config.source_video)),
        "reference_images": [str(Path(p)) for p in config.reference_images],
        "plan": asdict(config.plan),
        "start_sec": float(config.start_sec),
        "end_sec": config.end_sec,
        "mask_range": float(config.mask_range),
        "blend_strength": float(config.blend_strength),
        "restore_strength": float(config.restore_strength),
        "watermark": bool(config.watermark),
        "purpose_note": config.purpose_note,
        "output_dir": str(Path(config.output_dir)),
        "source_sig": source_sig,
    }


def payload_to_config(payload: dict) -> JobConfig:
    plan_data = dict(payload["plan"])
    plan_data["extra_args"] = list(plan_data.get("extra_args") or [])
    plan_data["warnings"] = list(plan_data.get("warnings") or [])
    return JobConfig(
        source_video=Path(payload["source_video"]),
        reference_images=[Path(p) for p in payload.get("reference_images") or []],
        plan=ExportPlan(**plan_data),
        start_sec=float(payload.get("start_sec") or 0.0),
        end_sec=payload.get("end_sec"),
        mask_range=float(payload.get("mask_range") or 0.70),
        blend_strength=float(payload.get("blend_strength") or 0.90),
        restore_strength=float(payload.get("restore_strength") or 0.32),
        watermark=bool(payload.get("watermark", True)),
        purpose_note=str(payload.get("purpose_note") or ""),
        output_dir=Path(payload.get("output_dir") or "outputs"),
    )


def start_job(config: JobConfig, source_sig: str) -> dict:
    video_path = Path(config.source_video)
    if not video_path.is_file():
        raise FileNotFoundError(f"video not found: {video_path}")
    refs = [Path(p) for p in config.reference_images]
    if not refs or any(not path.is_file() for path in refs):
        raise FileNotFoundError("identity photo not found")

    existing = refresh_job()
    if existing and existing.get("status") == "running":
        raise RuntimeError("이미 생성이 진행 중입니다.")

    payload = config_to_payload(config, source_sig)
    job_store.JOB_DIR.mkdir(parents=True, exist_ok=True)
    job_store.PAYLOAD_PATH.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    replace_job(
        {
            "status": "running",
            "stage": "queued",
            "detail": "백그라운드에서 생성 시작",
            "message": "백그라운드에서 생성 시작",
            "pid": None,
            "current_frame": 0,
            "total_frames": 0,
            "source_sig": source_sig,
            "output_path": "",
            "error": "",
        }
    )

    script = Path(__file__).resolve().parent.parent / "scripts" / "run_studio_job.py"
    log_file = job_store.LOG_PATH.open("ab")
    proc = subprocess.Popen(
        [sys.executable, str(script), str(job_store.PAYLOAD_PATH)],
        cwd=str(Path(__file__).resolve().parent.parent),
        stdout=log_file,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    return write_job(
        {
            "status": "running",
            "stage": "queued",
            "detail": "백그라운드 작업 시작됨",
            "message": "백그라운드 작업 시작됨",
            "pid": proc.pid,
            "source_sig": source_sig,
        }
    )


def running_job() -> dict | None:
    job = refresh_job()
    if job and job.get("status") == "running":
        return job
    return None


def latest_result_for(source_sig: str) -> JobResult | None:
    job = refresh_job()
    if not job or job.get("status") != "done":
        return None
    if job.get("source_sig") != source_sig:
        return None
    path = Path(str(job.get("output_path") or ""))
    if not path.is_file() or path.stat().st_size <= 0:
        return None
    return JobResult(
        ok=True,
        output_path=path,
        message=str(job.get("message") or job.get("detail") or "완료"),
        frames_total=int(job.get("frames_total") or job.get("frames") or 0),
        frames_swapped=int(job.get("frames_swapped") or 0),
        inference_count=int(job.get("inference_count") or job.get("swap_inferences") or 0),
    )

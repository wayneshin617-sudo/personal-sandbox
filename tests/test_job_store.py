from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from src.export_manager import ExportPlan
from src.job_runner import config_to_payload, latest_result_for, payload_to_config, start_job
from src.job_store import pid_alive, refresh_job, replace_job, write_job
from src.pipeline import JobConfig


def _patch_store(monkeypatch, tmp_path: Path) -> None:
    from src import job_store

    monkeypatch.setattr(job_store, "JOB_DIR", tmp_path)
    monkeypatch.setattr(job_store, "JOB_PATH", tmp_path / "current.json")
    monkeypatch.setattr(job_store, "PAYLOAD_PATH", tmp_path / "payload.json")
    monkeypatch.setattr(job_store, "LOG_PATH", tmp_path / "current.log")


def _sample_config(tmp_path: Path) -> JobConfig:
    video = tmp_path / "clip.mp4"
    face = tmp_path / "face.png"
    video.write_bytes(b"video")
    face.write_bytes(b"face")
    plan = ExportPlan(
        container="mp4",
        video_encoder="libx264",
        audio_encoder="aac",
        fps=25.0,
        width=1280,
        height=720,
        lossless=False,
        high_quality=True,
        drop_audio=False,
        extra_args=["-movflags", "+faststart"],
        warnings=["auto"],
        output_name="studio",
    )
    return JobConfig(
        source_video=video,
        reference_images=[face],
        plan=plan,
        watermark=True,
        output_dir=tmp_path / "out",
    )


def test_write_job_merges_and_refresh_marks_dead_pid(tmp_path: Path, monkeypatch) -> None:
    _patch_store(monkeypatch, tmp_path)
    replace_job({"status": "running", "pid": 1, "detail": "시작"})
    write_job({"current_frame": 12, "total_frames": 100})
    dead = subprocess.Popen([sys.executable, "-c", "raise SystemExit(0)"])
    dead.wait()
    write_job({"pid": dead.pid, "status": "running"})
    data = refresh_job()
    assert data is not None
    assert data["status"] == "error"
    assert data["current_frame"] == 12
    assert "끊겼" in (data.get("message") or "")


def test_pid_alive_true_for_self_false_for_dead() -> None:
    assert pid_alive(os.getpid()) is True
    proc = subprocess.Popen([sys.executable, "-c", "raise SystemExit(0)"])
    proc.wait()
    assert pid_alive(proc.pid) is False
    assert pid_alive(None) is False
    assert pid_alive(0) is False


def test_payload_roundtrip_keeps_plan(tmp_path: Path) -> None:
    cfg = _sample_config(tmp_path)
    payload = config_to_payload(cfg, "sig-1")
    restored = payload_to_config(payload)
    assert restored.source_video == cfg.source_video
    assert restored.reference_images == cfg.reference_images
    assert restored.plan.video_encoder == "libx264"
    assert restored.plan.extra_args == ["-movflags", "+faststart"]
    assert restored.watermark is True
    assert restored.skip_profiles is False
    assert payload["source_sig"] == "sig-1"


def test_start_job_writes_payload_and_records_pid(tmp_path: Path, monkeypatch) -> None:
    _patch_store(monkeypatch, tmp_path)
    cfg = _sample_config(tmp_path)
    captured: dict = {}

    class FakeProc:
        pid = 4321

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return FakeProc()

    monkeypatch.setattr("src.job_runner.subprocess.Popen", fake_popen)
    job = start_job(cfg, "video-sig")
    from src import job_store

    assert job["status"] == "running"
    assert job["pid"] == 4321
    assert job["source_sig"] == "video-sig"
    payload = __import__("json").loads(job_store.PAYLOAD_PATH.read_text(encoding="utf-8"))
    assert payload["source_video"] == str(cfg.source_video)
    assert captured["kwargs"]["start_new_session"] is True
    assert "run_studio_job.py" in str(captured["cmd"][1])


def test_start_job_refuses_second_running_job(tmp_path: Path, monkeypatch) -> None:
    _patch_store(monkeypatch, tmp_path)
    write_job({"status": "running", "pid": os.getpid()})
    cfg = _sample_config(tmp_path)
    try:
        start_job(cfg, "other")
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "진행" in str(exc)


def test_latest_result_for_requires_matching_file(tmp_path: Path, monkeypatch) -> None:
    _patch_store(monkeypatch, tmp_path)
    out = tmp_path / "result.mp4"
    out.write_bytes(b"mp4")
    replace_job(
        {
            "status": "done",
            "source_sig": "abc",
            "output_path": str(out),
            "message": "완료",
            "frames_total": 10,
        }
    )
    result = latest_result_for("abc")
    assert result is not None
    assert result.output_path == out
    assert latest_result_for("nope") is None

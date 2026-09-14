"""Persist swap-job status so the UI can die without killing the worker."""

from __future__ import annotations

import json
import os
from pathlib import Path

from config import TEMP_DIR

JOB_DIR = TEMP_DIR / "jobs"
JOB_PATH = JOB_DIR / "current.json"
PAYLOAD_PATH = JOB_DIR / "current_payload.json"
LOG_PATH = JOB_DIR / "current.log"


def _atomic_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def replace_job(payload: dict) -> dict:
    _atomic_write(JOB_PATH, payload)
    return payload


def write_job(payload: dict) -> dict:
    current = read_job() or {}
    current.update(payload)
    _atomic_write(JOB_PATH, current)
    return current


def read_job() -> dict | None:
    if not JOB_PATH.exists():
        return None
    try:
        data = json.loads(JOB_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
    except OSError:
        return False
    return True


def refresh_job() -> dict | None:
    data = read_job()
    if not data:
        return None
    if data.get("status") == "running" and not pid_alive(data.get("pid")):
        data["status"] = "error"
        data["stage"] = "error"
        data["detail"] = "작업 프로세스가 끊겼습니다. 다시 생성해 주세요."
        data["message"] = data["detail"]
        write_job(data)
    return data

#!/usr/bin/env python3
"""Face-swap studio: replace every detected face with the uploaded identity photo."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from config import CONSENT_TEXT, OUTPUTS_DIR, WATERMARK_TEXT, ensure_runtime_dirs
from src.chunk_drop import chunk_drop
from src.chunk_upload import install_chunk_route, load_latest, remember_result, resolve_download
from src.export_manager import (
    build_export_plan,
    list_encoders,
    list_muxers,
    preferred_audio_encoders,
    preferred_muxers,
    preferred_video_encoders,
)
from src.media_probe import ProbeError, ffmpeg_bin, ffprobe_bin, probe_and_validate_video
from src.model_manager import download_models, inspect_models
from src.job_runner import running_job, start_job
from src.job_store import refresh_job
from src.pipeline import JobConfig
from src.utils import LOGGER, cleanup_old_temps, make_work_dir, safe_stem
from src.validators import validate_image_input, validate_video_input


st.set_page_config(
    page_title="Studio · 얼굴 바꾸기",
    layout="wide",
    initial_sidebar_state="collapsed",
)
ensure_runtime_dirs()


def _inject_css() -> None:
    css_path = ROOT / "static" / "studio.css"
    css = css_path.read_text(encoding="utf-8") if css_path.exists() else ""
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def _download_markup(token: str, label: str = "영상 받기") -> str:
    return f'<a class="studio-dl" href="/_studio/file/{token}?download=1" download>{label}</a>'


def _file_sig(path: Path) -> str:
    return f"{path.resolve()}::{int(path.stat().st_size)}"


@st.cache_resource(show_spinner=False)
def _studio_ready() -> dict:
    models = inspect_models()
    ffmpeg_ok = True
    try:
        ffmpeg_bin()
        ffprobe_bin()
    except ProbeError:
        ffmpeg_ok = False
    return {"ffmpeg_ok": ffmpeg_ok, "models_ok": bool(models.ready_for_faceswap)}


@st.cache_resource(show_spinner=False)
def _export_caps() -> dict:
    muxers = preferred_muxers(list_muxers())
    vencs = preferred_video_encoders(list_encoders("video"))
    aencs = preferred_audio_encoders(list_encoders("audio"))
    return {
        "muxers": [m.name for m in muxers],
        "video": [e.name for e in vencs],
        "audio": [e.name for e in aencs],
    }


def _ingest_video(work: Path, dropped: list[Path], video_url: str, video_path_in: str) -> Path | None:
    try:
        if dropped:
            video_path = dropped[0]
            sig = _file_sig(video_path)
            if st.session_state.get("active_video_sig") != sig:
                st.session_state.active_video_sig = sig
                st.session_state.last_result = None
            st.session_state["saved_video"] = str(video_path)
            return video_path
        if video_url.strip():
            raw = video_url.strip()
            if raw.startswith(("http://", "https://")):
                from urllib.parse import unquote, urlparse
                from urllib.request import Request, urlopen

                dest_dir = work / "uploads"
                dest_dir.mkdir(parents=True, exist_ok=True)
                parsed = urlparse(raw)
                name = Path(unquote(parsed.path)).name or "download.bin"
                path = dest_dir / name
                req = Request(raw, headers={"User-Agent": "studio/1.0"})
                with urlopen(req, timeout=180) as resp, path.open("wb") as handle:
                    while True:
                        chunk = resp.read(8 * 1024 * 1024)
                        if not chunk:
                            break
                        handle.write(chunk)
                st.session_state["saved_video"] = str(path)
                return path
            candidate = Path(raw).expanduser()
            if candidate.exists():
                sig = _file_sig(candidate)
                if st.session_state.get("active_video_sig") != sig:
                    st.session_state.active_video_sig = sig
                    st.session_state.last_result = None
                st.session_state["saved_video"] = str(candidate)
                return candidate
            st.error("영상 주소 또는 경로를 확인하세요.")
            return None
        if video_path_in.strip():
            candidate = Path(video_path_in.strip()).expanduser()
            if not candidate.exists():
                st.error("그 경로에 영상이 없습니다.")
                return None
            sig = _file_sig(candidate)
            if st.session_state.get("active_video_sig") != sig:
                st.session_state.active_video_sig = sig
                st.session_state.last_result = None
            st.session_state["saved_video"] = str(candidate)
            return candidate
        saved = st.session_state.get("saved_video")
        if saved and Path(saved).exists():
            return Path(saved)
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("video ingest failed")
        st.error("영상을 받지 못했습니다.")
        LOGGER.error("%s", exc)
    return None


def _ingest_refs(dropped: list[Path]) -> list[Path]:
    if dropped:
        ok_paths = []
        for path in dropped:
            val = validate_image_input(path)
            if not val.ok:
                st.error("이 파일은 이미지로 열 수 없습니다.")
                return []
            ok_paths.append(path)
        st.session_state["saved_refs"] = [str(p) for p in ok_paths]
        st.session_state.last_result = None
        return ok_paths
    saved = st.session_state.get("saved_refs") or []
    return [Path(p) for p in saved if Path(p).exists()]


def _show_result(result: dict) -> None:
    path = Path(result["path"]) if result.get("path") else None
    if path is not None and path.exists():
        token = result.get("token")
        if not token or resolve_download(str(token)) is None:
            stored = remember_result(path, result.get("message") or "완료. 영상을 받으세요.")
            result.update(stored)
            token = stored["token"]
        st.video(str(path))
        st.markdown(_download_markup(str(token)), unsafe_allow_html=True)
        if result.get("message"):
            st.caption(result["message"])
        return
    st.error(result.get("message") or "결과를 저장하지 못했습니다. 다시 생성해 주세요.")


def main() -> None:
    _inject_css()
    install_chunk_route()
    cleanup_old_temps()
    latest = load_latest()
    if latest:
        st.session_state["prev_download"] = latest

    st.markdown(
        """
        <div class="studio-top">
          <div class="studio-brand">
            <div class="studio-logo">S</div>
            <div>
              <div class="studio-name">Studio</div>
              <div class="studio-tag">영상 속 얼굴을 사진 얼굴로 바꿉니다</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    ready = _studio_ready()
    work = Path(st.session_state.setdefault("work_dir", str(make_work_dir("ui"))))

    if not st.session_state.get("consent"):
        st.checkbox(CONSENT_TEXT, key="consent_box")
        if st.button("동의하고 시작", disabled=not st.session_state.get("consent_box")):
            st.session_state.consent = True
            st.rerun()
        st.stop()

    if not ready["ffmpeg_ok"]:
        st.error("이 컴퓨터에서 영상을 처리할 준비가 되지 않았습니다.")
        st.stop()
    if not ready["models_ok"]:
        st.error("생성에 필요한 모델이 없습니다.")
        if st.button("모델 받기"):
            with st.spinner("모델을 받는 중..."):
                try:
                    download_models()
                    st.cache_resource.clear()
                    st.success("다시 생성을 눌러 주세요.")
                except Exception as exc:  # noqa: BLE001
                    st.error(str(exc))
        st.stop()

    left, right = st.columns([0.42, 0.58], gap="large")
    with left:
        st.caption("영상에서 보이는 모든 얼굴을, 올린 사진의 얼굴로 바꿉니다. 큰 원본은 채팅이 아니라 아래 칸에 놓으세요. 2GB까지입니다.")
        dropped_video = chunk_drop("원본 영상 (큰 파일도 여기)", key="video_drop")
        dropped_refs = chunk_drop("얼굴 사진", key="ref_drop", multiple=True)
        video_url = st.text_input("또는 영상 URL", placeholder="https://...", key="video_url_input")
        video_path_in = st.text_input("또는 이 컴퓨터 경로", placeholder="/data/clip.mp4", key="video_path_input")
        watermark = st.toggle(f"결과에 {WATERMARK_TEXT} 표시", value=True)
        busy = running_job() is not None
        generate = st.button("생성하기", type="primary", use_container_width=True, disabled=busy)
        notice = st.empty()
        last = st.session_state.get("last_result") or st.session_state.get("prev_download")
        if isinstance(last, dict) and last.get("path") and last.get("token") and Path(last["path"]).exists():
            st.markdown(_download_markup(last["token"], "이전 결과 받기"), unsafe_allow_html=True)

    video_path = _ingest_video(work, dropped_video, video_url, video_path_in)
    ref_paths = _ingest_refs(dropped_refs)

    info = None
    if video_path is not None:
        video_val = validate_video_input(video_path)
        if video_val.ok:
            try:
                info = probe_and_validate_video(video_path)
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("probe failed")
                st.error("영상을 열 수 없습니다.")
                LOGGER.error("%s", exc)
        else:
            st.error("이 파일은 영상으로 열리지 않습니다.")

    with right:
        result = st.session_state.get("last_result")
        current_sig = _file_sig(video_path) if video_path is not None and video_path.exists() else None
        result_for_this = (
            isinstance(result, dict)
            and result.get("path")
            and Path(result["path"]).exists()
            and result.get("source_sig") == current_sig
        )
        if result_for_this:
            _show_result(result)
        elif video_path is not None:
            try:
                st.video(str(video_path))
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("source video preview failed: %s", exc)
            if ref_paths:
                st.caption("이 사진 얼굴로 영상 속 얼굴을 전부 바꿉니다.")
                st.image(str(ref_paths[0]), use_container_width=True)
        else:
            st.markdown(
                """
                <div class="studio-empty">
                  <h3>미리보기</h3>
                  <p>왼쪽에서 원본 영상과 얼굴 사진을 올리면 여기에서 결과를 봅니다.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    current_sig = _file_sig(video_path) if video_path is not None and video_path.exists() else None
    job = refresh_job()
    if generate:
        if video_path is None or info is None:
            notice.warning("원본 영상을 올려 주세요.")
            return
        if not ref_paths:
            notice.warning("얼굴 사진을 한 장 이상 올려 주세요.")
            return
        if running_job() is not None:
            notice.info("이미 생성이 진행 중입니다. 탭을 닫아도 이어서 돌아갑니다.")
        else:
            caps = _export_caps()
            plan = build_export_plan(
                source=info,
                container="auto",
                video_encoder="auto",
                audio_encoder="auto",
                fps_mode="source",
                custom_fps=None,
                resolution_mode="source",
                custom_size=None,
                lossless=False,
                high_quality=True,
                output_name=safe_stem("studio"),
                available_video=caps["video"],
                available_audio=caps["audio"],
                available_muxers=caps["muxers"],
            )
            cfg = JobConfig(
                source_video=video_path,
                reference_images=ref_paths,
                plan=plan,
                watermark=bool(watermark),
                output_dir=OUTPUTS_DIR,
            )
            try:
                start_job(cfg, source_sig=_file_sig(video_path))
                st.session_state.last_result = None
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("failed to start background job")
                notice.error("생성을 시작하지 못했습니다. 다시 눌러 주세요.")
                LOGGER.error("%s", exc)
                return
        st.rerun()

    job = refresh_job()
    if not job:
        return
    job_sig = job.get("source_sig")
    if job.get("status") == "running":
        current = int(job.get("current_frame") or 0)
        total = max(int(job.get("total_frames") or 0), current, 1)
        ratio = min(1.0, current / total) if total else 0.0
        detail = str(job.get("detail") or job.get("message") or "생성하는 중")
        notice.info("탭을 닫아도 생성은 서버에서 이어집니다.")
        st.progress(ratio, text=detail)
        time.sleep(1.5)
        st.rerun()
        return
    if job.get("status") == "done" and job_sig and job_sig == current_sig:
        path = Path(str(job.get("output_path") or ""))
        if path.is_file() and path.stat().st_size > 0:
            existing = st.session_state.get("last_result")
            already = (
                isinstance(existing, dict)
                and existing.get("path") == str(path)
                and existing.get("source_sig") == current_sig
            )
            if already:
                notice.success(str(existing.get("message") or "완료. 아래 버튼으로 영상을 받으세요."))
                return
            stored = remember_result(path, str(job.get("message") or "완료. 영상을 받으세요."), source_sig=current_sig)
            st.session_state.last_result = stored
            st.session_state.active_video_sig = current_sig
            st.rerun()
            return
        notice.error("결과는 끝났는데 파일을 찾지 못했습니다. 다시 생성해 주세요.")
        return
    if job.get("status") == "error" and (not job_sig or job_sig == current_sig):
        notice.error(str(job.get("message") or job.get("detail") or "생성에 실패했습니다. 다시 눌러 주세요."))


if __name__ == "__main__":
    main()

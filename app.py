#!/usr/bin/env python3
"""Consumer video studio UI. Face-swap pipeline stays behind the generate button."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import streamlit as st
import cv2

from config import CONSENT_TEXT, OUTPUTS_DIR, WATERMARK_TEXT, ensure_runtime_dirs
from src.chunk_drop import chunk_drop
from src.chunk_upload import install_chunk_route, register_download
from src.identity_gallery import (
    build_gallery,
    format_times,
    match_identity,
)
from src.target_selector import Selection, draw_candidates, select_by_click, select_by_number
from src.export_manager import (
    build_export_plan,
    list_encoders,
    list_muxers,
    preferred_audio_encoders,
    preferred_muxers,
    preferred_video_encoders,
)
from src.face_swapper import ModelUnavailable
from src.image_io import bgr_to_rgb
from src.media_probe import ProbeError, ffmpeg_bin, ffprobe_bin, probe_and_validate_video
from src.model_manager import download_models, inspect_models
from src.pipeline import JobConfig
from src.preview_click import fit_preview_size, map_click_to_frame
from src.runtime import RuntimeBundle, create_runtime
from src.studio_options import duration_window, output_size
from src.utils import LOGGER, cleanup_old_temps, make_work_dir, safe_stem
from src.validators import validate_image_input, validate_video_input
from src.video_io import extract_frame_at


st.set_page_config(
    page_title="Studio · AI 영상 생성기",
    layout="wide",
    initial_sidebar_state="collapsed",
)
ensure_runtime_dirs()

MODE_MEDIA = "미디어 → 영상"
MODE_IMAGE = "이미지 → 영상"
MODE_TEXT = "텍스트 → 영상"
DURATION_OPTIONS = ["5초", "10초", "15초", "전체"]
ASPECT_OPTIONS = ["원본", "16:9", "9:16", "1:1"]
RES_OPTIONS = ["원본", "720p", "1080p"]


def _inject_css() -> None:
    css_path = ROOT / "static" / "studio.css"
    css = css_path.read_text(encoding="utf-8") if css_path.exists() else ""
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def _save_upload(upload, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = Path(upload.name or "upload.bin").name or "upload.bin"
    path = dest_dir / name
    LOGGER.info("saving upload name=%s size=%s -> %s", name, getattr(upload, "size", "?"), path)
    if hasattr(upload, "seek"):
        try:
            upload.seek(0)
        except Exception:
            pass
    written = 0
    with path.open("wb") as handle:
        reader = getattr(upload, "read", None)
        if callable(reader):
            while True:
                chunk = reader(8 * 1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                written += len(chunk)
        else:
            data = upload.getbuffer()
            handle.write(data)
            written = len(data)
    if written <= 0:
        raise RuntimeError("올린 파일이 비어 있습니다.")
    return path


def _download_url(url: str, dest_dir: Path) -> Path:
    from urllib.parse import unquote, urlparse
    from urllib.request import Request, urlopen

    dest_dir.mkdir(parents=True, exist_ok=True)
    parsed = urlparse(url.strip())
    name = Path(unquote(parsed.path)).name or "download.bin"
    path = dest_dir / name
    req = Request(url.strip(), headers={"User-Agent": "studio/1.0"})
    with urlopen(req, timeout=180) as resp, path.open("wb") as handle:
        while True:
            chunk = resp.read(8 * 1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
    if not path.exists() or path.stat().st_size <= 0:
        raise RuntimeError("링크에서 파일을 받지 못했습니다.")
    return path


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


@st.cache_resource(show_spinner=True)
def _runtime() -> RuntimeBundle:
    return create_runtime()


def _try_image_click(image_rgb: np.ndarray, key: str, frame_wh: tuple[int, int]):
    try:
        from streamlit_image_coordinates import streamlit_image_coordinates

        click = streamlit_image_coordinates(image_rgb, key=key, use_column_width="always")
    except Exception:
        st.image(image_rgb, use_container_width=True)
        return None
    if click and "x" in click:
        x, y = map_click_to_frame(click, frame_wh)
        return {"x": x, "y": y}
    return None


def _preview_overlay(frame_bgr: np.ndarray) -> np.ndarray:
    h, w = frame_bgr.shape[:2]
    nw, nh = fit_preview_size(w, h, 1280)
    if (nw, nh) == (w, h):
        return bgr_to_rgb(frame_bgr)
    resized = cv2.resize(frame_bgr, (nw, nh), interpolation=cv2.INTER_AREA)
    return bgr_to_rgb(resized)


def _face_area(candidate) -> float:
    x1, y1, x2, y2 = [float(v) for v in candidate.face.box]
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def _auto_select(candidates):
    if not candidates:
        return None
    return max(candidates, key=_face_area)


def _header() -> None:
    st.markdown(
        """
        <div class="studio-top">
          <div class="studio-brand">
            <div class="studio-logo">S</div>
            <div>
              <div class="studio-name">Studio</div>
              <div class="studio-tag">AI 영상 생성기</div>
            </div>
          </div>
          <div class="studio-chip">원본 동작 · 배경 · 소리 유지</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _ingest_video(work: Path, dropped: list[Path], video_url: str, video_path_in: str) -> Path | None:
    try:
        if dropped:
            video_path = dropped[0]
            st.session_state["saved_video"] = str(video_path)
            st.session_state["video_sig"] = (video_path.name, int(video_path.stat().st_size))
            return video_path
        if video_url.strip():
            raw = video_url.strip()
            if raw.startswith(("http://", "https://")):
                with st.spinner("링크로 영상을 가져오는 중..."):
                    video_path = _download_url(raw, work / "uploads")
                st.session_state["saved_video"] = str(video_path)
                return video_path
            candidate = Path(raw).expanduser()
            if candidate.exists():
                st.session_state["saved_video"] = str(candidate)
                return candidate
            st.error("영상 주소 또는 경로를 확인하세요.")
            return None
        if video_path_in.strip():
            candidate = Path(video_path_in.strip()).expanduser()
            if not candidate.exists():
                st.error("그 경로에 영상이 없습니다.")
                return None
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
    return None


def _ingest_refs(work: Path, dropped: list[Path]) -> list[Path]:
    if dropped:
        ok_paths = []
        for path in dropped:
            val = validate_image_input(path)
            if not val.ok:
                st.error("이 파일은 이미지로 열 수 없습니다.")
                return []
            ok_paths.append(path)
        st.session_state["saved_refs"] = [str(p) for p in ok_paths]
        return ok_paths
    saved = st.session_state.get("saved_refs") or []
    return [Path(p) for p in saved if Path(p).exists()]


def _load_gallery(video_path: Path, info, runtime):
    sig = (str(video_path), int(video_path.stat().st_size), round(float(info.duration or 0.0), 2))
    if st.session_state.get("gallery_sig") != sig:
        with st.spinner("여러 장면에서 같은 사람을 묶는 중..."):
            gallery = build_gallery(video_path, info, runtime.person_detector, extract_frame_at)
        st.session_state.gallery = gallery
        st.session_state.gallery_sig = sig
        if gallery and st.session_state.get("selected_identity") not in {i.id for i in gallery}:
            st.session_state.selected_identity = gallery[0].id
    return st.session_state.get("gallery") or []


def _label_candidates(candidates, identities):
    labels: dict[int, str] = {}
    mapping: dict[int, int] = {}
    for cand in candidates:
        ident = match_identity(cand.face.normed_embedding, identities)
        if ident is not None:
            labels[cand.index] = f"사람 {ident.id}"
            mapping[cand.index] = ident.id
        else:
            labels[cand.index] = "새 얼굴"
    return labels, mapping


def _selection_for_identity(identities, identity_id: int, candidates) -> Selection | None:
    ident = next((item for item in identities if item.id == int(identity_id)), None)
    if ident is None:
        return None
    for cand in candidates or []:
        if match_identity(cand.face.normed_embedding, [ident], thresh=0.35) is not None:
            return Selection(
                person_index=ident.id,
                box=list(cand.face.box),
                person_box=list(cand.person_box),
                embedding=ident.embedding,
                kps=cand.face.kps,
            )
    hit = ident.hits[0]
    return Selection(
        person_index=ident.id,
        box=list(hit.box),
        person_box=list(hit.person_box),
        embedding=ident.embedding,
        kps=hit.kps,
    )


def _render_gallery(identities, current_t: float) -> None:
    if not identities:
        st.caption("여러 장면을 봐도 얼굴을 찾지 못했습니다.")
        return
    st.markdown("**이 영상의 사람**")
    st.caption("앵글이 바뀌어도 번호는 같은 사람을 가리킵니다. 이 장면에 있는 사람은 표시됩니다.")
    for start in range(0, len(identities), 4):
        row = identities[start : start + 4]
        cols = st.columns(len(row))
        for ident, col in zip(row, cols):
            with col:
                st.image(ident.thumb_rgb, use_container_width=True)
                here = any(abs(hit.time_sec - current_t) < 0.7 for hit in ident.hits)
                title = f"사람 {ident.id}" + (" · 지금" if here else "")
                if st.button(title, key=f"pick_id_{ident.id}", use_container_width=True):
                    st.session_state.selected_identity = ident.id
                    st.rerun()
                st.caption(format_times(ident.times))


def _show_result(result: dict) -> None:
    path = Path(result["path"]) if result.get("path") else None
    if path is not None and path.exists():
        st.video(str(path))
        token = result.get("token") or register_download(path)
        result["token"] = token
        st.markdown(
            f'<a class="studio-dl" href="/_studio/file/{token}" download>영상 받기</a>',
            unsafe_allow_html=True,
        )
        if result.get("message"):
            st.caption(result["message"])
        if st.button("다른 장면으로 다시 만들기", use_container_width=True):
            st.session_state.last_result = None
            st.rerun()
        return
    st.error(result.get("message") or "결과를 저장하지 못했습니다. 다시 생성해 주세요.")


def _pick_selection(frame, candidates, identities):
    if not candidates:
        return None
    labels, mapping = _label_candidates(candidates, identities)
    selected_id = st.session_state.get("selected_identity")
    if selected_id is None and identities:
        selected_id = identities[0].id
        st.session_state.selected_identity = selected_id
    selected_local = next((idx for idx, ident_id in mapping.items() if ident_id == selected_id), None)
    if selected_local is None:
        auto = _auto_select(candidates)
        selected_local = auto.index if auto else candidates[0].index
    overlay = draw_candidates(frame, candidates, selected=selected_local, studio=True, labels=labels)
    preview = _preview_overlay(overlay)
    orig_h, orig_w = frame.shape[:2]
    click = _try_image_click(preview, key="face_pick", frame_wh=(orig_w, orig_h))
    if click and "x" in click:
        hit = select_by_click(candidates, int(click["x"]), int(click["y"]))
        if hit:
            selected_local = hit.person_index
            if hit.person_index in mapping:
                st.session_state.selected_identity = mapping[hit.person_index]
                selected_id = mapping[hit.person_index]
    identity_ids = [item.id for item in identities] or [1]
    if selected_id not in identity_ids:
        selected_id = identity_ids[0]
        st.session_state.selected_identity = selected_id
    if "person_select_id" not in st.session_state or st.session_state.person_select_id not in identity_ids:
        st.session_state.person_select_id = selected_id
    if st.session_state.get("selected_identity") in identity_ids:
        st.session_state.person_select_id = st.session_state.selected_identity
    picked = st.selectbox(
        "사람 선택",
        options=identity_ids,
        format_func=lambda n: f"사람 {n}",
        key="person_select_id",
    )
    if picked is not None:
        st.session_state.selected_identity = int(picked)
        selected_id = int(picked)
    return _selection_for_identity(identities, int(selected_id), candidates)


def main() -> None:
    _inject_css()
    install_chunk_route()
    cleanup_old_temps()
    _header()
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

    mode = st.segmented_control(
        "생성 방식",
        options=[MODE_MEDIA, MODE_IMAGE, MODE_TEXT],
        default=MODE_MEDIA,
        key="gen_mode",
        selection_mode="single",
        label_visibility="collapsed",
    ) or MODE_MEDIA

    left, right = st.columns([0.42, 0.58], gap="large")

    with left:
        prompt_ph = {
            MODE_MEDIA: "예: 영상 속 가운데 사람을 올린 얼굴로 바꿔 주세요. 춤과 카메라는 그대로.",
            MODE_IMAGE: "예: 이 얼굴이 영상 속 주인공이 되게 해 주세요. 배경과 동작은 유지.",
            MODE_TEXT: "원하는 장면을 적어 주세요. 텍스트만으로는 영상을 만들지 않습니다. 영상과 얼굴 사진이 필요합니다.",
        }[mode]
        st.caption("프롬프트")
        prompt = st.text_area("프롬프트", placeholder=prompt_ph, height=140, label_visibility="collapsed")
        st.caption("원본 영상의 인물을, 올린 얼굴로 바꿉니다. 동작·배경·소리는 그대로입니다.")

        if mode == MODE_TEXT:
            st.info("텍스트로만 새 영상을 만들지는 않습니다. 영상과 얼굴 사진을 올리면 바로 만들 수 있습니다.")

        if mode == MODE_IMAGE:
            dropped_refs = chunk_drop("얼굴 사진", key="ref_drop", multiple=True)
            dropped_video = chunk_drop("움직임이 담긴 원본 영상", key="video_drop")
        else:
            dropped_video = chunk_drop("원본 영상", key="video_drop")
            dropped_refs = chunk_drop("얼굴 사진", key="ref_drop", multiple=True)

        with st.expander("링크로 가져오기"):
            video_url = st.text_input("영상 URL", placeholder="https://...", key="video_url_input")
            video_path_in = st.text_input("이 컴퓨터 경로", placeholder="/data/clip.mp4", key="video_path_input")

        duration_choice = st.pills(
            "길이", DURATION_OPTIONS, default="전체", key="duration_choice", selection_mode="single"
        ) or "전체"
        aspect_choice = st.pills(
            "화면 비율", ASPECT_OPTIONS, default="원본", key="aspect_choice", selection_mode="single"
        ) or "원본"
        res_choice = st.pills(
            "해상도", RES_OPTIONS, default="원본", key="res_choice", selection_mode="single"
        ) or "원본"

        watermark = st.toggle(f"결과에 {WATERMARK_TEXT} 표시", value=True)
        generate = st.button("생성하기", type="primary", use_container_width=True, disabled=(mode == MODE_TEXT))
        notice = st.empty()
        last = st.session_state.get("last_result")
        if isinstance(last, dict) and last.get("path") and last.get("token"):
            st.markdown(
                f'<a class="studio-dl" href="/_studio/file/{last["token"]}" download>영상 받기</a>',
                unsafe_allow_html=True,
            )

    video_path = _ingest_video(work, dropped_video, video_url, video_path_in)
    ref_paths = _ingest_refs(work, dropped_refs)

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

    selection = None
    identities = []
    with right:
        result = st.session_state.get("last_result")
        if isinstance(result, dict) and result.get("path"):
            _show_result(result)
        elif info is not None and video_path is not None:
            duration = float(info.duration or 0.0)
            pick_ts = st.slider(
                "장면",
                0.0,
                max(0.1, duration),
                min(0.4, duration) if duration else 0.0,
                0.05,
                key="scene_t",
            )
            try:
                runtime = _runtime()
                identities = _load_gallery(video_path, info, runtime)
                frame = extract_frame_at(video_path, pick_ts, info=info)
                candidates = runtime.person_detector.candidates(frame)
            except ModelUnavailable as exc:
                st.error(str(exc))
                candidates = []
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("frame pick failed")
                st.error("장면을 열 수 없습니다.")
                LOGGER.error("%s", exc)
                candidates = []

            _render_gallery(identities, float(pick_ts))
            if not candidates:
                try:
                    st.image(_preview_overlay(extract_frame_at(video_path, pick_ts, info=info)), use_container_width=True)
                except Exception:
                    pass
                st.caption("이 장면에서는 얼굴을 못 찾았습니다. 사람을 위에서 고르거나 장면을 옮기세요.")
            else:
                selection = _pick_selection(frame, candidates, identities)
                who = st.session_state.get("selected_identity")
                st.caption(
                    f"지금 장면에서는 사람 {who}입니다. 박스를 누르거나 위에서 같은 사람을 고르세요."
                    if who
                    else "바꿀 사람을 고르세요. 번호는 영상 전체에서 유지됩니다."
                )
        else:
            st.markdown(
                """
                <div class="studio-empty">
                  <h3>미리보기</h3>
                  <p>왼쪽에서 원본 영상과 얼굴 사진을 올리면, 여기에서 주인공을 고르고 결과를 봅니다.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    if not generate:
        return
    if mode == MODE_TEXT:
        notice.warning("영상과 얼굴 사진을 올린 뒤 생성해 주세요.")
        return
    if video_path is None or info is None:
        notice.warning("원본 영상을 올려 주세요.")
        return
    if not ref_paths:
        notice.warning("얼굴 사진을 한 장 이상 올려 주세요.")
        return
    try:
        runtime = _runtime()
    except Exception as exc:  # noqa: BLE001
        notice.error(str(exc))
        return
    if selection is None:
        try:
            if not identities:
                identities = _load_gallery(video_path, info, runtime)
            identity_id = st.session_state.get("selected_identity")
            if identity_id is None and identities:
                identity_id = identities[0].id
            frame = extract_frame_at(video_path, float(st.session_state.get("scene_t", 0.2)), info=info)
            candidates = runtime.person_detector.candidates(frame)
            if identity_id is not None:
                selection = _selection_for_identity(identities, int(identity_id), candidates)
            if selection is None:
                auto = _auto_select(candidates)
                selection = select_by_number(candidates, int(auto.index)) if auto else None
        except Exception:
            selection = None
    if selection is None:
        notice.warning("영상에서 얼굴을 찾지 못했습니다. 오른쪽에서 사람을 골라 주세요.")
        return

    caps = _export_caps()
    res_mode, custom_size = output_size(info, aspect_choice, res_choice)
    start_sec, end_sec = duration_window(
        duration_choice,
        float(info.duration or 0.0),
        float(st.session_state.get("scene_t", 0.0)),
    )
    plan = build_export_plan(
        source=info,
        container="auto",
        video_encoder="auto",
        audio_encoder="auto",
        fps_mode="source",
        custom_fps=None,
        resolution_mode=res_mode,
        custom_size=custom_size,
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
        selection=selection,
        plan=plan,
        start_sec=start_sec,
        end_sec=end_sec,
        watermark=bool(watermark),
        purpose_note=prompt or "",
        output_dir=OUTPUTS_DIR,
    )
    progress_bar = st.progress(0.0, text="생성 중")

    def _progress(ev):
        progress_bar.progress(ev.ratio, text=ev.message)

    try:
        runtime.engine.records.clear()
        runtime.engine.swapper.call_count = 0
        result = runtime.job.run(cfg, progress=_progress)
        path = result.output_path
        usable = bool(path and Path(path).exists())
        token = register_download(Path(path)) if usable else None
        st.session_state.last_result = {
            "ok": usable,
            "path": str(path) if usable else None,
            "message": "완료. 오른쪽에서 보고, 영상 받기로 저장하세요." if usable else result.message,
            "token": token,
        }
        if usable:
            st.rerun()
        notice.error(result.message)
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("generate failed")
        notice.error("생성에 실패했습니다.")
        LOGGER.error("%s", exc)


if __name__ == "__main__":
    main()

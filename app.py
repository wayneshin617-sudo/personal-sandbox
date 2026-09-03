#!/usr/bin/env python3
"""Local Streamlit app: identity-preserving face swap on a selected tracked person."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import streamlit as st

from check_environment import collect_environment
from config import CONSENT_TEXT, OUTPUTS_DIR, TEMP_DIR, WATERMARK_TEXT, ensure_runtime_dirs
from src.export_manager import (
    build_export_plan,
    list_encoders,
    list_muxers,
    preferred_audio_encoders,
    preferred_muxers,
    preferred_video_encoders,
    suffix_for_container,
)
from src.face_swapper import ModelUnavailable
from src.image_io import bgr_to_rgb
from src.media_probe import probe_and_validate_video, summarize_media
from src.model_manager import download_models, inspect_models
from src.pipeline import JobConfig
from src.runtime import RuntimeBundle, create_runtime
from src.target_selector import draw_candidates, select_by_click, select_by_number
from src.utils import LOGGER, cleanup_old_temps, make_work_dir, safe_stem
from src.validators import validate_image_input, validate_video_input
from src.video_io import extract_frame_at


st.set_page_config(page_title="Identity Face Swap Studio", layout="wide")
ensure_runtime_dirs()


def _save_upload(upload, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = upload.name or "upload.bin"
    path = dest_dir / name
    path.write_bytes(upload.getbuffer())
    return path


@st.cache_resource(show_spinner=False)
def _env() -> dict:
    return collect_environment()


@st.cache_resource(show_spinner=True)
def _runtime() -> RuntimeBundle:
    return create_runtime()


def _try_image_click(image_rgb: np.ndarray, key: str):
    try:
        from streamlit_image_coordinates import streamlit_image_coordinates

        return streamlit_image_coordinates(image_rgb, key=key)
    except Exception:
        st.image(image_rgb, caption="클릭 선택 패키지가 없으면 아래 번호로 선택하세요.")
        return None


def main() -> None:
    cleanup_old_temps()
    env = _env()

    st.title("Identity Face Swap Studio")
    st.caption("원본 동작·배경·오디오를 유지한 채, 선택한 인물만 InsightFace INSwapper로 변환합니다.")

    with st.expander("실행 환경", expanded=True):
        c1, c2, c3 = st.columns(3)
        c1.write(f"**Python**: {env['python']}")
        c1.write(f"**OS**: {env['os']}")
        c2.write(f"**GPU**: {env['gpu'].get('gpu_name') or '없음 (CPU 모드)'}")
        c2.write(f"**CUDA**: {env['gpu'].get('cuda_available')}")
        c3.write(f"**ONNX providers**: {env['onnxruntime'].get('available_providers')}")
        c3.write(f"**선택 provider**: {env.get('selected_provider')}")
        ff = env["ffmpeg"]
        if ff.get("ok"):
            st.success(f"FFmpeg/FFprobe 정상: {ff.get('ffmpeg_version')}")
            st.write(
                "사용 가능 muxer 예시:",
                ", ".join(ff.get("sample_muxers", [])),
            )
            st.write(
                "비디오 인코더 예시:",
                ", ".join(ff.get("sample_video_encoders", [])),
            )
            st.write(
                "오디오 인코더 예시:",
                ", ".join(ff.get("sample_audio_encoders", [])),
            )
        else:
            st.error(ff.get("ffmpeg_error") or ff.get("ffprobe_error") or "FFmpeg가 없습니다.")
            st.stop()
        st.write("패키지 버전:", env["packages"])
        for item in env["models"]["files"]:
            icon = "✅" if item["present"] else "❌"
            st.write(f"{icon} {item['name']} — {item['source']} / {item['license']}")
        for msg in env["models"]["messages"]:
            st.warning(msg)
        st.info("전체 인물 변환(Advanced): " + env["person_transform"]["reason"])

    if not st.session_state.get("consent"):
        st.subheader("사용 동의")
        agreed = st.checkbox(CONSENT_TEXT)
        if st.button("동의하고 계속", disabled=not agreed):
            st.session_state.consent = True
            st.rerun()
        st.stop()

    if not env["models"]["ready_for_faceswap"]:
        st.error("필수 face-swap 모델이 없어 처리를 시작할 수 없습니다. 단순 합성으로 대체하지 않습니다.")
        if st.button("모델 다운로드 시도"):
            with st.spinner("모델 다운로드 중..."):
                try:
                    download_models()
                    st.cache_resource.clear()
                    st.success("다운로드 완료. 페이지를 새로고침하세요.")
                except Exception as exc:  # noqa: BLE001
                    st.exception(exc)
        st.stop()

    try:
        runtime = _runtime()
    except ModelUnavailable as exc:
        st.error(str(exc))
        st.stop()
    except Exception as exc:  # noqa: BLE001
        st.error(f"모델 로드 실패: {exc}")
        LOGGER.exception("runtime load failed")
        st.stop()

    work = Path(st.session_state.setdefault("work_dir", str(make_work_dir("ui"))))

    st.header("1. 입력")
    video_file = st.file_uploader("원본 영상 (확장자 제한 없음 — 실제 디코딩으로 판정)", type=None)
    ref_files = st.file_uploader(
        "기준 이미지 1장 이상 (확장자 제한 없음 — Pillow/OpenCV 디코딩으로 판정)",
        type=None,
        accept_multiple_files=True,
    )

    if video_file is None:
        st.info("영상을 올리면 컨테이너/코덱 분석과 미리보기가 표시됩니다.")
        st.stop()

    video_path = _save_upload(video_file, work / "uploads")
    video_val = validate_video_input(video_path)
    if not video_val.ok:
        st.error(video_val.message)
        st.json(video_val.details)
        st.stop()
    info = probe_and_validate_video(video_path)
    st.success(summarize_media(info))
    with st.expander("FFprobe 상세"):
        st.json(
            {
                "format": info.format_name,
                "duration": info.duration,
                "fps": info.fps,
                "avg_fps": info.avg_fps,
                "rotation": info.rotation,
                "display": [info.display_width, info.display_height],
                "video": info.video.__dict__ if info.video else None,
                "audio": info.audio.__dict__ if info.audio else None,
                "warnings": info.warnings,
            }
        )

    if not ref_files:
        st.info("기준 이미지를 한 장 이상 올리세요.")
        st.stop()
    ref_paths = []
    for upload in ref_files:
        path = _save_upload(upload, work / "refs")
        val = validate_image_input(path)
        if not val.ok:
            st.error(f"{upload.name}: {val.message}")
            st.stop()
        st.write(f"기준 이미지 통과: {upload.name} — {val.message}")
        ref_paths.append(path)

    duration = float(info.duration or 0.0)
    st.header("2. 대상 인물 선택")
    pick_ts = st.slider("대상 선택 시점 (초)", 0.0, max(0.1, duration), min(0.2, duration), 0.05)
    try:
        frame = extract_frame_at(video_path, pick_ts, info=info)
    except Exception as exc:  # noqa: BLE001
        st.error(f"프레임 추출 실패: {exc}")
        st.stop()
    candidates = runtime.person_detector.candidates(frame)
    if not candidates:
        st.error("이 시점에서 얼굴을 찾지 못했습니다. 다른 시점을 선택하세요.")
        st.image(bgr_to_rgb(frame), caption="검출 실패 프레임")
        st.stop()

    overlay = draw_candidates(frame, candidates, selected=st.session_state.get("selected_index"))
    click = _try_image_click(bgr_to_rgb(overlay), key="face_pick")
    numbers = [c.index for c in candidates]
    default_idx = st.session_state.get("selected_index") or numbers[0]
    selected_number = st.number_input("대상 번호", min_value=min(numbers), max_value=max(numbers), value=int(default_idx))
    if click and "x" in click:
        hit = select_by_click(candidates, int(click["x"]), int(click["y"]))
        if hit:
            selected_number = hit.person_index
            st.session_state.selected_index = selected_number
            st.write(f"클릭으로 Person #{selected_number} 선택")
    selection = select_by_number(candidates, int(selected_number))
    if selection is None:
        st.error("선택한 번호의 인물이 없습니다.")
        st.stop()
    st.session_state.selected_index = selection.person_index
    st.image(bgr_to_rgb(draw_candidates(frame, candidates, selected=selection.person_index)), caption="선택 결과")

    st.header("3. 모드 및 품질")
    mode = st.radio(
        "처리 모드",
        ["얼굴 교체", "전체 인물 변환 (Advanced)"],
        index=0,
        help="전체 인물 변환은 현재 환경에서 비활성화될 수 있습니다.",
    )
    if mode.startswith("전체"):
        st.warning(env["person_transform"]["reason"])
        st.write("필요 모델:", env["person_transform"]["required_models"])
        st.write("필요 패키지:", env["person_transform"]["required_packages"])
        st.stop()

    col_a, col_b, col_c = st.columns(3)
    restore = col_a.slider("얼굴 복원 강도", 0.0, 1.0, 0.0 if not runtime.restorer_ready else 0.35, 0.05)
    if not runtime.restorer_ready:
        col_a.caption("GFPGAN 모델이 없어 복원은 적용되지 않습니다.")
        restore = 0.0
    mask_range = col_b.slider("마스크 범위", 0.2, 1.0, 0.70, 0.05)
    blend = col_c.slider("합성 강도", 0.2, 1.0, 0.90, 0.05)
    track_thresh = st.slider("추적 신뢰도 기준", 0.15, 0.85, 0.35, 0.05)
    watermark = st.checkbox(f"결과 좌측 하단에 '{WATERMARK_TEXT}' 워터마크", value=True)
    purpose = st.text_input("사용 목적 / 동의 기록 (선택)", placeholder="예: 본인 영상 편집, 당사자 동의 확보")

    st.header("4. 미리보기 구간 / 전체 처리")
    preview_end_default = min(duration, 2.0) if duration else 2.0
    p1, p2 = st.columns(2)
    preview_start = p1.number_input("미리보기 시작(초)", 0.0, max(0.0, duration), 0.0, 0.1)
    preview_end = p2.number_input("미리보기 끝(초)", 0.0, max(0.1, duration), preview_end_default, 0.1)

    st.header("5.보내기 설정 (런타임 muxer/encoder)")
    muxers = preferred_muxers(list_muxers())
    vencs = preferred_video_encoders(list_encoders("video"))
    aencs = preferred_audio_encoders(list_encoders("audio"))
    mux_names = ["auto"] + [m.name for m in muxers]
    v_names = ["auto"] + [e.name for e in vencs]
    a_names = ["auto", "copy", "none"] + [e.name for e in aencs]
    e1, e2, e3 = st.columns(3)
    container = e1.selectbox("출력 컨테이너", mux_names, index=0)
    video_enc = e2.selectbox("영상 코덱", v_names, index=0)
    audio_enc = e3.selectbox("오디오 코덱", a_names, index=0)
    if container in {"gif", "webp", "apng"} or audio_enc == "none":
        st.info("GIF/WebP 등 애니메이션 이미지 또는 오디오 없음 선택 시 결과물에 소리가 없습니다.")
    out_name = st.text_input("출력 파일명 (확장자 없이)", value="swapped")
    fps_mode = st.radio("FPS", ["원본 유지", "사용자 지정"], horizontal=True)
    custom_fps = st.number_input("지정 FPS", 1.0, 120.0, float(info.avg_fps or info.fps or 25.0), 0.1)
    res_mode = st.radio("해상도", ["원본 유지", "사용자 지정"], horizontal=True)
    custom_w = st.number_input("너비", 64, 7680, int(info.display_width or 1280), 2)
    custom_h = st.number_input("높이", 64, 4320, int(info.display_height or 720), 2)
    quality = st.radio("품질", ["고품질", "무손실"], horizontal=True)

    def _plan():
        return build_export_plan(
            source=info,
            container=container,
            video_encoder=video_enc,
            audio_encoder=audio_enc,
            fps_mode="custom" if fps_mode == "사용자 지정" else "source",
            custom_fps=custom_fps,
            resolution_mode="custom" if res_mode == "사용자 지정" else "source",
            custom_size=(int(custom_w), int(custom_h)),
            lossless=quality == "무손실",
            high_quality=True,
            output_name=safe_stem(out_name),
            available_video=[e.name for e in vencs],
            available_audio=[e.name for e in aencs],
            available_muxers=[m.name for m in muxers],
        )

    plan_preview = _plan()
    for warn in plan_preview.warnings:
        st.warning(warn)
    st.caption(
        f"실제 인코딩 예정: container={plan_preview.container} video={plan_preview.video_encoder} "
        f"audio={plan_preview.audio_encoder} {plan_preview.width}x{plan_preview.height} @ {plan_preview.fps:.3f}fps"
    )

    log_box = st.empty()
    progress_bar = st.progress(0.0, text="대기")
    status = st.empty()

    def _progress(ev):
        progress_bar.progress(ev.ratio, text=ev.message)
        status.write(ev.message)

    def _run(start: float, end: float | None, name_suffix: str):
        runtime.engine.records.clear()
        runtime.engine.swapper.call_count = 0
        plan = _plan()
        plan.output_name = f"{safe_stem(out_name)}{name_suffix}"
        cfg = JobConfig(
            source_video=video_path,
            reference_images=ref_paths,
            selection=selection,
            plan=plan,
            start_sec=start,
            end_sec=end,
            track_thresh=track_thresh,
            mask_range=mask_range,
            blend_strength=blend,
            restore_strength=restore,
            watermark=watermark,
            purpose_note=purpose,
            output_dir=OUTPUTS_DIR,
        )
        result = runtime.job.run(cfg, progress=_progress)
        st.session_state.last_result = result
        return result

    c_prev, c_full = st.columns(2)
    run_preview = c_prev.button("짧은 구간 테스트 렌더링")
    run_full = c_full.button("전체 영상 처리")

    result = st.session_state.get("last_result")
    if run_preview:
        if preview_end <= preview_start:
            st.error("미리보기 끝 시각이 시작보다 커야 합니다.")
        else:
            result = _run(float(preview_start), float(preview_end), "_preview")
    if run_full:
        result = _run(0.0, None, "")

    st.header("6. 결과")
    if result is None:
        st.info("아직 처리 결과가 없습니다.")
    else:
        if result.ok and result.output_path:
            st.success(result.message)
            st.video(str(result.output_path))
            st.write(
                {
                    "output": str(result.output_path),
                    "frames_total": result.frames_total,
                    "frames_swapped": result.frames_swapped,
                    "frames_kept_original": result.frames_kept_original,
                    "track_id": result.track_id,
                    "inferences": result.inference_count,
                }
            )
            if result.output_probe:
                st.write("출력 FFprobe 요약")
                vp = result.output_probe
                st.json(
                    {
                        "format": vp.get("format_name"),
                        "duration": vp.get("duration"),
                        "fps": vp.get("fps"),
                        "avg_fps": vp.get("avg_fps"),
                        "display": [vp.get("display_width"), vp.get("display_height")],
                        "has_audio": vp.get("has_audio"),
                    }
                )
            with open(result.output_path, "rb") as handle:
                st.download_button(
                    "결과 파일 저장",
                    data=handle.read(),
                    file_name=result.output_path.name,
                    mime="application/octet-stream",
                )
        else:
            st.error(result.message)
        with st.expander("처리 로그 / inference 기록", expanded=True):
            st.write(result.inference_log)
            st.write(result.similarity_samples)
            if result.log_path and result.log_path.exists():
                st.download_button(
                    "로그 JSON 저장",
                    data=result.log_path.read_text(encoding="utf-8"),
                    file_name=result.log_path.name,
                    mime="application/json",
                )
            log_text = "\n".join(str(x) for x in result.inference_log)
            st.text_area("로그 보기", log_text, height=180)

    if st.button("오래된 임시 파일 정리"):
        removed = cleanup_old_temps(0.0)
        st.write(f"정리된 항목: {removed} (현재 세션 작업 폴더는 제외될 수 있음)")
        # also sweep TEMP_DIR files older than now-0
        st.write(f"temp 경로: {TEMP_DIR}")


if __name__ == "__main__":
    main()

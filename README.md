# Identity Face Swap Studio

로컬 웹앱입니다. 원본 영상에서 사용자가 고른 **한 명의 인물**만 기준 사진의 정체성으로 바꿉니다. 춤, 자세, 카메라 이동, 배경, 다른 사람, 오디오 싱크, 길이·FPS는 원본을 유지합니다.

정지 얼굴을 영상에 붙이는 오버레이는 구현하지 않습니다. 실제 추론 엔진은 **InsightFace INSwapper (`inswapper_128.onnx`)** 입니다. 모델 파일이 없으면 기능을 끄고, 원본을 결과로 복사하지 않습니다.

## 실행 방법

Linux (이 저장소에서 검증한 명령):

```bash
cd /path/to/this/repo
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -c "from src.model_manager import download_models; download_models()"
python check_environment.py
python -m pytest tests -q
python scripts/run_e2e.py
python -m streamlit run app.py --server.headless true --server.address 0.0.0.0
```

Windows:

```bat
install_windows.bat
run_windows.bat
```

앱은 브라우저에서 Streamlit 주소(기본 `http://localhost:8501`)로 엽니다. 첫 화면의 동의 확인란을 체크해야 업로드/처리가 가능합니다.

`Please wait…` 또는 “서버에 연결할 수 없습니다”가 나오면:

1. 앱 프로세스가 실제로 떠 있는지 확인하세요. `run_linux.sh` / `run_windows.bat`가 창을 연 상태로 유지되어야 합니다.
2. `0.0.0.0:8501`에 바인딩합니다. `127.0.0.1`만 쓰면 다른 기기·포트 포워드에서 웹소켓이 끊깁니다.
3. `.streamlit/config.toml`에서 CORS/XSRF를 끄고 있습니다. 프록시(Cursor 포트 포워드 등) 뒤에서 접속할 때 필요합니다.
4. 방화벽에서 8501/tcp를 허용하세요.

Cloud Agent VM 안의 서버는 검증용이며, 로컬 PC에서 쓰려면 위 설치 후 본인 머신에서 `run_*.bat`/`run_linux.sh`를 실행하세요.

## 현재 환경에서 확인한 스택

| 항목 | 값 |
| --- | --- |
| Python | 3.10–3.12 (이 환경은 3.12.3) |
| UI | Streamlit 1.40.2 |
| 얼굴 검출 | InsightFace SCRFD `det_10g.onnx` (Haar Cascade 없음) |
| 랜드마크 | SCRFD 5점 + 선택적 `2d106det.onnx` |
| 임베딩 / 재식별 | ArcFace `w600k_r50.onnx` |
| 얼굴 교체 추론 | InsightFace INSwapper `inswapper_128.onnx` via ONNX Runtime |
| 선택 복원 | GFPGAN 1.4 ONNX (파일 있을 때만) |
| 추적 | IoU + embedding + 의상 히스토그램 Hungarian matching, lost-track ReID |
| 영상 I/O | FFmpeg / FFprobe (확장자 화이트리스트 없음) |
| GPU | CUDA EP가 있으면 사용, 없으면 CPUExecutionProvider |

## 모델 라이선스와 출처

자세한 URL·체크섬은 `models/README.md`에 있습니다.

- **InsightFace buffalo_l / inswapper_128**: 프로젝트 https://github.com/deepinsight/insightface  
  코드는 MIT에 가깝고, **모델 가중치는 비상업 연구 조건**이 일반적입니다. 상업 사용 전에 원 저장소 라이선스를 확인하세요.
- **GFPGAN 1.4**: https://github.com/TencentARC/GFPGAN , Apache-2.0
- **ONNX Runtime**: MIT
- **OpenCV**: Apache-2.0
- **Streamlit**: Apache-2.0

## IMPORT / EXPORT 정책

UI의 파일 선택기는 확장자를 제한하지 않습니다. 지원 여부는 다음으로만 판단합니다.

1. FFprobe로 컨테이너, 스트림, 코덱, duration, FPS, time base, 회전 메타데이터 검사
2. 이미지는 Pillow 또는 OpenCV로 실제 디코딩
3. 영상은 FFmpeg로 실제 디코딩 smoke test
4. 확장자가 없거나 헤더와 달라도 디코딩되면 허용

내보내기는 확장자만 바꾸는 복사가 아니라 FFmpeg 인코딩/muxing을 수행합니다. muxer·encoder 목록은 실행 중인 FFmpeg에서 조회합니다. H.264 MP4는 호환성 기본값일 뿐 강제가 아닙니다. GIF/WebP는 오디오가 빠짐을 UI에 표시합니다.

## 모드

- **얼굴 교체**: 구현됨. 랜드마크 정렬, 마스크 페더링, LAB 컬러 매칭, 프레임 간 박스/랜드마크 스무딩, 검출 실패 시 원본 프레임 유지.
- **전체 인물 변환 (Advanced)**: **구현되지 않음 / 비활성화**. ControlNet+identity video 생성과 충분한 VRAM이 필요합니다. 얼굴 교체 결과를 전신 변환이라고 부르지 않습니다. 필요 조건은 앱의 환경 패널에 그대로 표시됩니다.

## 테스트

```bash
python -m pytest tests -q
python scripts/run_e2e.py
```

`scripts/run_e2e.py`는 30프레임 이상 테스트 영상을 만들고 INSwapper inference를 실행한 뒤, 출력 파일을 FFprobe로 다시 엽니다. 로그는 `logs/e2e_report.json`과 `outputs/*.inference.json`에 남습니다.

단위 테스트는 합성 color+sine 클립으로 probe, 스트리밍 I/O, 트래커 ID 유지, 오디오 mux, export 검증을 확인합니다.

## 로그

- 앱 로그: `logs/app_YYYYMMDD.log`
- 환경 스냅샷: `logs/environment.json`
- 작업별 inference: `outputs/<name>.<ext>.inference.json`
- 임시 파일: `temp/` (앱이 오래된 항목을 정리)

오류가 나면 위 파일과 콘솔의 `INSWAPPER_INFERENCE` / `KEEP_ORIGINAL` 줄을 확인하세요.

## 안전장치

- 최초 실행 동의 확인란
- 기본 워터마크 `AI-altered`
- 사용 목적 메모 필드 (처리 로그에 기록)
- subprocess는 인자 배열만 사용

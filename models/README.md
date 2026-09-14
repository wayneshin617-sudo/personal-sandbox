# Models

이 폴더의 가중치는 Git에 포함하지 않습니다. `install_windows.bat`, `install_linux.sh`, 또는 앱의 다운로드 버튼이 아래 출처에서 받습니다.

모델이 없거나 체크섬이 맞지 않으면 **얼굴 교체 기능은 비활성화**됩니다. 원본 영상을 복사하거나 사진을 붙여 넣는 대체 합성은 하지 않습니다.

## 필수: 얼굴 검출 / 임베딩 (buffalo_l)

| 파일 | 역할 | 출처 |
| --- | --- | --- |
| `buffalo_l/det_10g.onnx` | SCRFD-10GF 얼굴 검출 + 5점 랜드마크 | InsightFace `buffalo_l` pack |
| `buffalo_l/w600k_r50.onnx` | ArcFace ResNet50 임베딩 (WebFace600K) | InsightFace `buffalo_l` pack |
| `buffalo_l/2d106det.onnx` | 106점 랜드마크 (선택) | InsightFace `buffalo_l` pack |

- 배포 ZIP: https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip
- 프로젝트: https://github.com/deepinsight/insightface
- 라이선스: InsightFace **모델은 비상업 연구 목적**이 일반 조건입니다. 코드(MIT)와 모델 조건이 다릅니다. 상업 사용 전 https://github.com/deepinsight/insightface 및 InsightFace 모델 라이선스를 직접 확인하세요.

ZIP을 받은 뒤 `models/buffalo_l/` 아래에 onnx 파일이 보이면 됩니다.

## 필수: 얼굴 교체 추론

| 파일 | 역할 | 출처 |
| --- | --- | --- |
| `inswapper_128.onnx` | InsightFace INSwapper identity transfer | InsightFace in_swapper 예제 |

- 문서: https://github.com/deepinsight/insightface/tree/master/examples/in_swapper
- Hugging Face 미러 (커뮤니티 업로드, SHA-256 검증):
  - https://huggingface.co/ApacheOne/insightface/resolve/main/insightface/inswapper_128.onnx
- 알려진 SHA-256: `0fa95f167682b4f61edf24f8d66c46b4ab130e8be058f00c8150e6d0170ca72f`
- 라이선스: InsightFace 모델 조건 (비상업 연구). 공식 데모는 Picsi.Ai로 이전되었으나 onnx 가중치는 위 경로에서 재현 가능합니다.

`buffalo_l` ArcFace 임베딩과만 짝이 맞습니다. 다른 인식 모델 임베딩을 넣으면 결과가 깨집니다.

## 선택: 얼굴 복원

| 파일 | 역할 | 출처 |
| --- | --- | --- |
| `gfpgan_1.4.onnx` | GFPGAN 1.4 얼굴 복원 | Tencent ARC GFPGAN |

- 원본: https://github.com/TencentARC/GFPGAN
- ONNX 미러: https://huggingface.co/facefusion/models-3.0.0/resolve/main/gfpgan_1.4.onnx
- 라이선스: Apache-2.0
- 파일이 없으면 복원 슬라이더는 무시되고 교체 결과만 사용합니다.

## 전체 인물 변환 (미설치)

아래는 Advanced 모드에 필요하지만 **이 프로젝트는 해당 체크포인트를  bundling하지 않으며, 없으면 기능을 끕니다.**

- OpenPose / DWPose / RTMPose
- Person segmentation (SAM 등)
- InstantID 또는 IP-Adapter FaceID
- Pose ControlNet + 비디오 temporal 모듈

CPU 또는 VRAM 부족 환경에서는 설치해도 실용적이지 않습니다.

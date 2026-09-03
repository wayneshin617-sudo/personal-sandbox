"""Project paths and runtime defaults."""

from __future__ import annotations

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
MODELS_DIR = ROOT_DIR / "models"
OUTPUTS_DIR = ROOT_DIR / "outputs"
TEMP_DIR = ROOT_DIR / "temp"
LOGS_DIR = ROOT_DIR / "logs"
TESTS_DIR = ROOT_DIR / "tests"

APP_NAME = "Studio"
APP_VERSION = "1.0.0"

CONSENT_TEXT = (
    "사용자는 입력 이미지와 영상의 사용 권한 및 당사자 동의를 확보했으며, "
    "결과물을 사칭, 괴롭힘, 명예훼손 또는 허위정보 제작에 사용하지 않습니다."
)

WATERMARK_TEXT = "AI-altered"
WATERMARK_DEFAULT = True

# Face detection / swap
DEFAULT_DET_SIZE = (640, 640)
DEFAULT_DET_THRESH = 0.50
DEFAULT_TRACK_THRESH = 0.35
DEFAULT_REID_THRESH = 0.45
DEFAULT_BLEND_STRENGTH = 0.90
DEFAULT_RESTORE_STRENGTH = 0.0
DEFAULT_MASK_RANGE = 0.70
MAX_TRACK_MISSES = 18
REID_MAX_LOST_FRAMES = 90

# Video
DEFAULT_PREVIEW_SECONDS = 2.0
MIN_E2E_FRAMES = 30
CHUNK_READ_FRAMES = 1

# Temp cleanup
TEMP_MAX_AGE_HOURS = 24

# Model filenames
BUFFALO_DIRNAME = "buffalo_l"
SCRFD_FILENAME = "det_10g.onnx"
ARCFACE_FILENAME = "w600k_r50.onnx"
LANDMARK_FILENAME = "2d106det.onnx"
INSWAPPER_FILENAME = "inswapper_128.onnx"
GFPGAN_FILENAME = "gfpgan_1.4.onnx"

# Known checksums (SHA-256). Empty string means "record after download, do not block".
MODEL_CHECKSUMS = {
    INSWAPPER_FILENAME: "0fa95f167682b4f61edf24f8d66c46b4ab130e8be058f00c8150e6d0170ca72f",
}

MODEL_URLS = {
    "buffalo_l.zip": [
        "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip",
        "https://huggingface.co/public-data/insightface/resolve/main/models/buffalo_l.zip",
    ],
    INSWAPPER_FILENAME: [
        "https://huggingface.co/ApacheOne/insightface/resolve/main/insightface/inswapper_128.onnx",
        "https://huggingface.co/ezioruan/inswapper_128.onnx/resolve/main/inswapper_128.onnx",
    ],
    GFPGAN_FILENAME: [
        "https://huggingface.co/facefusion/models-3.0.0/resolve/main/gfpgan_1.4.onnx",
    ],
}

COMPAT_DEFAULT_CONTAINER = "mp4"
COMPAT_DEFAULT_VIDEO_ENCODER = "libx264"
COMPAT_DEFAULT_AUDIO_ENCODER = "aac"

ANIMATION_CONTAINERS = {"gif", "webp", "apng"}


def ensure_runtime_dirs() -> None:
    for path in (MODELS_DIR, OUTPUTS_DIR, TEMP_DIR, LOGS_DIR):
        path.mkdir(parents=True, exist_ok=True)

#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "=== Identity Face Swap Studio - Linux install ==="
python3 - <<'PY'
import sys
print("Python", sys.version)
if sys.version_info < (3, 10):
    raise SystemExit("Python 3.10+ required")
PY

if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi || true
else
  echo "No nvidia-smi: CPU mode"
fi

if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
  echo "WARNING: install ffmpeg (includes ffprobe), e.g. sudo apt-get install -y ffmpeg"
fi

python - <<'PY'
from src.model_manager import download_models
download_models()
print("models ready")
PY

python check_environment.py
echo "Install finished."

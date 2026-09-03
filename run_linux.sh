#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -x .venv/bin/python ]]; then
  echo ".venv missing. Run ./install_linux.sh first."
  exit 1
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python check_environment.py
exec python -m streamlit run app.py --server.headless true --server.address 0.0.0.0

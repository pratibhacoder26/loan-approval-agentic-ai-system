#!/usr/bin/env bash
# Launch the Streamlit chatbot UI.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"

PYTHON_BIN="${PYTHON_BIN:-./venv/bin/python}"
PORT="${UI_PORT:-8501}"

exec "$PYTHON_BIN" -m streamlit run app/ui/streamlit_app.py \
    --server.port "$PORT" \
    --server.headless true

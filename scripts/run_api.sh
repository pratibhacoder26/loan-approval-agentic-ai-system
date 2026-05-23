#!/usr/bin/env bash
# Launch the FastAPI microservice.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"

PYTHON_BIN="${PYTHON_BIN:-./venv/bin/python}"
HOST="${API_HOST:-0.0.0.0}"
PORT="${API_PORT:-8000}"

exec "$PYTHON_BIN" -m uvicorn app.main:app --host "$HOST" --port "$PORT" --log-level info

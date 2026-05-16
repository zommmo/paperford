#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
fi

.venv/bin/python -m pip install -r requirements.txt

if [ ! -d "frontend/node_modules" ]; then
  (cd frontend && npm install)
fi

.venv/bin/python -m uvicorn api_app:app --host 127.0.0.1 --port 8000 &
api_pid=$!

cleanup() {
  kill "$api_pid" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

cd frontend
npm run dev

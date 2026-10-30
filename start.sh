#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if [[ ! -x .venv/bin/python ]]; then
  printf '%s\n' '请先安装：python3.12 -m venv .venv && .venv/bin/python -m pip install -r backend/requirements.lock.txt'
  exit 1
fi
if [[ ! -f frontend/dist/index.html ]]; then
  (cd frontend && npm ci --ignore-scripts && npm run build)
fi
export PYTHONPATH="$PWD/backend"
printf '%s\n' "GAIA 本地工作台：http://127.0.0.1:${PORT:-8765}" '按 Ctrl+C 停止服务。工作区保存在 .geoagent/'
exec .venv/bin/python -m uvicorn geoagent.app:app --host 127.0.0.1 --port "${PORT:-8765}"

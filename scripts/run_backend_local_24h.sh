#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${ROOT_DIR}/logs"
PID_FILE="${LOG_DIR}/backend.pid"
LOG_FILE="${LOG_DIR}/backend.log"

mkdir -p "${LOG_DIR}"

if [[ -f "${PID_FILE}" ]]; then
  OLD_PID="$(cat "${PID_FILE}" || true)"
  if [[ -n "${OLD_PID}" ]] && kill -0 "${OLD_PID}" 2>/dev/null; then
    echo "[run_backend_local_24h] already running pid=${OLD_PID}"
    exit 0
  fi
fi

cd "${ROOT_DIR}"
nohup python3 main.py --dashboard --port 3000 >>"${LOG_FILE}" 2>&1 &
NEW_PID=$!
echo "${NEW_PID}" > "${PID_FILE}"

echo "[run_backend_local_24h] started pid=${NEW_PID}"
echo "[run_backend_local_24h] log=${LOG_FILE}"


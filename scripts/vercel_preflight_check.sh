#!/usr/bin/env bash
set -euo pipefail

BACKEND_BASE_URL="${BACKEND_BASE_URL:-http://127.0.0.1:3010}"
API_KEY="${ARCHITECTURE_API_KEY:-}"
FRONTEND_ENV_FILE="${FRONTEND_ENV_FILE:-/workspace/dashboard-next/.env.local}"
EXPECTED_FRONTEND_ORIGIN="${EXPECTED_FRONTEND_ORIGIN:-https://your-project.vercel.app}"

if [[ -n "${API_KEY}" ]]; then
  AUTH_HEADER=(-H "x-api-key: ${API_KEY}")
else
  AUTH_HEADER=()
fi

echo "[preflight] backend=${BACKEND_BASE_URL}"
echo "[preflight] expected_frontend_origin=${EXPECTED_FRONTEND_ORIGIN}"

echo "[1/6] health check"
HEALTH_JSON="$(curl -sS "${BACKEND_BASE_URL}/api/health")"
echo "${HEALTH_JSON}" | python3 -m json.tool

echo "[2/6] ready check"
READY_JSON="$(curl -sS "${BACKEND_BASE_URL}/api/ready")"
echo "${READY_JSON}" | python3 -m json.tool

echo "[3/6] runtime profile check"
PROFILE_JSON="$(curl -sS "${BACKEND_BASE_URL}/api/runtime/profile")"
echo "${PROFILE_JSON}" | python3 -m json.tool

python3 - "$PROFILE_JSON" "$EXPECTED_FRONTEND_ORIGIN" <<'PY'
import json, sys
profile = json.loads(sys.argv[1])
expected_origin = sys.argv[2]
db = profile.get("db", {})
if db.get("active_backend") not in {"sqlite", "postgres"}:
    raise SystemExit("Invalid active backend")
cors = set(profile.get("cors_origins", []))
if expected_origin not in cors:
    raise SystemExit(f"Expected frontend origin missing from CORS: {expected_origin}")
print("[ok] runtime profile validation passed")
PY

echo "[4/6] metrics check"
METRICS_JSON="$(curl -sS "${BACKEND_BASE_URL}/api/metrics")"
echo "${METRICS_JSON}" | python3 -m json.tool

echo "[5/6] mutation auth check"
if [[ -n "${API_KEY}" ]]; then
  NO_KEY_STATUS="$(curl -sS -o /dev/null -w "%{http_code}" -X POST "${BACKEND_BASE_URL}/api/projects" -H "Content-Type: application/json" -d '{"project_id":"preflight-no-key","name":"preflight-no-key","repo_url":"https://example.com/no-key","default_branch":"master","tech_stack":"check"}')"
  if [[ "${NO_KEY_STATUS}" != "401" ]]; then
    echo "[error] API key is configured but unauthenticated mutation did not return 401 (got ${NO_KEY_STATUS})"
    exit 1
  fi
  echo "[ok] unauthenticated mutation blocked with 401"
fi

PROJECT_ID="preflight-$(date +%s)"
curl -sS -X POST "${BACKEND_BASE_URL}/api/projects" \
  "${AUTH_HEADER[@]}" \
  -H "Content-Type: application/json" \
  -d "{\"project_id\":\"${PROJECT_ID}\",\"name\":\"${PROJECT_ID}\",\"repo_url\":\"https://example.com/${PROJECT_ID}\",\"default_branch\":\"master\",\"tech_stack\":\"preflight\"}" \
  | python3 -m json.tool
echo "[ok] authenticated mutation succeeded"

echo "[6/6] frontend env file check (${FRONTEND_ENV_FILE})"
if [[ ! -f "${FRONTEND_ENV_FILE}" ]]; then
  echo "[warn] frontend env file not found: ${FRONTEND_ENV_FILE}"
  echo "       create from /workspace/dashboard-next/.env.local.example"
  exit 0
fi

python3 - "$FRONTEND_ENV_FILE" "$BACKEND_BASE_URL" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
expected_api = sys.argv[2]
env = {}
for raw in path.read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    env[k.strip()] = v.strip()

api = env.get("NEXT_PUBLIC_API_BASE", "")
ws = env.get("NEXT_PUBLIC_WS_BASE", "")
if not api:
    raise SystemExit("NEXT_PUBLIC_API_BASE missing")
if not ws:
    raise SystemExit("NEXT_PUBLIC_WS_BASE missing")
if not (api.startswith("http://") or api.startswith("https://")):
    raise SystemExit(f"Invalid NEXT_PUBLIC_API_BASE: {api}")
if not (ws.startswith("ws://") or ws.startswith("wss://")):
    raise SystemExit(f"Invalid NEXT_PUBLIC_WS_BASE: {ws}")
print(f"[ok] frontend env api={api}")
print(f"[ok] frontend env ws={ws}")
if api != expected_api:
    print(f"[warn] frontend API base ({api}) differs from check target ({expected_api})")
PY

echo
echo "[preflight] completed successfully"


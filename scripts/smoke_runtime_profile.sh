#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:3000}"
API_KEY="${ARCHITECTURE_API_KEY:-}"

echo "[smoke] base_url=${BASE_URL}"

if [[ -n "${API_KEY}" ]]; then
  AUTH_HEADER=(-H "x-api-key: ${API_KEY}")
else
  AUTH_HEADER=()
fi

echo "[smoke] /api/health"
curl -sS "${BASE_URL}/api/health" | python3 -m json.tool

echo "[smoke] /api/ready"
curl -sS "${BASE_URL}/api/ready" | python3 -m json.tool

echo "[smoke] /api/runtime/profile"
curl -sS "${BASE_URL}/api/runtime/profile" | python3 -m json.tool

echo "[smoke] /api/metrics"
curl -sS "${BASE_URL}/api/metrics" | python3 -m json.tool

echo "[smoke] mutation check (create project)"
curl -sS -X POST "${BASE_URL}/api/projects" \
  "${AUTH_HEADER[@]}" \
  -H "Content-Type: application/json" \
  -d '{"project_id":"smoke-local","name":"smoke-local","repo_url":"https://example.com/repo","default_branch":"master","tech_stack":"local"}' \
  | python3 -m json.tool


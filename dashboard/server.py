"""
dashboard/server.py

FastAPI 대시보드 서버. GET /, GET /api/status, POST /api/run.
"""

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# 프로젝트 루트 기준으로 import (server는 dashboard/ 안에 있음)
import sys
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from dashboard_state import get_snapshot, is_running
from usage_tracking import is_over_limit, reset_usage

app = FastAPI(title="Agent Team Dashboard")

# POST /api/run 에서 사용할 요청 바디 (실행은 main에서 래핑된 함수 호출)
class RunRequest(BaseModel):
    issue: int


@app.get("/", response_class=HTMLResponse)
def index():
    """대시보드 단일 페이지."""
    html_path = Path(__file__).resolve().parent / "static" / "index.html"
    if html_path.exists():
        return FileResponse(html_path)
    # fallback: 인라인 최소 HTML (static 미구성 시)
    return HTMLResponse(
        "<!DOCTYPE html><html><head><meta charset='utf-8'><title>Dashboard</title></head>"
        "<body><p>Dashboard static/index.html not found.</p><script>fetch('/api/status').then(r=>r.json()).then(d=>console.log(d));</script></body></html>"
    )


@app.get("/api/status")
def api_status():
    """현재 실행 상태 스냅샷. agents 배열 길이에 맞춰 프론트가 카드 렌더링."""
    return get_snapshot()


@app.post("/api/run")
def api_run(body: RunRequest):
    """단일 이슈 실행 트리거. 이미 실행 중이면 409. 사용량 상한 초과 시 403."""
    if is_running():
        raise HTTPException(status_code=409, detail="Already running")
    if is_over_limit():
        raise HTTPException(
            status_code=403,
            detail="Usage limit exceeded. Reset usage or increase limit in .env (USAGE_LIMIT_TOKENS / USAGE_LIMIT_CALLS).",
        )
    runner = getattr(app, "run_issue_fn", None)
    if runner is None:
        raise HTTPException(status_code=503, detail="Dashboard runner not registered")
    runner(body.issue)
    return {"ok": True, "issue": body.issue}


@app.post("/api/usage/reset")
def api_usage_reset():
    """사용량 초기화 (토큰/호출 횟수 0으로)."""
    reset_usage()
    return {"ok": True}


def register_runner(run_issue_fn):
    """main에서 호출: 백그라운드에서 이슈를 실행할 함수를 등록."""
    app.run_issue_fn = run_issue_fn

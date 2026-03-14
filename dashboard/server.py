"""
dashboard/server.py

FastAPI 대시보드 서버. GET /, GET /api/status, POST /api/run.
"""

import os
from pathlib import Path
from typing import Literal

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
from core.models import AgentRole, Project, TaskSource, TaskStatus
from core.orchestrator import ManagerOrchestrator
from core.repository import ArchitectureRepository
from core.queue import create_task_queue
from core.worker import WorkerRuntime

app = FastAPI(title="Agent Team Dashboard")

_db_backend = os.getenv("ARCHITECTURE_DB_BACKEND", "sqlite")
_db_path = os.getenv("ARCHITECTURE_DB_PATH", ".agent_architecture.db")
_postgres_dsn = os.getenv("ARCHITECTURE_POSTGRES_DSN")
_repo = ArchitectureRepository(
    db_path=_db_path,
    backend=_db_backend,
    postgres_dsn=_postgres_dsn,
)
_orchestrator = ManagerOrchestrator(_repo)
_task_queue = create_task_queue()
_worker_runtime = WorkerRuntime(_task_queue, _orchestrator)

# POST /api/run 에서 사용할 요청 바디 (실행은 main에서 래핑된 함수 호출)
class RunRequest(BaseModel):
    issue: int


class ProjectCreateRequest(BaseModel):
    project_id: str
    name: str
    repo_url: str
    default_branch: str = "master"
    tech_stack: str = ""


class TaskCreateRequest(BaseModel):
    project_id: str
    title: str
    description: str
    source: Literal["github", "cli", "discord", "scheduler"] = "cli"
    auto_enqueue: bool = False


class TaskStatusUpdateRequest(BaseModel):
    status: Literal["pending", "in_progress", "done", "failed"]


class ConversationCreateRequest(BaseModel):
    agent_role: Literal["pm", "cto", "developer", "qa", "architect", "marketing", "orchestrator"]
    content: str
    token_usage: int = 0


class WorkerRunOnceRequest(BaseModel):
    timeout_seconds: int = 1


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
    snapshot = get_snapshot()
    snapshot["github_repo"] = os.getenv("GITHUB_REPO") or ""
    return snapshot


@app.get("/api/projects")
def api_list_projects():
    return {"projects": [p.to_dict() for p in _repo.list_projects()]}


@app.post("/api/projects")
def api_upsert_project(body: ProjectCreateRequest):
    project = Project(
        project_id=body.project_id,
        name=body.name,
        repo_url=body.repo_url,
        default_branch=body.default_branch,
        tech_stack=body.tech_stack,
    )
    stored = _repo.upsert_project(project)
    return {"project": stored.to_dict()}


@app.get("/api/projects/{project_id}/tasks")
def api_list_project_tasks(project_id: str):
    project = _repo.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    tasks = _repo.list_tasks(project_id=project_id)
    return {"tasks": [t.to_dict() for t in tasks]}


@app.post("/api/tasks")
def api_create_task(body: TaskCreateRequest):
    project = _repo.get_project(body.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    result = _orchestrator.create_task_with_plan(
        project_id=body.project_id,
        title=body.title,
        description=body.description,
        source=TaskSource(body.source),
    )
    payload = result.to_dict()
    if body.auto_enqueue:
        job_id = _task_queue.enqueue(
            {
                "task_id": result.task.task_id,
                "project_id": result.task.project_id,
            }
        )
        payload["queue"] = {"enqueued": True, "job_id": job_id}
    else:
        payload["queue"] = {"enqueued": False}
    return payload


@app.patch("/api/tasks/{task_id}/status")
def api_update_task_status(task_id: str, body: TaskStatusUpdateRequest):
    updated = _orchestrator.update_status(task_id, TaskStatus(body.status))
    if not updated:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task": updated.to_dict()}


@app.get("/api/tasks/{task_id}/conversations")
def api_list_conversations(task_id: str):
    task = _repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    messages = _repo.list_conversations(task_id)
    return {"messages": [m.to_dict() for m in messages]}


@app.post("/api/tasks/{task_id}/conversations")
def api_add_conversation(task_id: str, body: ConversationCreateRequest):
    task = _repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    message = _orchestrator.add_message(
        task_id=task_id,
        role=AgentRole(body.agent_role),
        content=body.content,
        token_usage=body.token_usage,
    )
    return {"message": message.to_dict()}


@app.post("/api/tasks/{task_id}/enqueue")
def api_enqueue_task(task_id: str):
    task = _repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    job_id = _task_queue.enqueue({"task_id": task_id, "project_id": task.project_id})
    return {"ok": True, "task_id": task_id, "job_id": job_id}


@app.post("/api/workers/run-once")
def api_worker_run_once(body: WorkerRunOnceRequest):
    result = _worker_runtime.run_once(timeout_seconds=body.timeout_seconds)
    return {
        "ok": result.ok,
        "task_id": result.task_id,
        "message": result.message,
        "payload": result.payload,
    }


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

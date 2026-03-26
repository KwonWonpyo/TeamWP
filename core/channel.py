"""채널 추상화 레이어.

어떤 채널(GitHub Issues / Web Dashboard / CLI / Discord)로 지시가 들어오든
동일한 Task Queue로 진입하는 Instruction → Task 변환 레이어.

흐름:
    채널 → ChannelAdapter.ingest() → Instruction + WorkTask → Task Queue
    Task Queue → Worker → Orchestrator → Workflow (CrewAI)
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import Protocol

from core.models import Instruction, Project, TaskSource, WorkTask, utc_now_iso
from core.orchestrator import ManagerOrchestrator
from core.queue import TaskQueue
from core.repository import ArchitectureRepository


@dataclass
class IngestResult:
    instruction: Instruction
    task: WorkTask
    job_id: str


class ChannelAdapter(Protocol):
    """채널 추상 인터페이스."""
    def ingest(self, **kwargs) -> IngestResult: ...
    def notify(self, task_id: str, message: str) -> None: ...


# ──────────────────────────────────────────────────────────────
# GitHub Issues 채널
# ──────────────────────────────────────────────────────────────

class GithubIssueAdapter:
    """GitHub Issues 채널.

    이슈를 Instruction으로 변환하고 Task Queue에 진입시킨다.
    GITHUB_REPO 환경변수와 매칭되는 Project가 없으면 자동 생성한다.
    """

    def __init__(
        self,
        repo: ArchitectureRepository,
        orchestrator: ManagerOrchestrator,
        queue: TaskQueue,
    ):
        self.repo = repo
        self.orchestrator = orchestrator
        self.queue = queue

    def ingest(
        self,
        issue_number: int,
        title: str,
        body: str,
        project_id: str | None = None,
    ) -> IngestResult:
        """GitHub 이슈를 Task로 변환하고 큐에 넣는다."""
        if not project_id:
            project_id = self._resolve_project_id()

        instruction = Instruction(
            instruction_id=str(uuid.uuid4()),
            channel="github",
            product_id=project_id,
            raw_text=body,
            created_at=utc_now_iso(),
            github_issue_number=issue_number,
        )

        result = self.orchestrator.create_task_with_plan(
            project_id=project_id,
            title=title,
            description=body,
            source=TaskSource.GITHUB,
            issue_number=issue_number,
        )

        job_id = self.queue.enqueue(
            {
                "task_id": result.task.task_id,
                "project_id": project_id,
                "issue_number": issue_number,
            }
        )

        return IngestResult(instruction=instruction, task=result.task, job_id=job_id)

    def _resolve_project_id(self) -> str:
        """GITHUB_REPO 환경변수와 매칭되는 Project를 찾거나 자동 생성한다."""
        github_repo = os.getenv("GITHUB_REPO", "").strip()
        for p in self.repo.list_projects():
            if github_repo and (p.repo_url == github_repo or github_repo in p.get_repos()):
                return p.project_id

        # 없으면 자동 생성
        project_id = (
            f"github-{github_repo.replace('/', '-')}" if github_repo else str(uuid.uuid4())
        )
        project = Project(
            project_id=project_id,
            name=github_repo or "default",
            repo_url=github_repo,
            default_branch="main",
            tech_stack="",
        )
        if github_repo:
            project.set_repos([github_repo])
        self.repo.upsert_project(project)
        return project_id

    def notify(self, task_id: str, message: str) -> None:
        """태스크 완료 알림 (Phase 5: Discord 알림 구현 예정)."""
        pass


# ──────────────────────────────────────────────────────────────
# Web Dashboard 채널
# ──────────────────────────────────────────────────────────────

class DashboardAdapter:
    """웹 대시보드 채널.

    POST /api/instructions 수신 → Instruction → Task Queue.
    product_id로 대상 Product를 지정한다.
    """

    def __init__(
        self,
        repo: ArchitectureRepository,
        orchestrator: ManagerOrchestrator,
        queue: TaskQueue,
    ):
        self.repo = repo
        self.orchestrator = orchestrator
        self.queue = queue

    def ingest(
        self,
        product_id: str,
        raw_text: str,
        title: str | None = None,
    ) -> IngestResult:
        """대시보드 지시를 Task로 변환하고 큐에 넣는다."""
        instruction = Instruction(
            instruction_id=str(uuid.uuid4()),
            channel="dashboard",
            product_id=product_id,
            raw_text=raw_text,
            created_at=utc_now_iso(),
        )

        result = self.orchestrator.create_task_with_plan(
            project_id=product_id,
            title=title or raw_text[:80],
            description=raw_text,
            source=TaskSource.DASHBOARD,
        )

        job_id = self.queue.enqueue(
            {
                "task_id": result.task.task_id,
                "project_id": product_id,
            }
        )

        return IngestResult(instruction=instruction, task=result.task, job_id=job_id)

    def notify(self, task_id: str, message: str) -> None:
        """태스크 알림 (WebSocket은 dashboard/server.py WS 엔드포인트가 처리)."""
        pass

"""Manager Orchestrator 스켈레톤."""

from __future__ import annotations

from dataclasses import dataclass

from core.models import AgentRole, TaskSource, TaskStatus, TaskType, WorkTask, WorkflowStep
from core.repository import ArchitectureRepository
from core.workflow import TaskWorkflowEngine


@dataclass(slots=True)
class TaskPlanResult:
    task: WorkTask
    steps: list[WorkflowStep]

    def to_dict(self) -> dict:
        return {
            "task": self.task.to_dict(),
            "steps": [s.to_dict() for s in self.steps],
        }


class ManagerOrchestrator:
    """문서 기반 협업 플로우를 계획하고 conversation을 기록한다."""

    def __init__(self, repo: ArchitectureRepository, workflow_engine: TaskWorkflowEngine | None = None):
        self.repo = repo
        self.workflow_engine = workflow_engine or TaskWorkflowEngine(repo)

    def create_task_with_plan(
        self,
        project_id: str,
        title: str,
        description: str,
        source: TaskSource,
    ) -> TaskPlanResult:
        task = self.repo.create_task(
            project_id=project_id,
            title=title,
            description=description,
            source=source,
        )
        steps = self._build_default_plan()
        self.repo.add_conversation(
            task_id=task.task_id,
            agent_role=AgentRole.ORCHESTRATOR,
            content=f"Task created: {title}",
        )
        self.repo.add_conversation(
            task_id=task.task_id,
            agent_role=AgentRole.PM,
            content="요구사항 분석 및 스펙 초안 작성 시작",
        )
        return TaskPlanResult(task=task, steps=steps)

    def add_message(self, task_id: str, role: AgentRole, content: str, token_usage: int = 0):
        return self.repo.add_conversation(
            task_id=task_id,
            agent_role=role,
            content=content,
            token_usage=token_usage,
        )

    def update_status(self, task_id: str, status: TaskStatus) -> WorkTask | None:
        task = self.repo.update_task_status(task_id, status)
        if task:
            self.repo.add_conversation(
                task_id=task_id,
                agent_role=AgentRole.ORCHESTRATOR,
                content=f"Task status changed to {status.value}",
            )
        return task

    def execute_task(self, task_id: str) -> WorkTask | None:
        task = self.repo.get_task(task_id)
        if not task:
            return None

        self.update_status(task_id, TaskStatus.IN_PROGRESS)
        try:
            final_state = self.workflow_engine.execute(task)
            logs = final_state.get("logs", [])
            if logs:
                self.repo.add_conversation(
                    task_id=task_id,
                    agent_role=AgentRole.ORCHESTRATOR,
                    content=f"Workflow logs: {' | '.join(logs)}",
                )
            self.update_status(task_id, TaskStatus.DONE)
        except Exception as e:
            self.repo.add_conversation(
                task_id=task_id,
                agent_role=AgentRole.ORCHESTRATOR,
                content=f"Workflow execution failed: {e}",
            )
            self.update_status(task_id, TaskStatus.FAILED)
        return self.repo.get_task(task_id)

    @staticmethod
    def _build_default_plan() -> list[WorkflowStep]:
        return [
            WorkflowStep(
                sequence=1,
                role=AgentRole.PM,
                task_type=TaskType.PLAN_TASK,
                description="이슈 분석 및 기술 스펙 정의",
            ),
            WorkflowStep(
                sequence=2,
                role=AgentRole.CTO,
                task_type=TaskType.REVIEW_TASK,
                description="아키텍처/리스크 검토 및 구현 전략 확정",
            ),
            WorkflowStep(
                sequence=3,
                role=AgentRole.DEVELOPER,
                task_type=TaskType.CODE_TASK,
                description="코드 구현 및 브랜치 작업 수행",
            ),
            WorkflowStep(
                sequence=4,
                role=AgentRole.QA,
                task_type=TaskType.TEST_TASK,
                description="테스트/QA 게이트 수행",
            ),
            WorkflowStep(
                sequence=5,
                role=AgentRole.MARKETING,
                task_type=TaskType.PUBLISH_TASK,
                description="릴리즈 노트/PR 메시지 정리",
            ),
        ]

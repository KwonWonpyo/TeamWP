"""도메인 모델: 프로젝트/태스크/대화."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"


class TaskSource(str, Enum):
    GITHUB = "github"
    CLI = "cli"
    DISCORD = "discord"
    SCHEDULER = "scheduler"


class AgentRole(str, Enum):
    PM = "pm"
    CTO = "cto"
    DEVELOPER = "developer"
    QA = "qa"
    ARCHITECT = "architect"
    MARKETING = "marketing"
    ORCHESTRATOR = "orchestrator"


class TaskType(str, Enum):
    PLAN_TASK = "plan_task"
    CODE_TASK = "code_task"
    TEST_TASK = "test_task"
    REVIEW_TASK = "review_task"
    PUBLISH_TASK = "publish_task"


@dataclass(slots=True)
class Project:
    project_id: str
    name: str
    repo_url: str
    default_branch: str
    tech_stack: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class WorkTask:
    task_id: str
    project_id: str
    title: str
    description: str
    source: TaskSource
    status: TaskStatus
    created_at: str

    def to_dict(self) -> dict:
        data = asdict(self)
        data["source"] = self.source.value
        data["status"] = self.status.value
        return data


@dataclass(slots=True)
class ConversationMessage:
    message_id: str
    task_id: str
    agent_role: AgentRole
    content: str
    timestamp: str
    token_usage: int = 0

    def to_dict(self) -> dict:
        data = asdict(self)
        data["agent_role"] = self.agent_role.value
        return data


@dataclass(slots=True)
class WorkflowStep:
    sequence: int
    role: AgentRole
    task_type: TaskType
    description: str

    def to_dict(self) -> dict:
        data = asdict(self)
        data["role"] = self.role.value
        data["task_type"] = self.task_type.value
        return data

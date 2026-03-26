"""도메인 모델: 프로젝트/태스크/대화."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
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
    DASHBOARD = "dashboard"


class AgentRole(str, Enum):
    # 현재 팀 (바이스/아주르/플뢰르/엘시/베델)
    VICE = "vice"
    AZURE = "azure"
    FLEUR = "fleur"
    ELSI = "elsi"
    BETHEL = "bethel"
    # 시스템
    ORCHESTRATOR = "orchestrator"
    # 하위 호환 (레거시)
    PM = "pm"
    CTO = "cto"
    DEVELOPER = "developer"
    QA = "qa"
    ARCHITECT = "architect"
    MARKETING = "marketing"


class TaskType(str, Enum):
    PLAN_TASK = "plan_task"
    CODE_TASK = "code_task"
    TEST_TASK = "test_task"
    REVIEW_TASK = "review_task"
    PUBLISH_TASK = "publish_task"


@dataclass
class Project:
    project_id: str
    name: str
    repo_url: str
    default_branch: str
    tech_stack: str
    repos_json: str = ""  # JSON 직렬화된 workspace repo 목록

    def get_repos(self) -> list[str]:
        """워크스페이스 repo 목록. 없으면 repo_url 단일 항목으로 반환."""
        if self.repos_json:
            try:
                return json.loads(self.repos_json)
            except (json.JSONDecodeError, TypeError):
                pass
        return [self.repo_url] if self.repo_url else []

    def set_repos(self, repos: list[str]) -> None:
        self.repos_json = json.dumps(repos, ensure_ascii=False)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["repos"] = self.get_repos()
        return d


@dataclass
class WorkTask:
    task_id: str
    project_id: str
    title: str
    description: str
    source: TaskSource
    status: TaskStatus
    created_at: str
    issue_number: int | None = None  # GitHub Issues 채널에서 온 경우

    def to_dict(self) -> dict:
        data = asdict(self)
        data["source"] = self.source.value
        data["status"] = self.status.value
        return data


@dataclass
class Instruction:
    """채널로부터 수신된 원본 지시."""
    instruction_id: str
    channel: str          # "github" | "dashboard" | "cli" | "discord"
    product_id: str
    raw_text: str
    created_at: str
    github_issue_number: int | None = None


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

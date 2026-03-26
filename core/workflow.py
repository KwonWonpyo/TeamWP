"""Worker Architecture 워크플로우 실행기.

CrewAI를 실행 엔진으로 사용하는 커스텀 순차 워크플로우.
LangGraph 의존성 없음.

흐름:
  이슈 있음 (GitHub 소스):
    1단계. 바이스(PM) — 이슈 분석 + 팀 구성 JSON 출력
    2단계. 선발된 에이전트 동적 크루 실행

  이슈 없음 (Dashboard/CLI 소스):
    바이스가 태스크를 수신하고, Phase 3에서 GitHub 없는 태스크 구현 예정
"""

from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import TypedDict, Any

from crewai import Crew, Process

from core.models import AgentRole, WorkTask
from core.repository import ArchitectureRepository

CREW_TIMEOUT_SECONDS = int(os.getenv("CREW_TIMEOUT_SECONDS", "600"))
_DEFAULT_AGENT_IDS = ["dev", "qa"]


class WorkflowState(TypedDict):
    task_id: str
    project_id: str
    title: str
    description: str
    issue_number: int | None
    target_repos: list[str]
    logs: list[str]


class TaskWorkflowEngine:
    """바이스(PM) 플래닝 → 동적 에이전트 크루 순차 실행."""

    def __init__(self, repo: ArchitectureRepository):
        self.repo = repo

    def execute(self, task: WorkTask) -> dict[str, Any]:
        project = self.repo.get_project(task.project_id)
        target_repos = project.get_repos() if project else []

        initial: WorkflowState = {
            "task_id": task.task_id,
            "project_id": task.project_id,
            "title": task.title,
            "description": task.description,
            "issue_number": task.issue_number,
            "target_repos": target_repos,
            "logs": [],
        }
        return self._execute_workflow(initial)

    def _execute_workflow(self, state: WorkflowState) -> WorkflowState:
        issue_number = state.get("issue_number")

        if issue_number is None:
            # Dashboard/CLI 소스: GitHub 없는 실행 (Phase 3에서 확장)
            message = f"태스크 수신: {state['title']}"
            self.repo.add_conversation(state["task_id"], AgentRole.VICE, message)
            state["logs"].append(f"vice:{message}")
            self._run_non_github_crew(state)
        else:
            # GitHub 소스: 2단계 CrewAI 파이프라인
            self.repo.add_conversation(
                state["task_id"], AgentRole.VICE,
                f"GitHub 이슈 #{issue_number} 분석 시작",
            )

            # 1단계: 바이스 플래닝
            selected_ids = self._run_vice_planning(state, issue_number)
            self.repo.add_conversation(
                state["task_id"], AgentRole.VICE,
                f"팀 구성 완료: {', '.join(selected_ids)}",
            )
            state["logs"].append(f"vice:선발={selected_ids}")

            # 2단계: 동적 크루
            dynamic_ids = [a for a in selected_ids if a != "manager"]
            if dynamic_ids:
                result = self._run_dynamic_crew(state, issue_number, dynamic_ids)
                if result:
                    result_text = str(result)
                    self.repo.add_conversation(
                        state["task_id"], AgentRole.ORCHESTRATOR,
                        f"크루 실행 완료 ({len(dynamic_ids)}개 에이전트): {result_text[:500]}",
                    )
                    state["logs"].append("crew:완료")

                    # PR URL 추출 및 Discord 알림 (5-1)
                    pr_url = _extract_pr_url(result_text)
                    if pr_url:
                        self.repo.add_conversation(
                            state["task_id"], AgentRole.ORCHESTRATOR,
                            f"PR 생성됨: {pr_url} — 리뷰 후 머지해 주세요.",
                        )
                        state["logs"].append(f"pr:{pr_url}")
                        _notify_pr_created(issue_number, pr_url, state["title"])

        return state

    # ──────────────────────────────────────────────────────────
    # Stage 1: 바이스 플래닝
    # ──────────────────────────────────────────────────────────

    def _run_vice_planning(self, state: WorkflowState, issue_number: int) -> list[str]:
        """바이스(매니저)가 이슈를 분석하고 팀 구성 JSON을 반환한다. 실패 시 기본 세트 반환."""
        from tasks.tasks import create_issue_analysis_task, TASK_FACTORY
        from agents.agents import manager_agent

        task = create_issue_analysis_task(issue_number)
        crew = Crew(
            agents=[manager_agent],
            tasks=[task],
            process=Process.sequential,
            verbose=False,
        )

        with ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(crew.kickoff)
            try:
                result = fut.result(timeout=CREW_TIMEOUT_SECONDS)
            except FuturesTimeoutError:
                self.repo.add_conversation(
                    state["task_id"], AgentRole.VICE,
                    f"플래닝 타임아웃 ({CREW_TIMEOUT_SECONDS}초) — 기본 팀 사용: {_DEFAULT_AGENT_IDS}",
                )
                return _DEFAULT_AGENT_IDS
            except Exception as e:
                self.repo.add_conversation(
                    state["task_id"], AgentRole.VICE,
                    f"플래닝 실패: {e} — 기본 팀 사용: {_DEFAULT_AGENT_IDS}",
                )
                return _DEFAULT_AGENT_IDS

        agent_ids = _parse_agent_ids(result, TASK_FACTORY)
        return agent_ids or _DEFAULT_AGENT_IDS

    # ──────────────────────────────────────────────────────────
    # Stage 2: 동적 크루
    # ──────────────────────────────────────────────────────────

    def _run_dynamic_crew(
        self,
        state: WorkflowState,
        issue_number: int,
        agent_ids: list[str],
    ):
        """선발된 에이전트들로 동적 크루를 구성하고 실행한다."""
        from tasks.tasks import TASK_FACTORY
        from agents.agents import dev_agent, qa_agent, ui_designer_agent, ui_publisher_agent

        _AGENT_OBJ = {
            "azure": ui_designer_agent,
            "dev": dev_agent,
            "elcy": ui_publisher_agent,
            "qa": qa_agent,
        }

        feature_branch = f"feature/issue-{issue_number}"
        design_branch = f"design/issue-{issue_number}"

        tasks = []
        agents = []
        for aid in agent_ids:
            factory_fn = TASK_FACTORY.get(aid)
            agent_obj = _AGENT_OBJ.get(aid)
            if not factory_fn or not agent_obj:
                continue
            if aid == "azure":
                tasks.append(factory_fn(issue_number, design_branch))
            elif aid in ("dev", "elcy", "qa"):
                tasks.append(factory_fn(issue_number, feature_branch))
            else:
                tasks.append(factory_fn(issue_number))
            agents.append(agent_obj)

        if not tasks:
            return None

        crew = Crew(
            agents=agents,
            tasks=tasks,
            process=Process.sequential,
            verbose=False,
        )

        with ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(crew.kickoff)
            try:
                return fut.result(timeout=CREW_TIMEOUT_SECONDS)
            except FuturesTimeoutError:
                raise RuntimeError(f"크루 실행 시간 초과 ({CREW_TIMEOUT_SECONDS}초)")

    # ──────────────────────────────────────────────────────────
    # Non-GitHub 실행 (Dashboard/CLI — Phase 3에서 확장)
    # ──────────────────────────────────────────────────────────

    def _run_non_github_crew(self, state: WorkflowState) -> None:
        """GitHub 이슈 없는 소스(Dashboard 등)의 간소화된 실행."""
        self.repo.add_conversation(
            state["task_id"], AgentRole.FLEUR,
            f"태스크 '{state['title']}' 수신 — GitHub 이슈 없음, Phase 3 구현 예정",
        )
        state["logs"].append("non-github:수동 처리 필요")


# ──────────────────────────────────────────────────────────────────
# 유틸리티
# ──────────────────────────────────────────────────────────────────

_PR_URL_PATTERN = re.compile(
    r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/pull/\d+"
)


def _extract_pr_url(text: str) -> str | None:
    """CrewAI 실행 결과 텍스트에서 GitHub PR URL을 추출한다."""
    match = _PR_URL_PATTERN.search(text)
    return match.group(0) if match else None


def _notify_pr_created(issue_number: int | None, pr_url: str, title: str) -> None:
    """Discord PR 생성 알림 전송 (설정 누락 시 무시)."""
    try:
        from usage_tracking import send_discord_pr_created
        send_discord_pr_created(issue_number, pr_url, title)
    except Exception:
        pass


def _parse_agent_ids(result, task_factory: dict) -> list[str] | None:
    """매니저 출력의 JSON 블록에서 에이전트 ID 목록을 파싱한다."""
    text = ""
    if isinstance(result, str):
        text = result
    elif hasattr(result, "raw"):
        text = getattr(result, "raw", "") or ""
    else:
        text = str(result)

    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if not match:
        candidates = re.findall(r"\{[^{}]*\"agents\"\s*:[^{}]*\}", text, re.DOTALL)
        match_text = candidates[-1] if candidates else None
    else:
        match_text = match.group(1)

    if not match_text:
        return None

    try:
        data = json.loads(match_text)
        agents = data.get("agents", [])
        if isinstance(agents, list) and agents:
            valid = [a for a in agents if a in task_factory]
            return valid if valid else None
    except (json.JSONDecodeError, TypeError):
        pass
    return None

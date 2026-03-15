"""LangGraph 기반 워크플로우 스켈레톤.

LangGraph가 설치되지 않은 환경에서도 fallback 순차 실행으로 동작한다.
"""

from __future__ import annotations

from typing import TypedDict, Any

from core.models import AgentRole, WorkTask
from core.repository import ArchitectureRepository


class WorkflowState(TypedDict):
    task_id: str
    project_id: str
    title: str
    description: str
    logs: list[str]


class TaskWorkflowEngine:
    """PM -> CTO -> Developer -> QA -> Marketing 워크플로우 실행기."""

    def __init__(self, repo: ArchitectureRepository):
        self.repo = repo
        self._compiled_graph = self._try_build_langgraph()

    def execute(self, task: WorkTask) -> dict[str, Any]:
        initial: WorkflowState = {
            "task_id": task.task_id,
            "project_id": task.project_id,
            "title": task.title,
            "description": task.description,
            "logs": [],
        }
        if self._compiled_graph is not None:
            return self._compiled_graph.invoke(initial)
        return self._execute_fallback(initial)

    def _try_build_langgraph(self):
        try:
            from langgraph.graph import StateGraph, END
        except Exception:
            return None

        graph = StateGraph(WorkflowState)
        graph.add_node("pm", self._pm_node)
        graph.add_node("cto", self._cto_node)
        graph.add_node("developer", self._developer_node)
        graph.add_node("qa", self._qa_node)
        graph.add_node("marketing", self._marketing_node)

        graph.set_entry_point("pm")
        graph.add_edge("pm", "cto")
        graph.add_edge("cto", "developer")
        graph.add_edge("developer", "qa")
        graph.add_edge("qa", "marketing")
        graph.add_edge("marketing", END)

        return graph.compile()

    def _execute_fallback(self, state: WorkflowState) -> dict[str, Any]:
        state = self._pm_node(state)
        state = self._cto_node(state)
        state = self._developer_node(state)
        state = self._qa_node(state)
        state = self._marketing_node(state)
        return state

    def _pm_node(self, state: WorkflowState) -> WorkflowState:
        message = "요구사항 분석 및 기술 스펙 정리 완료"
        self.repo.add_conversation(state["task_id"], AgentRole.PM, message)
        state["logs"].append(f"pm:{message}")
        return state

    def _cto_node(self, state: WorkflowState) -> WorkflowState:
        message = "아키텍처/리스크 검토 및 구현 전략 확정"
        self.repo.add_conversation(state["task_id"], AgentRole.CTO, message)
        state["logs"].append(f"cto:{message}")
        return state

    def _developer_node(self, state: WorkflowState) -> WorkflowState:
        message = "코드 작업 단계 시작 (worker execution skeleton)"
        self.repo.add_conversation(state["task_id"], AgentRole.DEVELOPER, message)
        state["logs"].append(f"developer:{message}")
        return state

    def _qa_node(self, state: WorkflowState) -> WorkflowState:
        message = "QA 게이트 점검 완료"
        self.repo.add_conversation(state["task_id"], AgentRole.QA, message)
        state["logs"].append(f"qa:{message}")
        return state

    def _marketing_node(self, state: WorkflowState) -> WorkflowState:
        message = "PR/릴리즈 메시지 초안 작성 완료"
        self.repo.add_conversation(state["task_id"], AgentRole.MARKETING, message)
        state["logs"].append(f"marketing:{message}")
        return state


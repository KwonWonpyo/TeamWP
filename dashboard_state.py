"""
dashboard_state.py

대시보드용 공유 상태. 크루 실행(백그라운드 스레드)과 FastAPI가 동시에 접근하므로 Lock으로 보호.
Process.hierarchical 전환에 따라 어떤 에이전트가 선발되는지 사전에 알 수 없으므로,
작업실/휴게실 구분은 running 플래그 기준으로 단순화한다.
  - running=True: 전체 에이전트 작업실
  - running=False: 전체 에이전트 휴게실
"""

import threading
from typing import Any, Optional
from dataclasses import dataclass, field


@dataclass
class AgentState:
    id: str
    role: str
    state: str  # "idle" | "working" | "done"


@dataclass
class CurrentRun:
    issue_number: int
    current_task_index: int
    started_at: str
    completed_tasks: list[str] = field(default_factory=list)


_lock = threading.Lock()
_all_agents: list = []  # 서버 시작 시 등록된 전체 에이전트
_current_run: Optional[CurrentRun] = None
_last_result: str = ""
_processed_count: int = 0
_running: bool = False


def _make_agent_states(crew_agents: list[Any]) -> list:
    result = []
    for i, a in enumerate(crew_agents):
        role = getattr(a, "role", f"Agent {i}")
        aid = (role.lower().replace(" ", "_").replace("/", "_") or f"agent_{i}")[:50]
        result.append(AgentState(id=aid, role=role, state="idle"))
    return result


def init_agents_from_crew(crew_agents: list[Any]) -> None:
    """서버 시작 시 전체 에이전트 목록 등록."""
    global _all_agents
    with _lock:
        _all_agents = _make_agent_states(crew_agents)


def set_run_started(issue_number: int, started_at: str, run_agents: list[Any] | None = None) -> None:
    """크루 kickoff 직전: 현재 런 설정. hierarchical에서는 전체 에이전트가 작업실로 이동."""
    global _current_run, _running
    with _lock:
        _running = True
        _current_run = CurrentRun(
            issue_number=issue_number,
            current_task_index=0,
            started_at=started_at,
            completed_tasks=[],
        )
        for ag in _all_agents:
            ag.state = "working"


def on_task_complete(task_index: int, task_output_summary: str = "") -> None:
    """태스크 완료 콜백."""
    global _current_run
    with _lock:
        if _current_run is not None:
            _current_run.completed_tasks.append(task_output_summary or f"Task {task_index} done")
            _current_run.current_task_index = task_index + 1


def set_run_finished(result_summary: str = "", error: str = "") -> None:
    """크루 완료 또는 예외 시: last_result 갱신, running 해제."""
    global _last_result, _running, _processed_count, _current_run
    with _lock:
        _running = False
        _last_result = error if error else (result_summary or "완료")
        if _current_run is not None:
            _processed_count += 1
        _current_run = None
        for ag in _all_agents:
            ag.state = "idle"


def set_idle() -> None:
    """대기 상태로 초기화."""
    global _current_run
    with _lock:
        _current_run = None
        for ag in _all_agents:
            ag.state = "idle"


def is_running() -> bool:
    with _lock:
        return _running


def get_snapshot() -> dict:
    """API용 스냅샷. 스레드 안전."""
    try:
        from usage_tracking import get_usage
        usage = get_usage()
    except Exception:
        usage = {}
    with _lock:
        out = {
            "running": _running,
            # all_agents: 항상 전체 에이전트 목록 (휴게실/작업실 구분용)
            # running=True면 전체 에이전트 active=True (작업실), False면 전체 휴게실
            "all_agents": [
                {
                    "id": a.id,
                    "role": a.role,
                    "state": a.state,
                    "active": _running,
                }
                for a in _all_agents
            ],
            "current_run": (
                {
                    "issue_number": _current_run.issue_number,
                    "current_task_index": _current_run.current_task_index,
                    "started_at": _current_run.started_at,
                    "completed_tasks": list(_current_run.completed_tasks),
                }
                if _current_run else None
            ),
            "last_result": _last_result,
            "processed_count": _processed_count,
        }
        out["usage"] = usage
        return out

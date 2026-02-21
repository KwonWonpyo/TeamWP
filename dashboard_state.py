"""
dashboard_state.py

대시보드용 공유 상태. 크루 실행(백그라운드 스레드)과 FastAPI가 동시에 접근하므로 Lock으로 보호.
에이전트 수가 늘어나도 agents 리스트만 갱신하면 되도록 설계.
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
_all_agents: list = []  # 서버 시작 시 등록된 전체 에이전트 (변하지 않음)
_agents: list = []      # 현재 런에 선발된 에이전트 (런마다 재초기화)
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
    """서버 시작 시 전체 에이전트 목록 등록. _all_agents로 보존하며 대시보드 상시 표시에 사용."""
    global _agents, _all_agents
    with _lock:
        _all_agents = _make_agent_states(crew_agents)
        _agents = []  # 런 전까지 선발 목록 비움


def set_run_started(issue_number: int, started_at: str, run_agents: list[Any] | None = None) -> None:
    """크루 kickoff 직전: 현재 런 설정, 0번 에이전트 working.
    run_agents가 주어지면 해당 런의 실제 에이전트 목록으로 _agents를 재초기화한다.
    동적 팀 구성 시 런마다 에이전트 수가 달라지므로 반드시 선발 목록을 전달해야 한다.
    """
    global _current_run, _running, _agents
    with _lock:
        _running = True
        if run_agents is not None:
            _agents = _make_agent_states(run_agents)
        _current_run = CurrentRun(
            issue_number=issue_number,
            current_task_index=0,
            started_at=started_at,
            completed_tasks=[],
        )
        for i, ag in enumerate(_agents):
            ag.state = "working" if i == 0 else "idle"


def on_task_complete(task_index: int, task_output_summary: str = "") -> None:
    """태스크 N 완료 콜백: agents[N]=done, agents[N+1]=working(있으면), current_task_index 갱신."""
    global _current_run
    with _lock:
        if task_index < len(_agents):
            _agents[task_index].state = "done"
        if _current_run is not None:
            _current_run.completed_tasks.append(task_output_summary or f"Task {task_index} done")
            next_index = task_index + 1
            if next_index < len(_agents):
                _agents[next_index].state = "working"
                _current_run.current_task_index = next_index
            else:
                _current_run.current_task_index = -1  # all done


def set_run_finished(result_summary: str = "", error: str = "") -> None:
    """크루 완료 또는 예외 시: last_result 갱신, running 해제. 선발 에이전트 목록 유지(결과 확인용)."""
    global _last_result, _running, _processed_count, _current_run
    with _lock:
        _running = False
        _last_result = error if error else (result_summary or "완료")
        if _current_run is not None:
            _processed_count += 1
        _current_run = None
        # 완료 후 선발 에이전트 상태를 done으로 유지 (휴게실 복귀는 다음 런 시작 시)


def set_idle() -> None:
    """대기 상태로 초기화 (모든 에이전트 idle, current_run 없음)."""
    global _current_run, _agents
    with _lock:
        _current_run = None
        for ag in _agents:
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
        # 선발된 에이전트 id 세트 (작업실 표시 기준)
        active_ids = {a.id for a in _agents}
        # 선발 에이전트 상태 조회용 맵
        active_state_map = {a.id: a.state for a in _agents}

        out = {
            "running": _running,
            # all_agents: 항상 전체 에이전트 목록 (휴게실/작업실 구분용)
            "all_agents": [
                {
                    "id": a.id,
                    "role": a.role,
                    "state": active_state_map.get(a.id, "idle"),
                    "active": a.id in active_ids,
                }
                for a in _all_agents
            ],
            # agents: 하위 호환 (선발된 에이전트만)
            "agents": [
                {"id": a.id, "role": a.role, "state": a.state}
                for a in _agents
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

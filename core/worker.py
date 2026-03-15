"""Queue consumer worker runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.queue import TaskQueue
from core.orchestrator import ManagerOrchestrator


@dataclass(slots=True)
class WorkerResult:
    ok: bool
    task_id: str | None
    message: str
    payload: dict[str, Any] | None = None


class WorkerRuntime:
    """큐에서 task를 읽어 오케스트레이터 실행으로 전달."""

    def __init__(self, task_queue: TaskQueue, orchestrator: ManagerOrchestrator):
        self.task_queue = task_queue
        self.orchestrator = orchestrator

    def run_once(self, timeout_seconds: int = 1) -> WorkerResult:
        payload = self.task_queue.dequeue(timeout_seconds=timeout_seconds)
        if not payload:
            return WorkerResult(ok=True, task_id=None, message="No task in queue")

        task_id = payload.get("task_id")
        if not task_id:
            return WorkerResult(ok=False, task_id=None, message="Invalid payload: missing task_id", payload=payload)

        task = self.orchestrator.execute_task(task_id)
        if task is None:
            return WorkerResult(ok=False, task_id=task_id, message="Task not found", payload=payload)

        return WorkerResult(ok=True, task_id=task_id, message="Task executed", payload=payload)


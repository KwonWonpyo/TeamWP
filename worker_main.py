"""
worker_main.py

Phase 4 runtime용 워커 엔트리포인트.
큐에서 task를 소비해 Orchestrator workflow를 실행한다.
"""

from __future__ import annotations

import os
import time

from core.orchestrator import ManagerOrchestrator
from core.queue import create_task_queue
from core.repository import ArchitectureRepository
from core.worker import WorkerRuntime


def main():
    db_backend = os.getenv("ARCHITECTURE_DB_BACKEND", "sqlite")
    db_path = os.getenv("ARCHITECTURE_DB_PATH", ".agent_architecture.db")
    postgres_dsn = os.getenv("ARCHITECTURE_POSTGRES_DSN")
    poll_interval = float(os.getenv("WORKER_POLL_INTERVAL_SECONDS", "0.5"))
    dequeue_timeout = int(os.getenv("WORKER_DEQUEUE_TIMEOUT_SECONDS", "1"))

    repo = ArchitectureRepository(
        db_path=db_path,
        backend=db_backend,
        postgres_dsn=postgres_dsn,
    )
    orchestrator = ManagerOrchestrator(repo)
    task_queue = create_task_queue()
    runtime = WorkerRuntime(task_queue, orchestrator)

    print(
        "[worker] started",
        f"db_backend={db_backend}",
        f"queue_backend={os.getenv('ARCHITECTURE_QUEUE_BACKEND', 'local')}",
        sep=" | ",
    )

    while True:
        result = runtime.run_once(timeout_seconds=dequeue_timeout)
        if result.task_id:
            print(f"[worker] {result.message} task_id={result.task_id} ok={result.ok}")
        time.sleep(poll_interval)


if __name__ == "__main__":
    main()


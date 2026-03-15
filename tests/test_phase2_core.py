import os
import tempfile
import unittest

from core.models import Project, TaskSource
from core.orchestrator import ManagerOrchestrator
from core.queue import LocalTaskQueue
from core.repository import ArchitectureRepository
from core.worker import WorkerRuntime


class Phase2CoreTests(unittest.TestCase):
    def test_postgres_backend_requires_dsn(self):
        with self.assertRaises(ValueError):
            ArchitectureRepository(backend="postgres", postgres_dsn=None)

    def test_worker_no_task_returns_idle_result(self):
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.close()
        repo = ArchitectureRepository(db_path=tmp.name, backend="sqlite")
        orchestrator = ManagerOrchestrator(repo)
        worker = WorkerRuntime(LocalTaskQueue(), orchestrator)

        result = worker.run_once(timeout_seconds=1)
        self.assertTrue(result.ok)
        self.assertIsNone(result.task_id)
        self.assertIn("No task", result.message)

        os.remove(tmp.name)

    def test_worker_executes_enqueued_task(self):
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.close()
        repo = ArchitectureRepository(db_path=tmp.name, backend="sqlite")
        repo.upsert_project(
            Project(
                project_id="p1",
                name="project1",
                repo_url="https://example.com/repo.git",
                default_branch="master",
                tech_stack="python",
            )
        )
        orchestrator = ManagerOrchestrator(repo)
        task_plan = orchestrator.create_task_with_plan(
            project_id="p1",
            title="task-1",
            description="desc",
            source=TaskSource.CLI,
        )

        q = LocalTaskQueue()
        q.enqueue({"task_id": task_plan.task.task_id})
        worker = WorkerRuntime(q, orchestrator)
        run_result = worker.run_once(timeout_seconds=1)
        self.assertTrue(run_result.ok)

        updated = repo.get_task(task_plan.task.task_id)
        self.assertIsNotNone(updated)
        self.assertEqual(updated.status.value, "done")

        conv = repo.list_conversations(task_plan.task.task_id)
        self.assertGreaterEqual(len(conv), 7)

        os.remove(tmp.name)

    def test_hybrid_backend_falls_back_to_sqlite_without_postgres_dsn(self):
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.close()
        repo = ArchitectureRepository(
            db_path=tmp.name,
            backend="hybrid",
            postgres_dsn=None,
        )
        profile = repo.get_runtime_profile()
        self.assertEqual(profile["configured_backend"], "hybrid")
        self.assertEqual(profile["active_backend"], "sqlite")
        self.assertTrue(profile["fallback_active"])
        self.assertEqual(profile["fallback_reason"], "postgres_dsn_missing")
        os.remove(tmp.name)


if __name__ == "__main__":
    unittest.main()


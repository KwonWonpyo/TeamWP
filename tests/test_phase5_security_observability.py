import importlib
import os
import tempfile
import unittest

from fastapi.testclient import TestClient


class Phase5SecurityObservabilityTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.close()
        self.db_path = tmp.name

        os.environ["ARCHITECTURE_DB_PATH"] = self.db_path
        os.environ["ARCHITECTURE_DB_BACKEND"] = "sqlite"
        os.environ["ARCHITECTURE_QUEUE_BACKEND"] = "local"
        os.environ["ARCHITECTURE_API_KEY"] = "phase5-secret"

        import dashboard.server as server_module

        self.server = importlib.reload(server_module)
        self.client = TestClient(self.server.app)

    def tearDown(self):
        self.client.close()
        os.environ.pop("ARCHITECTURE_DB_PATH", None)
        os.environ.pop("ARCHITECTURE_DB_BACKEND", None)
        os.environ.pop("ARCHITECTURE_QUEUE_BACKEND", None)
        os.environ.pop("ARCHITECTURE_API_KEY", None)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_mutation_endpoints_require_api_key(self):
        no_key = self.client.post(
            "/api/projects",
            json={
                "project_id": "secure-p1",
                "name": "secure-p1",
                "repo_url": "https://github.com/org/secure-p1",
                "default_branch": "master",
                "tech_stack": "python",
            },
        )
        self.assertEqual(no_key.status_code, 401)

        with_key = self.client.post(
            "/api/projects",
            headers={"x-api-key": "phase5-secret"},
            json={
                "project_id": "secure-p1",
                "name": "secure-p1",
                "repo_url": "https://github.com/org/secure-p1",
                "default_branch": "master",
                "tech_stack": "python",
            },
        )
        self.assertEqual(with_key.status_code, 200)

    def test_websocket_requires_api_key_when_enabled(self):
        project_res = self.client.post(
            "/api/projects",
            headers={"x-api-key": "phase5-secret"},
            json={
                "project_id": "secure-ws",
                "name": "secure-ws",
                "repo_url": "https://github.com/org/secure-ws",
                "default_branch": "master",
                "tech_stack": "python",
            },
        )
        self.assertEqual(project_res.status_code, 200)

        task_res = self.client.post(
            "/api/tasks",
            headers={"x-api-key": "phase5-secret"},
            json={
                "project_id": "secure-ws",
                "title": "ws security",
                "description": "verify ws key",
                "source": "cli",
            },
        )
        task_id = task_res.json()["task"]["task_id"]

        with self.client.websocket_connect(f"/ws/tasks/{task_id}") as websocket:
            error_payload = websocket.receive_json()
            self.assertEqual(error_payload["type"], "error")
            self.assertIn("Invalid API key", error_payload["detail"])

        with self.client.websocket_connect(f"/ws/tasks/{task_id}?api_key=phase5-secret") as websocket:
            ok_payload = websocket.receive_json()
            self.assertEqual(ok_payload["type"], "task_feed")
            self.assertEqual(ok_payload["task_id"], task_id)

    def test_health_ready_and_metrics_endpoints(self):
        health = self.client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        self.assertTrue(health.json()["ok"])
        self.assertIn("db_active_backend", health.json())

        ready = self.client.get("/api/ready")
        self.assertEqual(ready.status_code, 200)
        self.assertTrue(ready.json()["ok"])
        self.assertIn("db_profile", ready.json())

        metrics = self.client.get("/api/metrics")
        self.assertEqual(metrics.status_code, 200)
        payload = metrics.json()
        self.assertIn("http_requests_total", payload)
        self.assertIn("ws_connections_total", payload)
        self.assertIn("task_executions_total", payload)

        runtime = self.client.get("/api/runtime/profile")
        self.assertEqual(runtime.status_code, 200)
        runtime_payload = runtime.json()
        self.assertIn("db", runtime_payload)
        self.assertIn("queue_backend", runtime_payload)


if __name__ == "__main__":
    unittest.main()


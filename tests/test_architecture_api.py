import importlib
import os
import tempfile
import unittest

from fastapi.testclient import TestClient


class ArchitectureApiTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.close()
        self.db_path = tmp.name
        os.environ["ARCHITECTURE_DB_PATH"] = self.db_path

        import dashboard.server as server_module

        self.server = importlib.reload(server_module)
        self.client = TestClient(self.server.app)

    def tearDown(self):
        self.client.close()
        os.environ.pop("ARCHITECTURE_DB_PATH", None)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_project_task_and_conversation_flow(self):
        project_res = self.client.post(
            "/api/projects",
            json={
                "project_id": "next-song",
                "name": "next-song",
                "repo_url": "https://github.com/org/next-song",
                "default_branch": "master",
                "tech_stack": "Next.js, FastAPI",
            },
        )
        self.assertEqual(project_res.status_code, 200)
        self.assertEqual(project_res.json()["project"]["project_id"], "next-song")

        create_task_res = self.client.post(
            "/api/tasks",
            json={
                "project_id": "next-song",
                "title": "Add OAuth login",
                "description": "Implement OAuth provider login",
                "source": "github",
            },
        )
        self.assertEqual(create_task_res.status_code, 200)
        payload = create_task_res.json()
        self.assertIn("task", payload)
        self.assertEqual(len(payload["steps"]), 5)
        task_id = payload["task"]["task_id"]

        conv_res = self.client.get(f"/api/tasks/{task_id}/conversations")
        self.assertEqual(conv_res.status_code, 200)
        conv_payload = conv_res.json()
        self.assertGreaterEqual(len(conv_payload["messages"]), 2)

        add_conv_res = self.client.post(
            f"/api/tasks/{task_id}/conversations",
            json={
                "agent_role": "developer",
                "content": "OAuth callback route implemented",
                "token_usage": 120,
            },
        )
        self.assertEqual(add_conv_res.status_code, 200)
        self.assertEqual(add_conv_res.json()["message"]["agent_role"], "developer")

        status_res = self.client.patch(
            f"/api/tasks/{task_id}/status",
            json={"status": "done"},
        )
        self.assertEqual(status_res.status_code, 200)
        self.assertEqual(status_res.json()["task"]["status"], "done")

        list_tasks_res = self.client.get("/api/projects/next-song/tasks")
        self.assertEqual(list_tasks_res.status_code, 200)
        self.assertEqual(list_tasks_res.json()["tasks"][0]["task_id"], task_id)

    def test_create_task_requires_existing_project(self):
        res = self.client.post(
            "/api/tasks",
            json={
                "project_id": "missing-project",
                "title": "Task",
                "description": "desc",
                "source": "cli",
            },
        )
        self.assertEqual(res.status_code, 404)


if __name__ == "__main__":
    unittest.main()

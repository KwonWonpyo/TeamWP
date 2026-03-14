"""SQLite 기반 저장소 계층."""

from __future__ import annotations

import sqlite3
import threading
import uuid
from pathlib import Path

from core.models import (
    AgentRole,
    ConversationMessage,
    Project,
    TaskSource,
    TaskStatus,
    WorkTask,
    utc_now_iso,
)


class ArchitectureRepository:
    """프로젝트/태스크/대화 데이터를 SQLite에 저장한다."""

    def __init__(self, db_path: str):
        self.db_path = str(Path(db_path))
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS projects (
                        project_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        repo_url TEXT NOT NULL,
                        default_branch TEXT NOT NULL,
                        tech_stack TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS tasks (
                        task_id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        description TEXT NOT NULL,
                        source TEXT NOT NULL,
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY(project_id) REFERENCES projects(project_id)
                    );

                    CREATE TABLE IF NOT EXISTS conversations (
                        message_id TEXT PRIMARY KEY,
                        task_id TEXT NOT NULL,
                        agent_role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        token_usage INTEGER NOT NULL DEFAULT 0,
                        FOREIGN KEY(task_id) REFERENCES tasks(task_id)
                    );
                    """
                )
                conn.commit()

    # ---------- projects ----------
    def upsert_project(self, project: Project) -> Project:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO projects (project_id, name, repo_url, default_branch, tech_stack)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(project_id) DO UPDATE SET
                        name=excluded.name,
                        repo_url=excluded.repo_url,
                        default_branch=excluded.default_branch,
                        tech_stack=excluded.tech_stack
                    """,
                    (
                        project.project_id,
                        project.name,
                        project.repo_url,
                        project.default_branch,
                        project.tech_stack,
                    ),
                )
                conn.commit()
        return project

    def list_projects(self) -> list[Project]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT project_id, name, repo_url, default_branch, tech_stack
                FROM projects
                ORDER BY name ASC
                """
            ).fetchall()
        return [self._row_to_project(r) for r in rows]

    def get_project(self, project_id: str) -> Project | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT project_id, name, repo_url, default_branch, tech_stack
                FROM projects
                WHERE project_id = ?
                """,
                (project_id,),
            ).fetchone()
        return self._row_to_project(row) if row else None

    # ---------- tasks ----------
    def create_task(
        self,
        project_id: str,
        title: str,
        description: str,
        source: TaskSource,
    ) -> WorkTask:
        task = WorkTask(
            task_id=str(uuid.uuid4()),
            project_id=project_id,
            title=title,
            description=description,
            source=source,
            status=TaskStatus.PENDING,
            created_at=utc_now_iso(),
        )
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO tasks (task_id, project_id, title, description, source, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task.task_id,
                        task.project_id,
                        task.title,
                        task.description,
                        task.source.value,
                        task.status.value,
                        task.created_at,
                    ),
                )
                conn.commit()
        return task

    def list_tasks(self, project_id: str | None = None) -> list[WorkTask]:
        query = """
            SELECT task_id, project_id, title, description, source, status, created_at
            FROM tasks
        """
        params: tuple = ()
        if project_id:
            query += " WHERE project_id = ?"
            params = (project_id,)
        query += " ORDER BY created_at DESC"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_task(r) for r in rows]

    def get_task(self, task_id: str) -> WorkTask | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT task_id, project_id, title, description, source, status, created_at
                FROM tasks
                WHERE task_id = ?
                """,
                (task_id,),
            ).fetchone()
        return self._row_to_task(row) if row else None

    def update_task_status(self, task_id: str, status: TaskStatus) -> WorkTask | None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE tasks SET status = ? WHERE task_id = ?",
                    (status.value, task_id),
                )
                conn.commit()
        return self.get_task(task_id)

    # ---------- conversations ----------
    def add_conversation(
        self,
        task_id: str,
        agent_role: AgentRole,
        content: str,
        token_usage: int = 0,
    ) -> ConversationMessage:
        message = ConversationMessage(
            message_id=str(uuid.uuid4()),
            task_id=task_id,
            agent_role=agent_role,
            content=content,
            timestamp=utc_now_iso(),
            token_usage=token_usage,
        )
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO conversations (message_id, task_id, agent_role, content, timestamp, token_usage)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        message.message_id,
                        message.task_id,
                        message.agent_role.value,
                        message.content,
                        message.timestamp,
                        message.token_usage,
                    ),
                )
                conn.commit()
        return message

    def list_conversations(self, task_id: str) -> list[ConversationMessage]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT message_id, task_id, agent_role, content, timestamp, token_usage
                FROM conversations
                WHERE task_id = ?
                ORDER BY timestamp ASC
                """,
                (task_id,),
            ).fetchall()
        return [self._row_to_message(r) for r in rows]

    # ---------- row mappers ----------
    @staticmethod
    def _row_to_project(row: sqlite3.Row) -> Project:
        return Project(
            project_id=row["project_id"],
            name=row["name"],
            repo_url=row["repo_url"],
            default_branch=row["default_branch"],
            tech_stack=row["tech_stack"],
        )

    @staticmethod
    def _row_to_task(row: sqlite3.Row) -> WorkTask:
        return WorkTask(
            task_id=row["task_id"],
            project_id=row["project_id"],
            title=row["title"],
            description=row["description"],
            source=TaskSource(row["source"]),
            status=TaskStatus(row["status"]),
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_message(row: sqlite3.Row) -> ConversationMessage:
        return ConversationMessage(
            message_id=row["message_id"],
            task_id=row["task_id"],
            agent_role=AgentRole(row["agent_role"]),
            content=row["content"],
            timestamp=row["timestamp"],
            token_usage=row["token_usage"],
        )

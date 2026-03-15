"""Task Queue 계층: Redis 기본, Local fallback."""

from __future__ import annotations

import json
import os
import queue
import uuid
from typing import Protocol, Any


class TaskQueue(Protocol):
    def enqueue(self, payload: dict[str, Any]) -> str: ...
    def dequeue(self, timeout_seconds: int = 1) -> dict[str, Any] | None: ...


class LocalTaskQueue:
    """Redis가 없을 때 사용하는 인메모리 큐."""

    def __init__(self):
        self._q: queue.Queue[str] = queue.Queue()

    def enqueue(self, payload: dict[str, Any]) -> str:
        item = dict(payload)
        item.setdefault("job_id", str(uuid.uuid4()))
        self._q.put(json.dumps(item))
        return item["job_id"]

    def dequeue(self, timeout_seconds: int = 1) -> dict[str, Any] | None:
        try:
            raw = self._q.get(timeout=timeout_seconds)
        except queue.Empty:
            return None
        return json.loads(raw)


class RedisTaskQueue:
    """Redis list(BRPOP/LPUSH) 기반 간단 큐."""

    def __init__(self, redis_url: str, queue_name: str = "agent:task_queue"):
        self.redis_url = redis_url
        self.queue_name = queue_name
        self.client = self._create_client(redis_url)

    @staticmethod
    def _create_client(redis_url: str):
        try:
            import redis
        except Exception as e:
            raise RuntimeError(
                "Redis queue를 사용하려면 redis 패키지가 필요합니다."
            ) from e
        return redis.Redis.from_url(redis_url, decode_responses=True)

    def enqueue(self, payload: dict[str, Any]) -> str:
        item = dict(payload)
        item.setdefault("job_id", str(uuid.uuid4()))
        self.client.lpush(self.queue_name, json.dumps(item))
        return item["job_id"]

    def dequeue(self, timeout_seconds: int = 1) -> dict[str, Any] | None:
        # BRPOP: (queue_name, value)
        result = self.client.brpop(self.queue_name, timeout=timeout_seconds)
        if not result:
            return None
        _, raw = result
        return json.loads(raw)


def create_task_queue() -> TaskQueue:
    backend = (os.getenv("ARCHITECTURE_QUEUE_BACKEND") or "local").lower()
    if backend == "redis":
        redis_url = os.getenv("ARCHITECTURE_REDIS_URL", "redis://127.0.0.1:6379/0")
        return RedisTaskQueue(redis_url=redis_url)
    return LocalTaskQueue()


from __future__ import annotations

import time
from datetime import datetime, timezone
from threading import Condition
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.json_store import load_json, save_json
from app.schemas.task import Task
from app.services.server_service import server_service


class TaskServiceError(Exception):
    pass


class TaskTimeoutError(TaskServiceError):
    pass


class TaskService:
    def __init__(self) -> None:
        self._task_records: List[Dict[str, Any]] = []
        self._next_id = 1
        self._condition = Condition()
        self._load_state()

    @staticmethod
    def _serialize_datetime(value: Optional[datetime]) -> Optional[str]:
        return value.isoformat() if value else None

    @staticmethod
    def _deserialize_datetime(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)

    def _serialize_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        return {
            **record,
            "created_at": self._serialize_datetime(record.get("created_at")),
            "started_at": self._serialize_datetime(record.get("started_at")),
            "finished_at": self._serialize_datetime(record.get("finished_at")),
        }

    def _deserialize_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        restored = dict(record)
        restored["created_at"] = self._deserialize_datetime(record.get("created_at")) or datetime.now(timezone.utc)
        restored["started_at"] = self._deserialize_datetime(record.get("started_at"))
        restored["finished_at"] = self._deserialize_datetime(record.get("finished_at"))
        restored.setdefault("payload", {})
        restored.setdefault("result", None)
        restored.setdefault("error", None)
        restored.setdefault("status", "pending")
        return restored

    def _load_state(self) -> None:
        raw_records = load_json(settings.task_state_file, [])
        self._task_records = [self._deserialize_record(item) for item in raw_records if isinstance(item, dict)]
        for record in self._task_records:
            if record["status"] == "running":
                record["status"] = "pending"
                record["started_at"] = None
                record["finished_at"] = None
                record["result"] = None
                record["error"] = None
        if self._task_records:
            self._next_id = max(record["id"] for record in self._task_records) + 1
        self._persist_locked()

    def _persist_locked(self) -> None:
        save_json(settings.task_state_file, [self._serialize_record(record) for record in self._task_records])

    def _find_record(self, task_id: int) -> Optional[Dict[str, Any]]:
        return next((record for record in self._task_records if record["id"] == task_id), None)

    def _to_task(self, record: Dict[str, Any]) -> Task:
        return Task(
            id=record["id"],
            server_id=record["server_id"],
            server_name=record["server_name"],
            agent_id=record["agent_id"],
            task_type=record["task_type"],
            payload=dict(record.get("payload", {})),
            status=record["status"],
            created_at=record["created_at"],
            started_at=record.get("started_at"),
            finished_at=record.get("finished_at"),
            result=record.get("result"),
            error=record.get("error"),
        )

    def create_task(self, *, server_id: int, server_name: str, agent_id: str, task_type: str, payload: Optional[Dict[str, Any]] = None) -> Task:
        with self._condition:
            record = {
                "id": self._next_id,
                "server_id": server_id,
                "server_name": server_name,
                "agent_id": agent_id,
                "task_type": task_type,
                "payload": dict(payload or {}),
                "status": "pending",
                "created_at": datetime.now(timezone.utc),
                "started_at": None,
                "finished_at": None,
                "result": None,
                "error": None,
            }
            self._task_records.append(record)
            self._next_id += 1
            self._persist_locked()
            self._condition.notify_all()
            return self._to_task(record)

    def claim_tasks(self, agent_id: str, limit: int = 5) -> List[Task]:
        with self._condition:
            claimed: List[Task] = []
            for record in sorted(self._task_records, key=lambda item: item["id"]):
                if len(claimed) >= limit:
                    break
                if record["agent_id"] != agent_id or record["status"] != "pending":
                    continue
                record["status"] = "running"
                record["started_at"] = datetime.now(timezone.utc)
                claimed.append(self._to_task(record))
            if claimed:
                self._persist_locked()
            return claimed

    def complete_task(self, *, agent_id: str, task_id: int, success: bool, result: Any = None, error: Optional[str] = None) -> Task:
        with self._condition:
            record = self._find_record(task_id)
            if record is None:
                raise TaskServiceError("任务不存在")
            if record["agent_id"] != agent_id:
                raise TaskServiceError("该任务不属于当前 Agent")
            if record["status"] in {"success", "failed"}:
                raise TaskServiceError("任务已经完成")

            if record["started_at"] is None:
                record["started_at"] = datetime.now(timezone.utc)
            record["finished_at"] = datetime.now(timezone.utc)
            record["result"] = result
            record["error"] = error
            record["status"] = "success" if success else "failed"
            self._persist_locked()
            self._condition.notify_all()
            return self._to_task(record)

    def wait_for_task(self, task_id: int, timeout: Optional[float] = None) -> Optional[Task]:
        timeout_value = timeout if timeout is not None else settings.task_wait_timeout_seconds
        deadline = time.monotonic() + timeout_value
        with self._condition:
            while True:
                record = self._find_record(task_id)
                if record is not None and record["status"] in {"success", "failed"}:
                    return self._to_task(record)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._condition.wait(timeout=remaining)

    def get_task(self, task_id: int) -> Optional[Task]:
        with self._condition:
            record = self._find_record(task_id)
            if record is None:
                return None
            return self._to_task(record)

    def list_tasks(self, server_id: Optional[int] = None, limit: int = 20) -> List[Task]:
        with self._condition:
            records = sorted(self._task_records, key=lambda item: item["id"], reverse=True)
            if server_id is not None:
                records = [record for record in records if record["server_id"] == server_id]
            return [self._to_task(record) for record in records[:limit]]

    def get_stats(self) -> Dict[str, int]:
        with self._condition:
            total_tasks = len(self._task_records)
            pending_tasks = sum(1 for record in self._task_records if record["status"] == "pending")
            running_tasks = sum(1 for record in self._task_records if record["status"] == "running")
            success_tasks = sum(1 for record in self._task_records if record["status"] == "success")
            failed_tasks = sum(1 for record in self._task_records if record["status"] == "failed")
            return {
                "total_tasks": total_tasks,
                "pending_tasks": pending_tasks,
                "running_tasks": running_tasks,
                "success_tasks": success_tasks,
                "failed_tasks": failed_tasks,
            }

    def dispatch_and_wait(self, server: Dict[str, Any], *, task_type: str, payload: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None) -> Task:
        agent_id = server.get("agent_id")
        if not agent_id:
            raise TaskServiceError("主机没有绑定 agent_id")
        if not server_service.is_server_online(server):
            raise TaskServiceError("Host Agent 当前离线，无法下发任务")

        task = self.create_task(
            server_id=server["id"],
            server_name=server["name"],
            agent_id=agent_id,
            task_type=task_type,
            payload=payload,
        )
        completed = self.wait_for_task(task.id, timeout=timeout)
        if completed is None:
            raise TaskTimeoutError(f"任务 #{task.id} 等待 Host Agent 超时")
        if completed.status != "success":
            raise TaskServiceError(completed.error or "Host Agent 执行失败")
        return completed



task_service = TaskService()

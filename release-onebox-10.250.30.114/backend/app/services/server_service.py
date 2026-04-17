from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
import subprocess
from threading import Lock
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.json_store import load_json, save_json
from app.schemas.agent import AgentHeartbeatRequest, AgentRegistrationRequest
from app.schemas.server import ConnectionTestResponse, Server, ServerCreate, ServerUpdate


class ServerService:
    HEARTBEAT_TIMEOUT_SECONDS = settings.heartbeat_timeout_seconds
    LEGACY_TEXT_REPLACEMENTS: Dict[str, str] = {
        "????????? Agent": "\u9884\u7f6e\u670d\u52a1\u5668\uff0c\u5f85\u63a5\u5165 Agent",
    }
    PRESET_SERVERS: List[Dict[str, Any]] = [
        {
            "name": f"10.250.30.{suffix}",
            "agent_id": f"agent-10-250-30-{suffix}",
            "host": f"10.250.30.{suffix}",
            "description": "\u9884\u7f6e\u670d\u52a1\u5668\uff0c\u5f85\u63a5\u5165 Agent",
            "tags": ["preset"],
        }
        for suffix in range(101, 107)
    ]

    def __init__(self) -> None:
        self._server_records: List[Dict[str, Any]] = []
        self._next_id = 1
        self._lock = Lock()
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
            "last_seen_at": self._serialize_datetime(record.get("last_seen_at")),
        }

    @classmethod
    def _repair_legacy_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return cls.LEGACY_TEXT_REPLACEMENTS.get(value, value)

    def _deserialize_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        restored = dict(record)
        restored["created_at"] = self._deserialize_datetime(record.get("created_at")) or datetime.now(timezone.utc)
        restored["last_seen_at"] = self._deserialize_datetime(record.get("last_seen_at"))
        restored["description"] = self._repair_legacy_text(record.get("description"))
        restored.setdefault("host", None)
        restored.setdefault("tags", [])
        restored.setdefault("status", "offline")
        restored.setdefault("agent_version", None)
        restored.setdefault("capabilities", [])
        restored.setdefault("management_ip", None)
        restored.setdefault("host_ip", None)
        restored.setdefault("reported_user", None)
        restored.setdefault("owner_user", None)
        restored.setdefault("os_name", None)
        restored.setdefault("runtime", None)
        restored.setdefault("cpu_percent", None)
        restored.setdefault("memory_percent", None)
        restored.setdefault("memory_total_bytes", None)
        restored.setdefault("memory_used_bytes", None)
        return restored

    def _load_state(self) -> None:
        raw_records = load_json(settings.server_state_file, [])
        self._server_records = [self._deserialize_record(item) for item in raw_records if isinstance(item, dict)]
        if self._server_records:
            self._next_id = max(record["id"] for record in self._server_records) + 1

        self._ensure_preset_servers()
        repaired_records = [self._serialize_record(record) for record in self._server_records]
        if repaired_records != raw_records:
            save_json(settings.server_state_file, repaired_records)

    def _persist_locked(self) -> None:
        save_json(settings.server_state_file, [self._serialize_record(record) for record in self._server_records])

    def _ensure_preset_servers(self) -> None:
        records_by_agent_id = {str(record.get("agent_id") or ""): record for record in self._server_records}
        for preset in self.PRESET_SERVERS:
            existing = records_by_agent_id.get(preset["agent_id"])
            if existing is not None:
                existing["name"] = preset["name"]
                existing["host"] = preset["host"]
                existing["description"] = preset["description"]
                existing["tags"] = list(preset.get("tags", []))
                existing.setdefault("management_ip", preset["host"])
                existing.setdefault("host_ip", preset["host"])
                continue

            record = {
                **preset,
                "id": self._next_id,
                "status": "offline",
                "created_at": datetime.now(timezone.utc),
                "last_seen_at": None,
                "agent_version": None,
                "capabilities": [],
                "management_ip": preset["host"],
                "host_ip": preset["host"],
                "reported_user": None,
                "os_name": None,
                "runtime": None,
                "cpu_percent": None,
                "memory_percent": None,
                "memory_total_bytes": None,
                "memory_used_bytes": None,
            }
            self._server_records.append(record)
            records_by_agent_id[preset["agent_id"]] = record
            self._next_id += 1

    @staticmethod
    def _choose_ping_target(record: Dict[str, Any]) -> Optional[str]:
        for key in ("management_ip", "host_ip", "host"):
            value = record.get(key)
            if value:
                return str(value).strip()
        return None

    def ping_server(self, server_id: int) -> ConnectionTestResponse:
        with self._lock:
            record = self._get_record(server_id)
            if record is None:
                return ConnectionTestResponse(success=False, message="\u5bbf\u4e3b\u673a\u4e0d\u5b58\u5728", checked_at=datetime.now(timezone.utc))

        target = self._choose_ping_target(record)
        if not target:
            return ConnectionTestResponse(success=False, message="\u672a\u914d\u7f6e\u53ef\u7528\u7684\u4e3b\u673a\u5730\u5740\uff0c\u65e0\u6cd5 Ping", checked_at=datetime.now(timezone.utc))

        try:
            completed = subprocess.run(
                ["ping", "-c", "1", "-W", "2", target],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
        except FileNotFoundError:
            return ConnectionTestResponse(success=False, message="\u5bb9\u5668\u5185\u7f3a\u5c11 ping \u547d\u4ee4", checked_at=datetime.now(timezone.utc))
        except subprocess.TimeoutExpired:
            return ConnectionTestResponse(success=False, message=f"Ping {target} \u8d85\u65f6", checked_at=datetime.now(timezone.utc))

        output = "\n".join(part for part in [completed.stdout, completed.stderr] if part).strip()
        if completed.returncode == 0:
            latency_ms = None
            match = re.search(r"time=([0-9.]+) ms", completed.stdout or "")
            if match:
                try:
                    latency_ms = float(match.group(1))
                except ValueError:
                    latency_ms = None
            message = f"Ping {target} \u6210\u529f"
            if latency_ms is not None:
                message += f"\uff0c\u5ef6\u8fdf {latency_ms:.2f} ms"
            return ConnectionTestResponse(success=True, message=message, checked_at=datetime.now(timezone.utc), latency_ms=latency_ms)

        message = output.splitlines()[-1] if output else f"Ping {target} \u5931\u8d25"
        return ConnectionTestResponse(success=False, message=message, checked_at=datetime.now(timezone.utc))

    def _get_record(self, server_id: int) -> Optional[Dict[str, Any]]:
        return next((record for record in self._server_records if record["id"] == server_id), None)

    def _find_by_agent_id(self, agent_id: str) -> Optional[Dict[str, Any]]:
        return next((record for record in self._server_records if record["agent_id"] == agent_id), None)

    def _refresh_status(self, record: Dict[str, Any]) -> None:
        last_seen = record.get("last_seen_at")
        if last_seen and datetime.now(timezone.utc) - last_seen <= timedelta(seconds=self.HEARTBEAT_TIMEOUT_SECONDS):
            record["status"] = "online"
        else:
            record["status"] = "offline"

    def _to_public(self, record: Dict[str, Any]) -> Server:
        self._refresh_status(record)
        return Server(
            id=record["id"],
            name=record["name"],
            agent_id=record["agent_id"],
            host=record.get("host"),
            description=record.get("description"),
            tags=list(record.get("tags", [])),
            status=record.get("status", "offline"),
            created_at=record["created_at"],
            last_seen_at=record.get("last_seen_at"),
            agent_version=record.get("agent_version"),
            capabilities=list(record.get("capabilities", [])),
            management_ip=record.get("management_ip"),
            host_ip=record.get("host_ip"),
            reported_user=record.get("reported_user"),
            owner_user=record.get("owner_user"),
            os_name=record.get("os_name"),
            runtime=record.get("runtime"),
            cpu_percent=record.get("cpu_percent"),
            memory_percent=record.get("memory_percent"),
            memory_total_bytes=record.get("memory_total_bytes"),
            memory_used_bytes=record.get("memory_used_bytes"),
        )

    def _build_auto_record(
        self,
        *,
        agent_id: str,
        host: Optional[str],
        version: Optional[str],
        capabilities: List[str],
        description: str,
        default_name: Optional[str] = None,
        management_ip: Optional[str] = None,
        host_ip: Optional[str] = None,
        reported_user: Optional[str] = None,
        owner_user: Optional[str] = None,
        os_name: Optional[str] = None,
        runtime: Optional[str] = None,
        cpu_percent: Optional[float] = None,
        memory_percent: Optional[float] = None,
        memory_total_bytes: Optional[int] = None,
        memory_used_bytes: Optional[int] = None,
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        return {
            "id": self._next_id,
            "name": default_name or agent_id,
            "agent_id": agent_id,
            "host": host,
            "description": description,
            "tags": ["auto-registered"],
            "status": "online",
            "created_at": now,
            "last_seen_at": now,
            "agent_version": version,
            "capabilities": list(capabilities),
            "management_ip": management_ip,
            "host_ip": host_ip,
            "reported_user": reported_user,
            "owner_user": owner_user,
            "os_name": os_name,
            "runtime": runtime,
            "cpu_percent": cpu_percent,
            "memory_percent": memory_percent,
            "memory_total_bytes": memory_total_bytes,
            "memory_used_bytes": memory_used_bytes,
        }

    def _upsert_agent_record(
        self,
        *,
        agent_id: str,
        host: Optional[str],
        version: Optional[str],
        capabilities: List[str],
        name: Optional[str] = None,
        description: str,
        management_ip: Optional[str] = None,
        host_ip: Optional[str] = None,
        reported_user: Optional[str] = None,
        owner_user: Optional[str] = None,
        os_name: Optional[str] = None,
        runtime: Optional[str] = None,
        cpu_percent: Optional[float] = None,
        memory_percent: Optional[float] = None,
        memory_total_bytes: Optional[int] = None,
        memory_used_bytes: Optional[int] = None,
    ) -> Dict[str, Any]:
        record = self._find_by_agent_id(agent_id)
        if record is None:
            record = self._build_auto_record(
                agent_id=agent_id,
                host=host,
                version=version,
                capabilities=capabilities,
                description=description,
                default_name=name,
                management_ip=management_ip,
                host_ip=host_ip,
                reported_user=reported_user,
                owner_user=owner_user,
                os_name=os_name,
                runtime=runtime,
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_total_bytes=memory_total_bytes,
                memory_used_bytes=memory_used_bytes,
            )
            self._server_records.append(record)
            self._next_id += 1
            return record

        if name:
            record["name"] = name
        if host is not None:
            record["host"] = host
        if version is not None:
            record["agent_version"] = version
        record["capabilities"] = list(capabilities)
        record["last_seen_at"] = datetime.now(timezone.utc)
        record["status"] = "online"
        if management_ip is not None:
            record["management_ip"] = management_ip
        if host_ip is not None:
            record["host_ip"] = host_ip
        if reported_user is not None:
            record["reported_user"] = reported_user
        if owner_user is not None:
            record["owner_user"] = owner_user
        if os_name is not None:
            record["os_name"] = os_name
        if runtime is not None:
            record["runtime"] = runtime
        if cpu_percent is not None:
            record["cpu_percent"] = cpu_percent
        if memory_percent is not None:
            record["memory_percent"] = memory_percent
        if memory_total_bytes is not None:
            record["memory_total_bytes"] = memory_total_bytes
        if memory_used_bytes is not None:
            record["memory_used_bytes"] = memory_used_bytes
        return record

    def is_server_online(self, record: Dict[str, Any]) -> bool:
        last_seen = record.get("last_seen_at")
        if not last_seen:
            return False
        return datetime.now(timezone.utc) - last_seen <= timedelta(seconds=self.HEARTBEAT_TIMEOUT_SECONDS)

    def list_servers(self) -> List[Server]:
        with self._lock:
            records = sorted(self._server_records, key=lambda item: item["id"])
            return [self._to_public(record) for record in records]

    def get_server(self, server_id: int) -> Optional[Server]:
        with self._lock:
            record = self._get_record(server_id)
            if record is None:
                return None
            return self._to_public(record)

    def get_server_record(self, server_id: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            record = self._get_record(server_id)
            if record is None:
                return None
            self._refresh_status(record)
            return dict(record)

    def create_server(self, payload: ServerCreate) -> Server:
        with self._lock:
            if self._find_by_agent_id(payload.agent_id) is not None:
                raise ValueError(f"agent_id '{payload.agent_id}' \u5df2\u5b58\u5728")

            record = payload.model_dump()
            record["id"] = self._next_id
            record["status"] = "offline"
            record["created_at"] = datetime.now(timezone.utc)
            record["last_seen_at"] = None
            record["agent_version"] = None
            record["capabilities"] = []
            record["management_ip"] = None
            record["host_ip"] = None
            record["reported_user"] = None
            record["owner_user"] = None
            record["os_name"] = None
            record["runtime"] = None
            record["cpu_percent"] = None
            record["memory_percent"] = None
            record["memory_total_bytes"] = None
            record["memory_used_bytes"] = None
            self._server_records.append(record)
            self._next_id += 1
            self._persist_locked()
            return self._to_public(record)

    def update_server(self, server_id: int, payload: ServerUpdate) -> Optional[Server]:
        with self._lock:
            record = self._get_record(server_id)
            if record is None:
                return None

            updates = payload.model_dump(exclude_unset=True)
            new_agent_id = updates.get("agent_id")
            if new_agent_id and new_agent_id != record["agent_id"] and self._find_by_agent_id(new_agent_id) is not None:
                raise ValueError(f"agent_id '{new_agent_id}' \u5df2\u5b58\u5728")

            for key, value in updates.items():
                record[key] = value
            self._persist_locked()
            return self._to_public(record)

    def delete_server(self, server_id: int) -> bool:
        with self._lock:
            original_length = len(self._server_records)
            self._server_records = [record for record in self._server_records if record["id"] != server_id]
            deleted = len(self._server_records) < original_length
            if deleted:
                self._persist_locked()
            return deleted

    def register_agent(self, payload: AgentRegistrationRequest) -> Server:
        with self._lock:
            record = self._upsert_agent_record(
                agent_id=payload.agent_id,
                name=payload.name,
                host=payload.host,
                version=payload.version,
                capabilities=payload.capabilities,
                management_ip=payload.management_ip,
                host_ip=payload.host_ip,
                reported_user=payload.reported_user,
                owner_user=None,
                os_name=payload.os_name,
                runtime=payload.runtime,
                cpu_percent=payload.cpu_percent,
                memory_percent=payload.memory_percent,
                memory_total_bytes=payload.memory_total_bytes,
                memory_used_bytes=payload.memory_used_bytes,
                description="\u7531 Host Agent \u81ea\u52a8\u6ce8\u518c",
            )
            self._persist_locked()
            return self._to_public(record)

    def heartbeat_agent(self, agent_id: str, payload: AgentHeartbeatRequest) -> Server:
        with self._lock:
            record = self._upsert_agent_record(
                agent_id=agent_id,
                host=payload.host,
                version=payload.version,
                capabilities=payload.capabilities,
                management_ip=payload.management_ip,
                host_ip=payload.host_ip,
                reported_user=payload.reported_user,
                owner_user=None,
                os_name=payload.os_name,
                runtime=payload.runtime,
                cpu_percent=payload.cpu_percent,
                memory_percent=payload.memory_percent,
                memory_total_bytes=payload.memory_total_bytes,
                memory_used_bytes=payload.memory_used_bytes,
                description="\u7531 Host Agent \u5fc3\u8df3\u81ea\u52a8\u521b\u5efa",
            )
            self._persist_locked()
            return self._to_public(record)

    def test_connection(self, server_id: int) -> ConnectionTestResponse:
        with self._lock:
            record = self._get_record(server_id)
            if record is None:
                return ConnectionTestResponse(
                    success=False,
                    message="\u5bbf\u4e3b\u673a\u4e0d\u5b58\u5728",
                    checked_at=datetime.now(timezone.utc),
                )

            self._refresh_status(record)
            if record["status"] == "online" and record.get("last_seen_at") is not None:
                seconds = round((datetime.now(timezone.utc) - record["last_seen_at"]).total_seconds(), 2)
                return ConnectionTestResponse(
                    success=True,
                    message=f"Host Agent \u5728\u7ebf\uff0c\u6700\u8fd1\u5fc3\u8df3 {seconds} \u79d2\u524d",
                    checked_at=datetime.now(timezone.utc),
                    latency_ms=None,
                )

            return ConnectionTestResponse(
                success=False,
                message="Host Agent \u79bb\u7ebf\uff0c\u8bf7\u786e\u8ba4\u5bbf\u4e3b\u673a Agent \u5df2\u542f\u52a8",
                checked_at=datetime.now(timezone.utc),
                latency_ms=None,
            )

    def get_stats(self) -> Dict[str, int]:
        with self._lock:
            online_servers = 0
            for record in self._server_records:
                self._refresh_status(record)
                if record["status"] == "online":
                    online_servers += 1
            total_servers = len(self._server_records)
            return {
                "total_servers": total_servers,
                "online_servers": online_servers,
                "offline_servers": max(total_servers - online_servers, 0),
            }


server_service = ServerService()

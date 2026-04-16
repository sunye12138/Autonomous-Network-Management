from __future__ import annotations

from app.core.config import settings
from app.schemas.system import SystemOverview
from app.services.artifact_service import artifact_service
from app.services.server_service import server_service
from app.services.task_service import task_service


class SystemService:
    def get_overview(self) -> SystemOverview:
        server_stats = server_service.get_stats()
        task_stats = task_service.get_stats()
        capabilities = sorted({capability for server in server_service.list_servers() for capability in server.capabilities})
        artifact_stats = artifact_service.get_stats()
        return SystemOverview(
            api_prefix=settings.api_prefix,
            artifact_dir=str(settings.artifact_dir),
            heartbeat_timeout_seconds=settings.heartbeat_timeout_seconds,
            agent_heartbeat_interval_seconds=settings.agent_heartbeat_interval_seconds,
            agent_poll_interval_seconds=settings.agent_poll_interval_seconds,
            capabilities=capabilities,
            **server_stats,
            **task_stats,
            **artifact_stats,
        )


system_service = SystemService()

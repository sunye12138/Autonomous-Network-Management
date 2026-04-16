from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class SystemOverview(BaseModel):
    architecture: str = Field(default="web-portal -> api-server -> host-agent")
    api_prefix: str
    artifact_dir: str
    total_servers: int
    online_servers: int
    offline_servers: int
    total_tasks: int
    pending_tasks: int
    running_tasks: int
    success_tasks: int
    failed_tasks: int
    total_artifacts: int
    heartbeat_timeout_seconds: int
    agent_heartbeat_interval_seconds: int
    agent_poll_interval_seconds: int
    capabilities: List[str] = Field(default_factory=list)

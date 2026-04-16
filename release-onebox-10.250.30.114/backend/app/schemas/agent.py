from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import normalize_optional_string, normalize_required_string, normalize_string_list


class AgentInfoBase(BaseModel):
    host: Optional[str] = Field(default=None, max_length=255)
    management_ip: Optional[str] = Field(default=None, max_length=255)
    host_ip: Optional[str] = Field(default=None, max_length=255)
    reported_user: Optional[str] = Field(default=None, max_length=255)
    os_name: Optional[str] = Field(default=None, max_length=255)
    runtime: Optional[str] = Field(default=None, max_length=255)
    version: Optional[str] = Field(default=None, max_length=50)
    capabilities: List[str] = Field(default_factory=list)
    cpu_percent: Optional[float] = Field(default=None, ge=0, le=100)
    memory_percent: Optional[float] = Field(default=None, ge=0, le=100)
    memory_total_bytes: Optional[int] = Field(default=None, ge=0)
    memory_used_bytes: Optional[int] = Field(default=None, ge=0)

    @field_validator("host", "management_ip", "host_ip", "reported_user", "os_name", "runtime", "version", mode="before")
    @classmethod
    def _normalize_optional_strings(cls, value: object) -> object:
        return normalize_optional_string(value)

    @field_validator("capabilities", mode="before")
    @classmethod
    def _normalize_capabilities(cls, value: object) -> object:
        return normalize_string_list(value)


class AgentRegistrationRequest(AgentInfoBase):
    agent_id: str = Field(..., min_length=1, max_length=100)
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)

    @field_validator("agent_id", mode="before")
    @classmethod
    def _normalize_agent_id(cls, value: object) -> object:
        return normalize_required_string(value)

    @field_validator("name", mode="before")
    @classmethod
    def _normalize_name(cls, value: object) -> object:
        return normalize_optional_string(value)


class AgentHeartbeatRequest(AgentInfoBase):
    pass


class AgentPollRequest(AgentHeartbeatRequest):
    limit: int = Field(default=5, ge=1, le=20)


class AgentRegistrationResponse(BaseModel):
    success: bool
    message: str
    server_id: int
    status: str
    heartbeat_interval_seconds: int = 15
    poll_interval_seconds: int = 3

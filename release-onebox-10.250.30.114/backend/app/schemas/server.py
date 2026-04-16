from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import (
    normalize_optional_string,
    normalize_optional_string_list,
    normalize_required_string,
    normalize_string_list,
)


class ServerBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Server name")
    agent_id: str = Field(..., min_length=1, max_length=100, description="Bound host agent ID")
    host: Optional[str] = Field(default=None, max_length=255, description="Host/IP or remark")
    description: Optional[str] = Field(default=None, max_length=500, description="Remark")
    tags: List[str] = Field(default_factory=list, description="Tags")

    @field_validator("name", "agent_id", mode="before")
    @classmethod
    def _normalize_required_strings(cls, value: object) -> object:
        return normalize_required_string(value)

    @field_validator("host", "description", mode="before")
    @classmethod
    def _normalize_optional_strings(cls, value: object) -> object:
        return normalize_optional_string(value)

    @field_validator("tags", mode="before")
    @classmethod
    def _normalize_tags(cls, value: object) -> object:
        return normalize_string_list(value)


class ServerCreate(ServerBase):
    pass


class ServerUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    agent_id: Optional[str] = Field(default=None, min_length=1, max_length=100)
    host: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = Field(default=None, max_length=500)
    tags: Optional[List[str]] = None

    @field_validator("name", "agent_id", mode="before")
    @classmethod
    def _normalize_optional_required_strings(cls, value: object) -> object:
        if value is None:
            return None
        return normalize_required_string(value)

    @field_validator("host", "description", mode="before")
    @classmethod
    def _normalize_optional_strings(cls, value: object) -> object:
        return normalize_optional_string(value)

    @field_validator("tags", mode="before")
    @classmethod
    def _normalize_optional_tags(cls, value: object) -> object:
        return normalize_optional_string_list(value)


class Server(ServerBase):
    id: int
    status: str = Field(default="offline", description="Agent connection status")
    created_at: datetime
    last_seen_at: Optional[datetime] = None
    agent_version: Optional[str] = None
    capabilities: List[str] = Field(default_factory=list)
    management_ip: Optional[str] = Field(default=None, description="Management IP reported by agent")
    host_ip: Optional[str] = Field(default=None, description="Host/internal IP reported by agent")
    reported_user: Optional[str] = Field(default=None, description="Current user reported by agent")
    os_name: Optional[str] = Field(default=None, description="Operating system description")
    runtime: Optional[str] = Field(default=None, description="Container runtime description")
    cpu_percent: Optional[float] = Field(default=None, ge=0, le=100, description="Current CPU usage percentage")
    memory_percent: Optional[float] = Field(default=None, ge=0, le=100, description="Current memory usage percentage")
    memory_total_bytes: Optional[int] = Field(default=None, ge=0, description="Total memory in bytes")
    memory_used_bytes: Optional[int] = Field(default=None, ge=0, description="Used memory in bytes")


class ConnectionTestResponse(BaseModel):
    success: bool
    message: str
    checked_at: datetime
    latency_ms: Optional[float] = None

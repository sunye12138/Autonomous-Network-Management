from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Task(BaseModel):
    id: int
    server_id: int
    server_name: str
    agent_id: str
    task_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None


class TaskResultRequest(BaseModel):
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None


class TaskClaimResponse(BaseModel):
    tasks: List[Task] = Field(default_factory=list)

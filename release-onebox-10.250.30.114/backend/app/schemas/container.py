from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ContainerSummary(BaseModel):
    id: str = Field(..., description="Container ID")
    name: str = Field(..., description="Container name")
    image: str = Field(..., description="Image name")
    status: str = Field(..., description="Container status")
    state: Optional[str] = Field(default=None, description="Running state")
    ports: Optional[str] = Field(default=None, description="Published ports")
    running_for: Optional[str] = Field(default=None, description="Running time")


class ImageSummary(BaseModel):
    id: str = Field(..., description="Image ID")
    repository: str = Field(..., description="Image repository")
    tag: str = Field(..., description="Image tag")
    reference: str = Field(..., description="Preferred image reference")
    digest: Optional[str] = Field(default=None, description="Image digest")
    created_since: Optional[str] = Field(default=None, description="Relative created time")
    created_at: Optional[str] = Field(default=None, description="Absolute created time")
    size: Optional[str] = Field(default=None, description="Image size")


class ContainerActionResponse(BaseModel):
    success: bool
    message: str
    container_name: str


class ContainerLogsResponse(BaseModel):
    container_name: str
    logs: str

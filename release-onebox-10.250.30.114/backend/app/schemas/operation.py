from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import normalize_optional_string, normalize_required_string
from app.schemas.task import Task


class ImageExportRequest(BaseModel):
    image_ref: str = Field(..., min_length=1, max_length=255, description="Docker image reference")
    artifact_name: Optional[str] = Field(default=None, max_length=255, description="Optional exported file name")

    @field_validator("image_ref", mode="before")
    @classmethod
    def _normalize_image_ref(cls, value: object) -> object:
        return normalize_required_string(value)

    @field_validator("artifact_name", mode="before")
    @classmethod
    def _normalize_artifact_name(cls, value: object) -> object:
        return normalize_optional_string(value)


class ImageImportRequest(BaseModel):
    artifact_id: int = Field(..., ge=1, description="Artifact ID")


class ComposeDeployRequest(BaseModel):
    artifact_id: int = Field(..., ge=1, description="Artifact ID")
    project_name: Optional[str] = Field(default=None, max_length=100, description="docker compose project name")
    compose_file: str = Field(default="docker-compose.yml", min_length=1, max_length=255)
    workdir: Optional[str] = Field(default=None, max_length=255, description="Sub directory inside extracted bundle")

    @field_validator("project_name", "workdir", mode="before")
    @classmethod
    def _normalize_optional_strings(cls, value: object) -> object:
        return normalize_optional_string(value)

    @field_validator("compose_file", mode="before")
    @classmethod
    def _normalize_compose_file(cls, value: object) -> object:
        return normalize_required_string(value)


class OperationResponse(BaseModel):
    success: bool
    message: str
    task: Task

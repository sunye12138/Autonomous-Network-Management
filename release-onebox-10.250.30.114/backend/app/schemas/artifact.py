from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Artifact(BaseModel):
    id: int
    file_name: str = Field(..., description="Original file name")
    kind: str = Field(default="generic", description="Artifact kind")
    content_type: Optional[str] = Field(default=None, description="HTTP content type")
    size_bytes: int = Field(..., ge=0, description="Artifact size in bytes")
    sha256: str = Field(..., description="Artifact SHA256")
    source: str = Field(default="web-upload", description="Upload source")
    created_at: datetime
    download_url: str = Field(..., description="Artifact download API path")

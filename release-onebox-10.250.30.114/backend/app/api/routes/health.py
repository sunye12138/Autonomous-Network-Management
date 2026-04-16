from __future__ import annotations

from typing import Dict

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health_check() -> Dict[str, str]:
    return {
        "status": "ok",
        "message": "API Server is running",
        "architecture": "web-portal -> api-server -> host-agent",
    }

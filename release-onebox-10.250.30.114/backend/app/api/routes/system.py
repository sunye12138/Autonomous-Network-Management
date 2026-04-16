from __future__ import annotations

from fastapi import APIRouter

from app.schemas.system import SystemOverview
from app.services.system_service import system_service

router = APIRouter()


@router.get("/overview", response_model=SystemOverview)
def get_system_overview() -> SystemOverview:
    return system_service.get_overview()

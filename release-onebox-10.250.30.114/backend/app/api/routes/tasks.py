from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.task import Task
from app.services.task_service import task_service

router = APIRouter()


@router.get("", response_model=List[Task])
def list_tasks(server_id: Optional[int] = Query(default=None), limit: int = Query(default=20, ge=1, le=200)) -> List[Task]:
    return task_service.list_tasks(server_id=server_id, limit=limit)


@router.get("/{task_id}", response_model=Task)
def get_task(task_id: int) -> Task:
    task = task_service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task

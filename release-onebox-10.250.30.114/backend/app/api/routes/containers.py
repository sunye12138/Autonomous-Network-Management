from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.container import ContainerActionResponse, ContainerLogsResponse, ContainerSummary, ImageSummary
from app.services.docker_service import DockerServiceError, docker_service
from app.services.server_service import server_service

router = APIRouter()


def _get_server_or_404(server_id: int) -> Dict[str, Any]:
    server = server_service.get_server_record(server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")
    return server


@router.get("/servers/{server_id}/containers", response_model=List[ContainerSummary])
def list_containers(server_id: int) -> List[ContainerSummary]:
    server = _get_server_or_404(server_id)
    try:
        return docker_service.list_containers(server)
    except DockerServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/servers/{server_id}/images", response_model=List[ImageSummary])
def list_images(server_id: int) -> List[ImageSummary]:
    server = _get_server_or_404(server_id)
    try:
        return docker_service.list_images(server)
    except DockerServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/servers/{server_id}/containers/{container_name}/start", response_model=ContainerActionResponse)
def start_container(server_id: int, container_name: str) -> ContainerActionResponse:
    server = _get_server_or_404(server_id)
    try:
        return docker_service.start_container(server, container_name)
    except DockerServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/servers/{server_id}/containers/{container_name}/stop", response_model=ContainerActionResponse)
def stop_container(server_id: int, container_name: str) -> ContainerActionResponse:
    server = _get_server_or_404(server_id)
    try:
        return docker_service.stop_container(server, container_name)
    except DockerServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/servers/{server_id}/containers/{container_name}/restart", response_model=ContainerActionResponse)
def restart_container(server_id: int, container_name: str) -> ContainerActionResponse:
    server = _get_server_or_404(server_id)
    try:
        return docker_service.restart_container(server, container_name)
    except DockerServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/servers/{server_id}/containers/{container_name}/logs", response_model=ContainerLogsResponse)
def get_container_logs(server_id: int, container_name: str, tail: int = Query(default=200, ge=1, le=1000)) -> ContainerLogsResponse:
    server = _get_server_or_404(server_id)
    try:
        return docker_service.get_logs(server, container_name, tail=tail)
    except DockerServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

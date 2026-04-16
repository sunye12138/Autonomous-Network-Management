from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status

from app.schemas.operation import ComposeDeployRequest, ImageExportRequest, ImageImportRequest, OperationResponse
from app.services.operation_service import OperationServiceError, operation_service
from app.services.server_service import server_service

router = APIRouter()


def _get_server_or_404(server_id: int) -> Dict[str, Any]:
    server = server_service.get_server_record(server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")
    return server


@router.post("/servers/{server_id}/images/export", response_model=OperationResponse)
def export_image(server_id: int, payload: ImageExportRequest) -> OperationResponse:
    server = _get_server_or_404(server_id)
    try:
        return operation_service.export_image(server, payload)
    except OperationServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/servers/{server_id}/images/import", response_model=OperationResponse)
def import_image(server_id: int, payload: ImageImportRequest) -> OperationResponse:
    server = _get_server_or_404(server_id)
    try:
        return operation_service.import_image(server, payload)
    except OperationServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/servers/{server_id}/deployments/compose", response_model=OperationResponse)
def deploy_compose_bundle(server_id: int, payload: ComposeDeployRequest) -> OperationResponse:
    server = _get_server_or_404(server_id)
    try:
        return operation_service.deploy_compose_bundle(server, payload)
    except OperationServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

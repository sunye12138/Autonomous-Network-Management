from __future__ import annotations

from typing import List, Optional
from urllib.parse import unquote

from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from fastapi.responses import FileResponse

from app.schemas.artifact import Artifact
from app.services.artifact_service import ArtifactServiceError, artifact_service

router = APIRouter()


@router.get("", response_model=List[Artifact])
def list_artifacts(kind: Optional[str] = Query(default=None)) -> List[Artifact]:
    return artifact_service.list_artifacts(kind=kind)


@router.get("/{artifact_id}", response_model=Artifact)
def get_artifact(artifact_id: int) -> Artifact:
    artifact = artifact_service.get_artifact(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    return artifact


@router.post("/upload", response_model=Artifact, status_code=status.HTTP_201_CREATED)
async def upload_artifact(
    request: Request,
    x_artifact_name: str = Header(...),
    x_artifact_kind: Optional[str] = Header(default=None),
    x_artifact_source: Optional[str] = Header(default=None),
    content_type: Optional[str] = Header(default=None, alias="Content-Type"),
) -> Artifact:
    try:
        return artifact_service.store_bytes(
            await request.body(),
            file_name=unquote(x_artifact_name),
            kind=unquote(x_artifact_kind) if x_artifact_kind else None,
            content_type=content_type,
            source=unquote(x_artifact_source) if x_artifact_source else None,
        )
    except ArtifactServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{artifact_id}/download")
def download_artifact(artifact_id: int) -> FileResponse:
    artifact = artifact_service.get_artifact(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    try:
        path = artifact_service.get_artifact_path(artifact_id)
    except ArtifactServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return FileResponse(
        path,
        media_type=artifact.content_type or "application/octet-stream",
        filename=artifact.file_name,
    )

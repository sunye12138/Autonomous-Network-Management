from __future__ import annotations

from typing import List, Optional
from urllib.parse import unquote

from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from fastapi.responses import FileResponse

from app.core.config import settings
from app.schemas.artifact import Artifact
from app.services.artifact_service import ArtifactServiceError, ArtifactTooLargeError, artifact_service

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
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > settings.artifact_upload_max_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"上传内容过大，最大允许 {settings.artifact_upload_max_bytes} 字节",
                )
        except ValueError:
            pass

    artifact_id, normalized_name, stored_name, timestamp, session = artifact_service.begin_upload(
        file_name=unquote(x_artifact_name),
    )
    try:
        async for chunk in request.stream():
            session.append(chunk)
        return artifact_service.finish_upload(
            artifact_id=artifact_id,
            normalized_name=normalized_name,
            stored_name=stored_name,
            timestamp=timestamp,
            session=session,
            kind=unquote(x_artifact_kind) if x_artifact_kind else None,
            content_type=content_type,
            source=unquote(x_artifact_source) if x_artifact_source else None,
        )
    except ArtifactTooLargeError as exc:
        session.close(remove_file=True)
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)) from exc
    except ArtifactServiceError as exc:
        session.close(remove_file=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception:
        session.close(remove_file=True)
        raise


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

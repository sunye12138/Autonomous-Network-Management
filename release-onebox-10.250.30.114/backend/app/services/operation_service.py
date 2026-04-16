from __future__ import annotations

from typing import Any, Dict

from app.core.config import settings
from app.schemas.operation import ComposeDeployRequest, ImageExportRequest, ImageImportRequest, OperationResponse
from app.schemas.task import Task
from app.services.artifact_service import artifact_service
from app.services.task_service import TaskServiceError, task_service


class OperationServiceError(Exception):
    pass


class OperationService:
    def _dispatch(self, server: Dict[str, Any], *, task_type: str, payload: Dict[str, Any], timeout: float) -> Task:
        try:
            return task_service.dispatch_and_wait(server, task_type=task_type, payload=payload, timeout=timeout)
        except TaskServiceError as exc:
            raise OperationServiceError(str(exc)) from exc

    @staticmethod
    def _build_response(task: Task, default_message: str) -> OperationResponse:
        result = task.result if isinstance(task.result, dict) else {}
        message = result.get("message") if isinstance(result, dict) else None
        return OperationResponse(success=task.status == "success", message=message or default_message, task=task)

    def export_image(self, server: Dict[str, Any], payload: ImageExportRequest) -> OperationResponse:
        task = self._dispatch(
            server,
            task_type="artifact.export_image",
            payload={
                "image_ref": payload.image_ref,
                "artifact_name": payload.artifact_name,
            },
            timeout=settings.artifact_task_timeout_seconds,
        )
        return self._build_response(task, f"镜像 {payload.image_ref} 导出完成")

    def import_image(self, server: Dict[str, Any], payload: ImageImportRequest) -> OperationResponse:
        artifact = artifact_service.get_artifact(payload.artifact_id)
        if artifact is None:
            raise OperationServiceError("制品不存在")
        if artifact.kind not in {"docker-image", "generic"}:
            raise OperationServiceError("该制品不是可导入的镜像包")

        task = self._dispatch(
            server,
            task_type="artifact.import_image",
            payload={
                "artifact_id": payload.artifact_id,
            },
            timeout=settings.artifact_task_timeout_seconds,
        )
        return self._build_response(task, f"镜像包 {artifact.file_name} 导入完成")

    def deploy_compose_bundle(self, server: Dict[str, Any], payload: ComposeDeployRequest) -> OperationResponse:
        artifact = artifact_service.get_artifact(payload.artifact_id)
        if artifact is None:
            raise OperationServiceError("制品不存在")
        if artifact.kind not in {"compose-bundle", "generic"}:
            raise OperationServiceError("该制品不是可部署的 Compose 包")

        task = self._dispatch(
            server,
            task_type="deploy.compose_bundle",
            payload={
                "artifact_id": payload.artifact_id,
                "project_name": payload.project_name,
                "compose_file": payload.compose_file,
                "workdir": payload.workdir,
            },
            timeout=settings.artifact_task_timeout_seconds,
        )
        project_name = payload.project_name or artifact.file_name
        return self._build_response(task, f"Compose 项目 {project_name} 部署完成")


operation_service = OperationService()

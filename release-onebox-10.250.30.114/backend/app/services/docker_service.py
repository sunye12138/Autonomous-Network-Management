from __future__ import annotations

from typing import Any, Dict, List

from app.core.config import settings
from app.schemas.container import ContainerActionResponse, ContainerLogsResponse, ContainerSummary, ImageSummary
from app.services.task_service import TaskServiceError, task_service


class DockerServiceError(Exception):
    pass


class DockerService:
    def _dispatch(self, server: Dict[str, Any], task_type: str, payload: Dict[str, Any], timeout: float | None = None) -> Dict[str, Any]:
        try:
            task = task_service.dispatch_and_wait(
                server,
                task_type=task_type,
                payload=payload,
                timeout=timeout if timeout is not None else settings.docker_task_timeout_seconds,
            )
        except TaskServiceError as exc:
            raise DockerServiceError(str(exc)) from exc

        result = task.result or {}
        if not isinstance(result, dict):
            raise DockerServiceError("Host Agent returned an invalid result")
        return result

    def list_containers(self, server: Dict[str, Any]) -> List[ContainerSummary]:
        result = self._dispatch(server, "docker.list_containers", {})
        containers = result.get("containers", [])
        if not isinstance(containers, list):
            raise DockerServiceError("Invalid container list format")
        return [ContainerSummary.model_validate(item) for item in containers]

    def list_images(self, server: Dict[str, Any]) -> List[ImageSummary]:
        result = self._dispatch(server, "docker.list_images", {})
        images = result.get("images", [])
        if not isinstance(images, list):
            raise DockerServiceError("Invalid image list format")
        return [ImageSummary.model_validate(item) for item in images]

    def start_container(self, server: Dict[str, Any], container_name: str) -> ContainerActionResponse:
        result = self._dispatch(server, "docker.container_action", {"action": "start", "container_name": container_name})
        return ContainerActionResponse.model_validate(result)

    def stop_container(self, server: Dict[str, Any], container_name: str) -> ContainerActionResponse:
        result = self._dispatch(server, "docker.container_action", {"action": "stop", "container_name": container_name})
        return ContainerActionResponse.model_validate(result)

    def restart_container(self, server: Dict[str, Any], container_name: str) -> ContainerActionResponse:
        result = self._dispatch(server, "docker.container_action", {"action": "restart", "container_name": container_name})
        return ContainerActionResponse.model_validate(result)

    def get_logs(self, server: Dict[str, Any], container_name: str, tail: int = 200) -> ContainerLogsResponse:
        result = self._dispatch(server, "docker.container_logs", {"container_name": container_name, "tail": tail})
        return ContainerLogsResponse.model_validate(result)



docker_service = DockerService()

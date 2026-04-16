from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.core.config import settings
from app.schemas.agent import AgentHeartbeatRequest, AgentPollRequest, AgentRegistrationRequest, AgentRegistrationResponse
from app.schemas.task import Task, TaskClaimResponse, TaskResultRequest
from app.services.server_service import server_service
from app.services.task_service import TaskServiceError, task_service

router = APIRouter()


def _build_response(message: str, server_id: int, status_text: str) -> AgentRegistrationResponse:
    return AgentRegistrationResponse(
        success=True,
        message=message,
        server_id=server_id,
        status=status_text,
        heartbeat_interval_seconds=settings.agent_heartbeat_interval_seconds,
        poll_interval_seconds=settings.agent_poll_interval_seconds,
    )


@router.post("/register", response_model=AgentRegistrationResponse)
def register_agent(payload: AgentRegistrationRequest) -> AgentRegistrationResponse:
    server = server_service.register_agent(payload)
    return _build_response(f"Agent {payload.agent_id} registered", server.id, server.status)


@router.post("/{agent_id}/heartbeat", response_model=AgentRegistrationResponse)
def heartbeat_agent(agent_id: str, payload: AgentHeartbeatRequest) -> AgentRegistrationResponse:
    server = server_service.heartbeat_agent(agent_id, payload)
    return _build_response(f"Heartbeat received from {agent_id}", server.id, server.status)


@router.post("/{agent_id}/tasks/claim", response_model=TaskClaimResponse)
def claim_tasks(agent_id: str, payload: AgentPollRequest) -> TaskClaimResponse:
    server_service.heartbeat_agent(
        agent_id,
        AgentHeartbeatRequest(
            host=payload.host,
            management_ip=payload.management_ip,
            host_ip=payload.host_ip,
            reported_user=payload.reported_user,
            os_name=payload.os_name,
            runtime=payload.runtime,
            version=payload.version,
            capabilities=payload.capabilities,
            cpu_percent=payload.cpu_percent,
            memory_percent=payload.memory_percent,
            memory_total_bytes=payload.memory_total_bytes,
            memory_used_bytes=payload.memory_used_bytes,
        ),
    )
    tasks = task_service.claim_tasks(agent_id, limit=payload.limit)
    return TaskClaimResponse(tasks=tasks)


@router.post("/{agent_id}/tasks/{task_id}/complete", response_model=Task)
def complete_task(agent_id: str, task_id: int, payload: TaskResultRequest) -> Task:
    try:
        return task_service.complete_task(
            agent_id=agent_id,
            task_id=task_id,
            success=payload.success,
            result=payload.result,
            error=payload.error,
        )
    except TaskServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

from fastapi import APIRouter

from app.api.routes import agents, artifacts, containers, health, operations, servers, system, tasks

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(system.router, prefix="/system", tags=["system"])
api_router.include_router(servers.router, prefix="/servers", tags=["servers"])
api_router.include_router(containers.router, tags=["containers"])
api_router.include_router(operations.router, tags=["operations"])
api_router.include_router(artifacts.router, prefix="/artifacts", tags=["artifacts"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])

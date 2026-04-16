from __future__ import annotations

from typing import Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    description="Web Portal / API Server / Host Agent 架构的控制后端。",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)


@app.on_event("startup")
def on_startup() -> None:
    settings.ensure_directories()


@app.get("/", tags=["root"])
def root() -> Dict[str, str]:
    return {
        "message": "Host Agent Control API is running",
        "architecture": "web-portal -> api-server -> host-agent",
        "docs": "/docs",
    }

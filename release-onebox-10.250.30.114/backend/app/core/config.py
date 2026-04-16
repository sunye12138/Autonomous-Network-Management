from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
from typing import List, Optional

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _parse_cors_origins(raw_value: Optional[str]) -> List[str]:
    if not raw_value:
        return ["*"]
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _parse_path(raw_value: Optional[str], fallback: Path) -> Path:
    return Path(raw_value).expanduser() if raw_value else fallback


def _default_data_dir() -> Path:
    return _parse_path(os.getenv("DATA_DIR"), BACKEND_DIR / "data")


def _default_artifact_dir() -> Path:
    return _parse_path(os.getenv("ARTIFACT_DIR"), _default_data_dir() / "artifacts")


def _default_server_state_file() -> Path:
    return _parse_path(os.getenv("SERVER_STATE_FILE"), _default_data_dir() / "servers.json")


def _default_task_state_file() -> Path:
    return _parse_path(os.getenv("TASK_STATE_FILE"), _default_data_dir() / "tasks.json")


def _default_artifact_state_file() -> Path:
    return _parse_path(os.getenv("ARTIFACT_STATE_FILE"), _default_data_dir() / "artifacts.json")


@dataclass
class Settings:
    app_name: str = os.getenv("APP_NAME", "Host Agent Control API")
    app_version: str = os.getenv("APP_VERSION", "0.2.0")
    api_prefix: str = os.getenv("API_PREFIX", "/api")
    debug: bool = os.getenv("DEBUG", "true").lower() == "true"
    cors_origins: List[str] = field(default_factory=lambda: _parse_cors_origins(os.getenv("CORS_ORIGINS", "*")))
    data_dir: Path = field(default_factory=_default_data_dir)
    artifact_dir: Path = field(default_factory=_default_artifact_dir)
    server_state_file: Path = field(default_factory=_default_server_state_file)
    task_state_file: Path = field(default_factory=_default_task_state_file)
    artifact_state_file: Path = field(default_factory=_default_artifact_state_file)
    heartbeat_timeout_seconds: int = int(os.getenv("HEARTBEAT_TIMEOUT_SECONDS", "45"))
    task_wait_timeout_seconds: float = float(os.getenv("TASK_WAIT_TIMEOUT_SECONDS", "25"))
    docker_task_timeout_seconds: float = float(os.getenv("DOCKER_TASK_TIMEOUT_SECONDS", "120"))
    artifact_task_timeout_seconds: float = float(os.getenv("ARTIFACT_TASK_TIMEOUT_SECONDS", "300"))
    agent_heartbeat_interval_seconds: int = int(os.getenv("AGENT_HEARTBEAT_INTERVAL_SECONDS", "15"))
    agent_poll_interval_seconds: int = int(os.getenv("AGENT_POLL_INTERVAL_SECONDS", "3"))

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.server_state_file.parent.mkdir(parents=True, exist_ok=True)
        self.task_state_file.parent.mkdir(parents=True, exist_ok=True)
        self.artifact_state_file.parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()

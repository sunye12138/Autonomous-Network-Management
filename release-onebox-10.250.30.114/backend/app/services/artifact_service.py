from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
from threading import Lock
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.json_store import load_json, save_json
from app.schemas.artifact import Artifact


class ArtifactServiceError(Exception):
    pass


class ArtifactService:
    _unsafe_filename_pattern = re.compile(r'[<>:"/\\|?*\x00-\x1F]+')

    def __init__(self) -> None:
        self._records: List[Dict[str, Any]] = []
        self._next_id = 1
        self._lock = Lock()
        self._load_state()

    @staticmethod
    def _serialize_datetime(value: datetime) -> str:
        return value.isoformat()

    @staticmethod
    def _deserialize_datetime(value: Optional[str]) -> datetime:
        if not value:
            return datetime.now(timezone.utc)
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)

    def _sanitize_filename(self, file_name: str) -> str:
        normalized = Path(file_name).name.strip() or "artifact.bin"
        sanitized = self._unsafe_filename_pattern.sub("_", normalized)
        return sanitized or "artifact.bin"

    def _serialize_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        return {
            **record,
            "created_at": self._serialize_datetime(record["created_at"]),
        }

    def _deserialize_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        restored = dict(record)
        restored["created_at"] = self._deserialize_datetime(record.get("created_at"))
        restored.setdefault("content_type", None)
        restored.setdefault("kind", "generic")
        restored.setdefault("source", "web-upload")
        restored.setdefault("sha256", "")
        restored.setdefault("size_bytes", 0)
        return restored

    def _load_state(self) -> None:
        raw_records = load_json(settings.artifact_state_file, [])
        self._records = [self._deserialize_record(item) for item in raw_records if isinstance(item, dict)]
        if self._records:
            self._next_id = max(record["id"] for record in self._records) + 1

    def _persist_locked(self) -> None:
        save_json(settings.artifact_state_file, [self._serialize_record(record) for record in self._records])

    def _to_public(self, record: Dict[str, Any]) -> Artifact:
        return Artifact(
            id=record["id"],
            file_name=record["file_name"],
            kind=record.get("kind", "generic"),
            content_type=record.get("content_type"),
            size_bytes=record.get("size_bytes", 0),
            sha256=record.get("sha256", ""),
            source=record.get("source", "web-upload"),
            created_at=record["created_at"],
            download_url=f"{settings.api_prefix}/artifacts/{record['id']}/download",
        )

    def _get_record(self, artifact_id: int) -> Optional[Dict[str, Any]]:
        return next((record for record in self._records if record["id"] == artifact_id), None)

    def list_artifacts(self, kind: Optional[str] = None) -> List[Artifact]:
        with self._lock:
            records = sorted(self._records, key=lambda item: item["created_at"], reverse=True)
            if kind:
                records = [record for record in records if record.get("kind") == kind]
            return [self._to_public(record) for record in records]

    def get_artifact(self, artifact_id: int) -> Optional[Artifact]:
        with self._lock:
            record = self._get_record(artifact_id)
            if record is None:
                return None
            return self._to_public(record)

    def get_artifact_record(self, artifact_id: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            record = self._get_record(artifact_id)
            return dict(record) if record is not None else None

    def get_artifact_path(self, artifact_id: int) -> Path:
        with self._lock:
            record = self._get_record(artifact_id)
            if record is None:
                raise ArtifactServiceError("制品不存在")
            path = settings.artifact_dir / record["stored_name"]
            if not path.exists():
                raise ArtifactServiceError("制品文件不存在")
            return path

    def store_bytes(
        self,
        data: bytes,
        *,
        file_name: str,
        kind: Optional[str] = None,
        content_type: Optional[str] = None,
        source: Optional[str] = None,
    ) -> Artifact:
        if not data:
            raise ArtifactServiceError("上传内容不能为空")

        with self._lock:
            artifact_id = self._next_id
            normalized_name = self._sanitize_filename(file_name)
            timestamp = datetime.now(timezone.utc)
            stored_name = f"{artifact_id}_{timestamp.strftime('%Y%m%d%H%M%S')}_{normalized_name}"
            path = settings.artifact_dir / stored_name
            path.write_bytes(data)

            record = {
                "id": artifact_id,
                "file_name": normalized_name,
                "stored_name": stored_name,
                "kind": (kind or "generic").strip() or "generic",
                "content_type": content_type or "application/octet-stream",
                "size_bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "source": source or "web-upload",
                "created_at": timestamp,
            }
            self._records.append(record)
            self._next_id += 1
            self._persist_locked()
            return self._to_public(record)

    def get_stats(self) -> Dict[str, int]:
        with self._lock:
            return {
                "total_artifacts": len(self._records),
            }


artifact_service = ArtifactService()

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


class ArtifactTooLargeError(ArtifactServiceError):
    pass


class ArtifactUploadSession:
    def __init__(self, *, path: Path, max_bytes: int) -> None:
        self.path = path
        self.max_bytes = max_bytes
        self.size_bytes = 0
        self._sha256 = hashlib.sha256()
        self._file = path.open("wb")
        self._closed = False

    def append(self, chunk: bytes) -> None:
        if self._closed or not chunk:
            return
        next_size = self.size_bytes + len(chunk)
        if next_size > self.max_bytes:
            self.close(remove_file=True)
            raise ArtifactTooLargeError(f"上传内容过大，最大允许 {self.max_bytes} 字节")
        self._file.write(chunk)
        self._sha256.update(chunk)
        self.size_bytes = next_size

    def close(self, *, remove_file: bool = False) -> None:
        if not self._closed:
            self._file.close()
            self._closed = True
        if remove_file:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass

    @property
    def sha256(self) -> str:
        return self._sha256.hexdigest()


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

    def _reserve_artifact_locked(self, file_name: str) -> tuple[int, str, str, datetime, Path]:
        artifact_id = self._next_id
        normalized_name = self._sanitize_filename(file_name)
        timestamp = datetime.now(timezone.utc)
        stored_name = f"{artifact_id}_{timestamp.strftime('%Y%m%d%H%M%S')}_{normalized_name}"
        path = settings.artifact_dir / stored_name
        self._next_id += 1
        return artifact_id, normalized_name, stored_name, timestamp, path

    def begin_upload(self, *, file_name: str) -> tuple[int, str, str, datetime, ArtifactUploadSession]:
        with self._lock:
            artifact_id, normalized_name, stored_name, timestamp, path = self._reserve_artifact_locked(file_name)
        return artifact_id, normalized_name, stored_name, timestamp, ArtifactUploadSession(
            path=path,
            max_bytes=settings.artifact_upload_max_bytes,
        )

    def finish_upload(
        self,
        *,
        artifact_id: int,
        normalized_name: str,
        stored_name: str,
        timestamp: datetime,
        session: ArtifactUploadSession,
        kind: Optional[str] = None,
        content_type: Optional[str] = None,
        source: Optional[str] = None,
    ) -> Artifact:
        session.close()
        if session.size_bytes <= 0:
            session.close(remove_file=True)
            raise ArtifactServiceError("上传内容不能为空")

        record = {
            "id": artifact_id,
            "file_name": normalized_name,
            "stored_name": stored_name,
            "kind": (kind or "generic").strip() or "generic",
            "content_type": content_type or "application/octet-stream",
            "size_bytes": session.size_bytes,
            "sha256": session.sha256,
            "source": source or "web-upload",
            "created_at": timestamp,
        }
        with self._lock:
            self._records.append(record)
            self._persist_locked()
            return self._to_public(record)

    def store_bytes(
        self,
        data: bytes,
        *,
        file_name: str,
        kind: Optional[str] = None,
        content_type: Optional[str] = None,
        source: Optional[str] = None,
    ) -> Artifact:
        artifact_id, normalized_name, stored_name, timestamp, session = self.begin_upload(file_name=file_name)
        try:
            session.append(data)
            return self.finish_upload(
                artifact_id=artifact_id,
                normalized_name=normalized_name,
                stored_name=stored_name,
                timestamp=timestamp,
                session=session,
                kind=kind,
                content_type=content_type,
                source=source,
            )
        except Exception:
            session.close(remove_file=True)
            raise

    def get_stats(self) -> Dict[str, int]:
        with self._lock:
            return {
                "total_artifacts": len(self._records),
            }


artifact_service = ArtifactService()

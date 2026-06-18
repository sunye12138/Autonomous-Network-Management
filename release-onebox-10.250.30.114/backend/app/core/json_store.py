from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import logging
import json
import os
from pathlib import Path
import tempfile
from typing import Any


logger = logging.getLogger(__name__)


def _broken_backup_path(path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    return path.with_name(f"{path.stem}.broken-{stamp}{path.suffix}")


def _backup_broken_json(path: Path, raw_bytes: bytes) -> None:
    try:
        backup_path = _broken_backup_path(path)
        backup_path.write_bytes(raw_bytes)
        logger.warning("Backed up broken JSON file %s to %s", path, backup_path)
    except OSError as exc:
        logger.warning("Failed to back up broken JSON file %s: %s", path, exc)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return deepcopy(default)
    try:
        raw_bytes = path.read_bytes()
    except OSError:
        return deepcopy(default)
    try:
        return json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        _backup_broken_json(path, raw_bytes)
        return deepcopy(default)


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)

    temp_fd, temp_path = tempfile.mkstemp(
        prefix=f".{path.stem}.",
        suffix=f"{path.suffix}.tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as temp_file:
            temp_file.write(serialized)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        try:
            os.replace(temp_path, path)
        except PermissionError:
            path.write_text(serialized, encoding="utf-8")
            try:
                os.unlink(temp_path)
            except OSError:
                pass
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise

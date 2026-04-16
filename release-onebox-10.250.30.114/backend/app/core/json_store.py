from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
from typing import Any


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return deepcopy(default)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
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

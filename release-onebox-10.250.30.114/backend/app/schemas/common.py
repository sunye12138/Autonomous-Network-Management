from __future__ import annotations

from typing import Iterable, Optional


def normalize_required_string(value: object) -> object:
    if isinstance(value, str):
        return value.strip()
    return value


def normalize_optional_string(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    return value


def normalize_string_list(values: object) -> object:
    if values is None:
        return []
    if not isinstance(values, Iterable) or isinstance(values, (str, bytes)):
        return values

    normalized_values: list[str] = []
    seen: set[str] = set()
    for item in values:
        if item is None:
            continue
        normalized = str(item).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        normalized_values.append(normalized)
    return normalized_values


def normalize_optional_string_list(values: object) -> object:
    if values is None:
        return None
    return normalize_string_list(values)

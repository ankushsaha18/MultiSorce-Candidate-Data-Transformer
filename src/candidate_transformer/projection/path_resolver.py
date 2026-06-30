"""Canonical/projection path resolution helpers."""

from __future__ import annotations

from typing import Any
import re

_TOKEN_RE = re.compile(r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?P<index>\[(?:\d+)?\])?")


class PathResolutionError(KeyError):
    """Raised when a projection path cannot be resolved."""


def resolve_path(data: Any, path: str) -> Any:
    """Resolve a small JSONPath-like path.

    Supported examples:

    - ``full_name``
    - ``emails[0]``
    - ``skills[].name``
    - ``location.country``
    """
    tokens = _parse_path(path)
    return _resolve_tokens(data, tokens)


def set_path(data: dict[str, Any], path: str, value: Any) -> None:
    """Set a possibly dotted destination path in a dict."""
    parts = path.split(".")
    cursor = data
    for part in parts[:-1]:
        if not part:
            raise PathResolutionError(f"invalid destination path: {path}")
        child = cursor.setdefault(part, {})
        if not isinstance(child, dict):
            raise PathResolutionError(f"destination path collides with non-object: {path}")
        cursor = child
    cursor[parts[-1]] = value


def path_exists(data: Any, path: str) -> bool:
    """Return whether a path can be resolved."""
    try:
        resolve_path(data, path)
    except (PathResolutionError, IndexError, TypeError):
        return False
    return True


def provenance_field_pattern(path: str) -> re.Pattern[str]:
    """Build a provenance field matcher for exact and ``[]`` paths."""
    escaped = re.escape(path).replace(r"\[\]", r"\[\d+\]")
    return re.compile(f"^{escaped}$")


def _parse_path(path: str) -> list[tuple[str, int | None | str]]:
    tokens: list[tuple[str, int | None | str]] = []
    for part in path.split("."):
        match = _TOKEN_RE.fullmatch(part)
        if not match:
            raise PathResolutionError(f"unsupported path syntax: {path}")
        raw_index = match.group("index")
        if raw_index is None:
            index: int | None | str = None
        elif raw_index == "[]":
            index = "all"
        else:
            index = int(raw_index[1:-1])
        tokens.append((match.group("name"), index))
    return tokens


def _resolve_tokens(data: Any, tokens: list[tuple[str, int | None | str]]) -> Any:
    if not tokens:
        return data

    name, index = tokens[0]
    remainder = tokens[1:]

    if isinstance(data, dict):
        if name not in data:
            raise PathResolutionError(f"path component not found: {name}")
        value = data[name]
    else:
        if not hasattr(data, name):
            raise PathResolutionError(f"path component not found: {name}")
        value = getattr(data, name)

    if index == "all":
        if not isinstance(value, list):
            raise PathResolutionError(f"path component is not a list: {name}")
        return [_resolve_tokens(item, remainder) for item in value]

    if isinstance(index, int):
        if not isinstance(value, list):
            raise PathResolutionError(f"path component is not a list: {name}")
        value = value[index]

    return _resolve_tokens(value, remainder)

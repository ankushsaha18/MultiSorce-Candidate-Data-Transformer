"""Projection configuration loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json


class ProjectionConfigError(ValueError):
    """Raised when a projection config is invalid."""


def load_projection_config(path: str | Path) -> dict[str, Any]:
    """Load and validate a JSON projection config."""
    config_path = Path(path)
    if not config_path.exists():
        raise ProjectionConfigError(f"Projection config does not exist: {config_path}")
    if config_path.suffix.lower() != ".json":
        raise ProjectionConfigError("Projection config must be a JSON file")

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProjectionConfigError(f"Invalid projection config JSON: {exc}") from exc
    except OSError as exc:
        raise ProjectionConfigError(f"Could not read projection config: {exc}") from exc

    validate_projection_config(config)
    return config


def validate_projection_config(config: dict[str, Any]) -> None:
    """Validate the small runtime projection config shape."""
    if not isinstance(config, dict):
        raise ProjectionConfigError("Projection config root must be an object")

    fields = config.get("fields")
    if not isinstance(fields, list):
        raise ProjectionConfigError("Projection config must contain a fields array")

    on_missing = config.get("on_missing", "null")
    if on_missing not in {"null", "omit", "error"}:
        raise ProjectionConfigError("on_missing must be one of: null, omit, error")

    seen_paths: set[str] = set()
    for index, field in enumerate(fields):
        if not isinstance(field, dict):
            raise ProjectionConfigError(f"fields[{index}] must be an object")

        path = field.get("path")
        if not isinstance(path, str) or not path.strip():
            raise ProjectionConfigError(f"fields[{index}].path must be a non-empty string")
        if path in seen_paths:
            raise ProjectionConfigError(f"duplicate projected field path: {path}")
        seen_paths.add(path)

        source_path = field.get("from", path)
        if not isinstance(source_path, str) or not source_path.strip():
            raise ProjectionConfigError(f"fields[{index}].from must be a non-empty string")

        expected_type = field.get("type")
        if expected_type is not None and expected_type not in {
            "string",
            "number",
            "boolean",
            "object",
            "array",
            "string[]",
            "number[]",
            "any",
        }:
            raise ProjectionConfigError(f"unsupported projected type: {expected_type}")

        normalize = field.get("normalize")
        if normalize is not None and normalize not in {"E164", "YYYY-MM", "canonical", "ISO-3166-alpha2"}:
            raise ProjectionConfigError(f"unsupported normalization option: {normalize}")

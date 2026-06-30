"""Runtime configuration loading utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json

import yaml


class ConfigError(RuntimeError):
    """Raised when configuration cannot be loaded or parsed."""


def load_config(path: str | Path) -> dict[str, Any]:
    """Load a JSON or YAML configuration file.

    The loader is intentionally small and generic. Validation of domain-specific
    config files will live in the validation layer once business logic is added.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"Configuration file does not exist: {config_path}")

    try:
        raw_text = config_path.read_text(encoding="utf-8")
        if config_path.suffix.lower() == ".json":
            loaded = json.loads(raw_text)
        elif config_path.suffix.lower() in {".yaml", ".yml"}:
            loaded = yaml.safe_load(raw_text)
        else:
            raise ConfigError(
                f"Unsupported configuration format: {config_path.suffix}"
            )
    except ConfigError:
        raise
    except Exception as exc:
        raise ConfigError(f"Failed to load configuration {config_path}: {exc}") from exc

    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ConfigError(f"Configuration root must be an object: {config_path}")
    return loaded

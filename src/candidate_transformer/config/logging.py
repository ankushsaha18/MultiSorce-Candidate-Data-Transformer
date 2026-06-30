"""Logging configuration helpers."""

from __future__ import annotations

from pathlib import Path
from logging.config import dictConfig
import logging

from candidate_transformer.config.loader import ConfigError, load_config


def configure_logging(path: str | Path = "configs/logging.yaml") -> None:
    """Configure application logging from a YAML or JSON logging config."""
    config_path = Path(path)
    config = load_config(config_path)
    _ensure_file_handler_dirs(config, config_path.parent)
    dictConfig(config)
    logging.getLogger(__name__).debug("Logging configured from %s", config_path)


def _ensure_file_handler_dirs(config: dict, base_dir: Path) -> None:
    handlers = config.get("handlers", {})
    if not isinstance(handlers, dict):
        raise ConfigError("Logging configuration 'handlers' must be an object.")

    for handler in handlers.values():
        if not isinstance(handler, dict):
            continue
        filename = handler.get("filename")
        if not filename:
            continue

        log_path = Path(filename)
        if not log_path.is_absolute():
            log_path = base_dir.parent / log_path
        log_path.parent.mkdir(parents=True, exist_ok=True)

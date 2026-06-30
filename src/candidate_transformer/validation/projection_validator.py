"""Projection config validator exports."""

from candidate_transformer.projection.config_loader import (
    ProjectionConfigError,
    validate_projection_config,
)

__all__ = ["ProjectionConfigError", "validate_projection_config"]

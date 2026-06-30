"""Validation helpers for configs, canonical records, and outputs."""

from candidate_transformer.validation.canonical_validator import validate_candidate
from candidate_transformer.validation.output_validator import (
    ValidationIssue,
    ValidationResult,
    validate_projected_output,
)
from candidate_transformer.validation.projection_validator import (
    ProjectionConfigError,
    validate_projection_config,
)

__all__ = [
    "ProjectionConfigError",
    "ValidationIssue",
    "ValidationResult",
    "validate_candidate",
    "validate_projected_output",
    "validate_projection_config",
]

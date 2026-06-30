"""Canonical profile validation helpers."""

from __future__ import annotations

from pydantic import ValidationError

from candidate_transformer.models import Candidate
from candidate_transformer.validation.output_validator import ValidationIssue, ValidationResult


def validate_candidate(candidate: Candidate | dict) -> ValidationResult:
    """Validate a canonical candidate without raising."""
    try:
        Candidate.model_validate(candidate)
    except ValidationError as exc:
        return ValidationResult(
            is_valid=False,
            errors=[
                ValidationIssue(
                    field=".".join(str(part) for part in error["loc"]) or "candidate",
                    message=error["msg"],
                    error_type=error["type"],
                )
                for error in exc.errors()
            ],
        )
    return ValidationResult(is_valid=True, errors=[])

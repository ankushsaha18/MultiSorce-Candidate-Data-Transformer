"""Projected output validation with Pydantic."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, create_model

from candidate_transformer.projection.config_loader import (
    ProjectionConfigError,
    validate_projection_config,
)


class ValidationIssue(BaseModel):
    """A structured validation error safe to return to callers."""

    model_config = ConfigDict(extra="forbid")

    field: str
    message: str
    error_type: str


class ValidationResult(BaseModel):
    """Non-throwing validation result for projected output."""

    model_config = ConfigDict(extra="forbid")

    is_valid: bool
    errors: list[ValidationIssue] = Field(default_factory=list)


class ConfidenceBlock(BaseModel):
    """Optional confidence metadata block."""

    model_config = ConfigDict(extra="allow")


class ProvenanceItem(BaseModel):
    """Projected provenance item shape."""

    model_config = ConfigDict(extra="allow")

    field: str
    value: Any = None
    source: str
    source_type: str
    method: str
    confidence: float = Field(ge=0.0, le=1.0)
    selected: bool


def validate_projected_output(output: dict[str, Any], config: dict[str, Any]) -> ValidationResult:
    """Validate projected output against the runtime projection config.

    This function never raises for validation failures. Invalid configs are also
    returned as structured errors so callers can report them without crashing.
    """
    try:
        validate_projection_config(config)
    except ProjectionConfigError as exc:
        return ValidationResult(
            is_valid=False,
            errors=[
                ValidationIssue(
                    field="config",
                    message=str(exc),
                    error_type="config_error",
                )
            ],
        )

    if not isinstance(output, dict):
        return ValidationResult(
            is_valid=False,
            errors=[
                ValidationIssue(
                    field="output",
                    message="Projected output must be an object",
                    error_type="type_error",
                )
            ],
        )

    model = _build_output_model(config)
    try:
        model.model_validate(output)
    except ValidationError as exc:
        return ValidationResult(is_valid=False, errors=_issues_from_validation_error(exc))

    return ValidationResult(is_valid=True, errors=[])


def _build_output_model(config: dict[str, Any]) -> type[BaseModel]:
    fields: dict[str, tuple[Any, Any]] = {}
    on_missing = config.get("on_missing", "null")

    for field_config in config["fields"]:
        path = field_config["path"]
        top_level_name = path.split(".", maxsplit=1)[0]
        annotation = _annotation_for_type(field_config.get("type", "any"))
        if not field_config.get("required"):
            annotation = annotation | None
        default = ... if field_config.get("required") else None
        fields[top_level_name] = (annotation, default)

    if config.get("include_confidence", False):
        fields["confidence"] = (ConfidenceBlock, ...)
        fields["overall_confidence"] = (float, ...)

    if config.get("include_provenance", False):
        fields["provenance"] = (list[ProvenanceItem], ...)

    return create_model(
        "ProjectedOutputModel",
        __config__=ConfigDict(extra="forbid"),
        **fields,
    )


def _annotation_for_type(type_name: str) -> Any:
    annotations = {
        "string": str,
        "number": float | int,
        "boolean": bool,
        "object": dict[str, Any],
        "array": list[Any],
        "string[]": list[str],
        "number[]": list[float | int],
        "any": Any,
    }
    return annotations[type_name]


def _issues_from_validation_error(exc: ValidationError) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"]) or "output"
        issues.append(
            ValidationIssue(
                field=location,
                message=error["msg"],
                error_type=error["type"],
            )
        )
    return issues

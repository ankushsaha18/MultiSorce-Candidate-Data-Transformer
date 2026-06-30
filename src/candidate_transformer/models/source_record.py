"""Intermediate source records emitted by source parsers."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SourceRecord(BaseModel):
    """A parsed source row/document represented with canonical field names.

    This is intentionally not the final canonical ``Candidate`` model. Source
    records preserve raw values and parser warnings so later stages can
    normalize, score, merge, and explain decisions deterministically.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    source_type: str
    source_id: str
    record_id: str
    canonical: dict[str, Any] = Field(default_factory=dict)
    raw: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("source_type", "source_id", "record_id")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        if not value:
            raise ValueError("source metadata fields cannot be empty")
        return value

    @field_validator("warnings")
    @classmethod
    def validate_warnings(cls, value: list[str]) -> list[str]:
        if any(not warning for warning in value):
            raise ValueError("warnings cannot contain empty values")
        return value

"""Canonical data models.

These models define the stable internal representation used after extraction
and normalization. They intentionally do not know anything about source parsing.
"""

from __future__ import annotations

from typing import Any, Literal
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Confidence = float
YearMonth = str

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_E164_RE = re.compile(r"^\+[1-9]\d{1,14}$")
_YEAR_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_URL_RE = re.compile(r"^https?://[^\s]+$")


class CanonicalBaseModel(BaseModel):
    """Base model settings shared by canonical models."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class Location(CanonicalBaseModel):
    """Normalized candidate location."""

    city: str | None = None
    region: str | None = None
    country: str | None = Field(
        default=None,
        description="ISO-3166 alpha-2 country code.",
    )

    @field_validator("city", "region")
    @classmethod
    def empty_location_parts_to_none(cls, value: str | None) -> str | None:
        if value == "":
            return None
        return value

    @field_validator("country")
    @classmethod
    def validate_country(cls, value: str | None) -> str | None:
        if value in {None, ""}:
            return None
        normalized = value.upper()
        if not re.fullmatch(r"[A-Z]{2}", normalized):
            raise ValueError("country must be an ISO-3166 alpha-2 code")
        return normalized


class Skill(CanonicalBaseModel):
    """Canonical skill with field-level confidence and contributing sources."""

    name: str
    confidence: Confidence = Field(ge=0.0, le=1.0)
    sources: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value:
            raise ValueError("skill name cannot be empty")
        return value

    @field_validator("sources")
    @classmethod
    def validate_sources(cls, value: list[str]) -> list[str]:
        if any(not source for source in value):
            raise ValueError("skill sources cannot contain empty values")
        return value


class Experience(CanonicalBaseModel):
    """Normalized work experience entry."""

    company: str | None = None
    title: str | None = None
    start: YearMonth | None = None
    end: YearMonth | Literal["present"] | None = None
    summary: str | None = None

    @field_validator("company", "title", "summary")
    @classmethod
    def empty_text_to_none(cls, value: str | None) -> str | None:
        if value == "":
            return None
        return value

    @field_validator("start")
    @classmethod
    def validate_start(cls, value: YearMonth | None) -> YearMonth | None:
        return _validate_year_month_or_none(value, "start")

    @field_validator("end")
    @classmethod
    def validate_end(
        cls, value: YearMonth | Literal["present"] | None
    ) -> YearMonth | Literal["present"] | None:
        if value == "present":
            return value
        return _validate_year_month_or_none(value, "end")

    @model_validator(mode="after")
    def validate_date_order(self) -> Experience:
        if self.start and self.end and self.end != "present" and self.end < self.start:
            raise ValueError("experience end date cannot be before start date")
        return self


class Education(CanonicalBaseModel):
    """Normalized education entry."""

    institution: str | None = None
    degree: str | None = None
    field: str | None = None
    end_year: int | None = Field(default=None, ge=1900, le=2200)

    @field_validator("institution", "degree", "field")
    @classmethod
    def empty_text_to_none(cls, value: str | None) -> str | None:
        if value == "":
            return None
        return value


class Provenance(CanonicalBaseModel):
    """Trace of a selected or rejected value back to its source."""

    field: str
    value: Any = None
    source: str
    source_type: str
    method: str
    confidence: Confidence = Field(ge=0.0, le=1.0)
    selected: bool = True
    location: dict[str, Any] | None = None

    @field_validator("field", "source", "source_type", "method")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        if not value:
            raise ValueError("provenance text fields cannot be empty")
        return value


class Links(CanonicalBaseModel):
    """Normalized candidate links."""

    linkedin: str | None = None
    github: str | None = None
    portfolio: str | None = None
    other: list[str] = Field(default_factory=list)

    @field_validator("linkedin", "github", "portfolio")
    @classmethod
    def validate_optional_url(cls, value: str | None) -> str | None:
        if value in {None, ""}:
            return None
        if not _URL_RE.fullmatch(value):
            raise ValueError("link must be an http or https URL")
        return value

    @field_validator("other")
    @classmethod
    def validate_other_urls(cls, value: list[str]) -> list[str]:
        for url in value:
            if not _URL_RE.fullmatch(url):
                raise ValueError("other links must be http or https URLs")
        return value


class Candidate(CanonicalBaseModel):
    """Canonical candidate profile."""

    candidate_id: str
    full_name: str | None = None
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    location: Location = Field(default_factory=Location)
    links: Links = Field(default_factory=Links)
    headline: str | None = None
    years_experience: float | None = Field(default=None, ge=0.0)
    skills: list[Skill] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    provenance: list[Provenance] = Field(default_factory=list)
    overall_confidence: Confidence = Field(ge=0.0, le=1.0)

    @field_validator("candidate_id")
    @classmethod
    def validate_candidate_id(cls, value: str) -> str:
        if not value:
            raise ValueError("candidate_id cannot be empty")
        return value

    @field_validator("full_name", "headline")
    @classmethod
    def empty_text_to_none(cls, value: str | None) -> str | None:
        if value == "":
            return None
        return value

    @field_validator("emails")
    @classmethod
    def validate_emails(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for email in value:
            lowered = email.lower()
            if not _EMAIL_RE.fullmatch(lowered):
                raise ValueError(f"invalid email: {email}")
            if lowered not in seen:
                normalized.append(lowered)
                seen.add(lowered)
        return normalized

    @field_validator("phones")
    @classmethod
    def validate_phones(cls, value: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for phone in value:
            if not _E164_RE.fullmatch(phone):
                raise ValueError(f"phone must be E.164: {phone}")
            if phone not in seen:
                deduped.append(phone)
                seen.add(phone)
        return deduped


def _validate_year_month_or_none(value: str | None, field_name: str) -> str | None:
    if value in {None, ""}:
        return None
    if not _YEAR_MONTH_RE.fullmatch(value):
        raise ValueError(f"{field_name} must be in YYYY-MM format")
    return value

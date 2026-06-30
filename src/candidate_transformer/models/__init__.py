"""Shared data models."""

from candidate_transformer.models.canonical import (
    Candidate,
    Education,
    Experience,
    Links,
    Location,
    Provenance,
    Skill,
)
from candidate_transformer.models.source_record import SourceRecord

__all__ = [
    "Candidate",
    "Education",
    "Experience",
    "Links",
    "Location",
    "Provenance",
    "Skill",
    "SourceRecord",
]

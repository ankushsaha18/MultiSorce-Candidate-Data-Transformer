"""Deterministic confidence scoring helpers."""

from __future__ import annotations

from candidate_transformer.confidence.signals import (
    SOURCE_FIELD_CONFIDENCE,
    UNKNOWN_SOURCE_CONFIDENCE,
)
from candidate_transformer.models import Provenance


def score_source_field(source_type: str) -> float:
    """Return the deterministic confidence for a field from a source type."""
    return SOURCE_FIELD_CONFIDENCE.get(source_type, UNKNOWN_SOURCE_CONFIDENCE)


def score_merged_list(confidences: list[float] | tuple[float, ...]) -> float:
    """Score a merged list item as the average of contributing confidences."""
    if not confidences:
        return 0.0
    return _round_confidence(sum(confidences) / len(confidences))


def score_overall_from_provenance(provenance: list[Provenance]) -> float:
    """Score overall confidence as the average of populated selected fields."""
    populated = [
        item.confidence
        for item in provenance
        if item.selected and _is_populated(item.value)
    ]
    if not populated:
        return 0.0
    return _round_confidence(sum(populated) / len(populated))


def _round_confidence(value: float) -> float:
    return round(value, 4)


def _is_populated(value: object) -> bool:
    if value is None:
        return False
    if value == "":
        return False
    if isinstance(value, (list, tuple, set, dict)) and not value:
        return False
    return True

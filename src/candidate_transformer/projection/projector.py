"""Runtime projection engine."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from candidate_transformer.models import Candidate
from candidate_transformer.normalization import (
    normalize_country_to_alpha2,
    normalize_date_to_year_month,
    normalize_phone_to_e164,
    normalize_skill_name,
)
from candidate_transformer.projection.config_loader import (
    ProjectionConfigError,
    validate_projection_config,
)
from candidate_transformer.projection.path_resolver import (
    PathResolutionError,
    provenance_field_pattern,
    resolve_path,
    set_path,
)


def project_candidate(candidate: Candidate, config: dict[str, Any]) -> dict[str, Any]:
    """Project a canonical candidate into a runtime-configured output dict.

    The canonical candidate is never mutated; projection always works from a
    serialized copy of the model.
    """
    validate_projection_config(config)
    canonical = deepcopy(candidate.model_dump(mode="json"))
    output: dict[str, Any] = {}
    confidence: dict[str, float] = {}
    provenance = []

    on_missing = config.get("on_missing", "null")

    for field_config in config["fields"]:
        dest_path = field_config["path"]
        source_path = field_config.get("from", dest_path)

        try:
            value = resolve_path(canonical, source_path)
        except (PathResolutionError, IndexError, TypeError):
            value = None

        if value is None:
            if field_config.get("required") or on_missing == "error":
                raise ProjectionConfigError(f"missing required projection value: {source_path}")
            if on_missing == "omit":
                continue

        value = _apply_normalization(value, field_config.get("normalize"))
        _validate_projected_type(value, field_config.get("type"), dest_path)
        set_path(output, dest_path, value)

        if config.get("include_confidence", False):
            field_confidence = _confidence_for_path(candidate, source_path)
            if field_confidence is not None:
                set_path(confidence, dest_path, field_confidence)

        if config.get("include_provenance", False):
            provenance.extend(_provenance_for_path(candidate, source_path))

    if config.get("include_confidence", False):
        output["confidence"] = confidence
        output["overall_confidence"] = candidate.overall_confidence

    if config.get("include_provenance", False):
        output["provenance"] = _dedupe_provenance(provenance)

    return output


def _apply_normalization(value: Any, normalize: str | None) -> Any:
    if normalize is None or value is None:
        return value

    if isinstance(value, list):
        return [_apply_normalization(item, normalize) for item in value]

    if normalize == "E164":
        return normalize_phone_to_e164(str(value))
    if normalize == "YYYY-MM":
        return normalize_date_to_year_month(str(value))
    if normalize == "canonical":
        return normalize_skill_name(str(value))
    if normalize == "ISO-3166-alpha2":
        return normalize_country_to_alpha2(str(value))

    raise ProjectionConfigError(f"unsupported normalization option: {normalize}")


def _validate_projected_type(value: Any, expected_type: str | None, path: str) -> None:
    if expected_type in {None, "any"} or value is None:
        return

    validators = {
        "string": lambda item: isinstance(item, str),
        "number": lambda item: isinstance(item, int | float) and not isinstance(item, bool),
        "boolean": lambda item: isinstance(item, bool),
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
        "string[]": lambda item: isinstance(item, list) and all(isinstance(child, str) for child in item),
        "number[]": lambda item: isinstance(item, list)
        and all(isinstance(child, int | float) and not isinstance(child, bool) for child in item),
    }

    validator = validators.get(expected_type)
    if validator is None:
        raise ProjectionConfigError(f"unsupported projected type: {expected_type}")
    if not validator(value):
        raise ProjectionConfigError(f"projected field {path} does not match type {expected_type}")


def _confidence_for_path(candidate: Candidate, source_path: str) -> float | None:
    matches = _provenance_for_path(candidate, source_path)
    selected = [item["confidence"] for item in matches if item.get("selected")]
    if not selected:
        return None
    return round(sum(selected) / len(selected), 4)


def _provenance_for_path(candidate: Candidate, source_path: str) -> list[dict[str, Any]]:
    pattern = provenance_field_pattern(source_path)
    return [
        item.model_dump(mode="json")
        for item in candidate.provenance
        if item.selected and pattern.fullmatch(item.field)
    ]


def _dedupe_provenance(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for item in items:
        key = (item["field"], item["source"], repr(item["value"]))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped

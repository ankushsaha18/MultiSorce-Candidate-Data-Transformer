"""Deterministic candidate merge engine."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any
import re

from candidate_transformer.models import (
    Candidate,
    Education,
    Experience,
    Provenance,
    Skill,
    SourceRecord,
)
from candidate_transformer.confidence import (
    score_merged_list,
    score_overall_from_provenance,
    score_source_field,
)
from candidate_transformer.normalization import (
    normalize_date_range,
    normalize_date_to_year_month,
    normalize_phone_to_e164,
    normalize_skill_name,
)

SOURCE_PRIORITY = {
    "resume_pdf": 100,
    "recruiter_csv": 50,
}

@dataclass(frozen=True)
class MergeValue:
    """A candidate value plus source metadata used for deterministic ordering."""

    field: str
    value: Any
    record: SourceRecord
    index: int = 0

    @property
    def priority(self) -> int:
        return SOURCE_PRIORITY.get(self.record.source_type, 0)

    @property
    def confidence(self) -> float:
        return score_source_field(self.record.source_type)

    @property
    def source(self) -> str:
        return self.record.record_id


def merge_two_candidate_records(left: SourceRecord, right: SourceRecord) -> Candidate:
    """Merge exactly two intermediate candidate records."""
    return merge_candidate_records([left, right])


def merge_candidate_records(records: list[SourceRecord]) -> Candidate:
    """Merge one or more source records into a canonical candidate."""
    if not records:
        raise ValueError("at least one source record is required")

    ordered_records = sorted(
        records,
        key=lambda record: (
            -SOURCE_PRIORITY.get(record.source_type, 0),
            record.source_type,
            record.source_id,
            record.record_id,
        ),
    )

    provenance: list[Provenance] = []
    full_name = _merge_singleton("full_name", ordered_records, provenance)
    headline = _merge_singleton("headline", ordered_records, provenance)
    years_experience = _merge_number_singleton("years_experience", ordered_records, provenance)
    location = _merge_mapping_singleton("location", ordered_records, provenance)
    links = _merge_mapping_singleton("links", ordered_records, provenance)
    emails = _merge_emails(ordered_records, provenance)
    phones = _merge_phones(ordered_records, provenance)
    skills = _merge_skills(ordered_records, provenance)
    experience = _merge_experience(ordered_records, provenance)
    education = _merge_education(ordered_records, provenance)

    candidate = Candidate(
        candidate_id=_candidate_id(full_name, emails, phones, ordered_records),
        full_name=full_name,
        emails=emails,
        phones=phones,
        location=location or {},
        links=links or {},
        headline=headline,
        years_experience=years_experience,
        skills=skills,
        experience=experience,
        education=education,
        provenance=sorted(provenance, key=lambda item: (item.field, not item.selected, item.source)),
        overall_confidence=_overall_confidence(provenance),
    )
    return candidate


def _merge_singleton(
    field: str,
    records: list[SourceRecord],
    provenance: list[Provenance],
) -> str | None:
    values = [
        MergeValue(field=field, value=value, record=record)
        for record in records
        if (value := _clean_text(record.canonical.get(field)))
    ]
    if not values:
        return None

    selected = _select_best(values)
    provenance.append(_provenance(field, selected, selected=True))

    for rejected in values:
        if rejected is selected or rejected.value == selected.value:
            continue
        provenance.append(_provenance(field, rejected, selected=False))

    return selected.value


def _merge_number_singleton(
    field: str,
    records: list[SourceRecord],
    provenance: list[Provenance],
) -> float | None:
    values = [
        MergeValue(field=field, value=value, record=record)
        for record in records
        if (value := record.canonical.get(field)) is not None
    ]
    if not values:
        return None
    selected = _select_best(values)
    provenance.append(_provenance(field, selected, selected=True))
    try:
        return float(selected.value)
    except (TypeError, ValueError):
        return None


def _merge_mapping_singleton(
    field: str,
    records: list[SourceRecord],
    provenance: list[Provenance],
) -> dict[str, Any] | None:
    values = [
        MergeValue(field=field, value=value, record=record)
        for record in records
        if isinstance((value := record.canonical.get(field)), dict)
        and any(_is_populated(child) for child in value.values())
    ]
    if not values:
        return None
    selected = _select_best(values)
    provenance.append(_provenance(field, selected, selected=True))
    return selected.value


def _merge_emails(records: list[SourceRecord], provenance: list[Provenance]) -> list[str]:
    values: list[MergeValue] = []
    for record in records:
        for index, email in enumerate(_as_list(record.canonical.get("emails"))):
            normalized = _clean_text(email)
            if normalized:
                values.append(MergeValue("emails", normalized.lower(), record, index))

    return _merge_unique_scalars("emails", values, provenance)


def _merge_phones(records: list[SourceRecord], provenance: list[Provenance]) -> list[str]:
    values: list[MergeValue] = []
    for record in records:
        for index, phone in enumerate(_as_list(record.canonical.get("phones"))):
            normalized = normalize_phone_to_e164(_clean_text(phone), default_region="US")
            if normalized:
                values.append(MergeValue("phones", normalized, record, index))

    return _merge_unique_scalars("phones", values, provenance)


def _merge_unique_scalars(
    field: str,
    values: list[MergeValue],
    provenance: list[Provenance],
) -> list[str]:
    grouped_by_value: dict[str, list[MergeValue]] = {}
    for value in sorted(values, key=_merge_value_sort_key):
        grouped_by_value.setdefault(value.value, []).append(value)

    selected = sorted(
        (_select_best(group) for group in grouped_by_value.values()),
        key=_merge_value_sort_key,
    )
    output: list[str] = []
    for index, item in enumerate(selected):
        output.append(item.value)
        confidence = score_merged_list(
            [contributor.confidence for contributor in grouped_by_value[item.value]]
        )
        provenance.append(
            _provenance(
                f"{field}[{index}]",
                item,
                selected=True,
                confidence=confidence,
            )
        )
    return output


def _merge_skills(records: list[SourceRecord], provenance: list[Provenance]) -> list[Skill]:
    grouped: dict[str, list[MergeValue]] = {}
    display_names: dict[str, str] = {}

    for record in records:
        for index, raw_skill in enumerate(_as_list(record.canonical.get("skills"))):
            raw_name = raw_skill.get("name") if isinstance(raw_skill, dict) else raw_skill
            skill_name = normalize_skill_name(_clean_text(raw_name))
            if not skill_name:
                continue
            key = skill_name.casefold()
            display_names[key] = skill_name
            grouped.setdefault(key, []).append(MergeValue("skills", skill_name, record, index))

    skills: list[Skill] = []
    for index, key in enumerate(sorted(grouped, key=lambda item: display_names[item].casefold())):
        sources = sorted({item.source for item in grouped[key]})
        confidence = score_merged_list([item.confidence for item in grouped[key]])
        skill = Skill(name=display_names[key], confidence=confidence, sources=sources)
        skills.append(skill)
        best = _select_best(grouped[key])
        provenance.append(
            _provenance(
                f"skills[{index}].name",
                best,
                selected=True,
                value=skill.name,
                confidence=confidence,
            )
        )

    return skills


def _merge_experience(
    records: list[SourceRecord],
    provenance: list[Provenance],
) -> list[Experience]:
    grouped: dict[tuple[str, str], list[MergeValue]] = {}

    for record in records:
        for index, raw_experience in enumerate(_as_list(record.canonical.get("experience"))):
            if not isinstance(raw_experience, dict):
                continue
            normalized = _normalize_experience(raw_experience)
            if not any(normalized.values()):
                continue
            key = (
                _key_text(normalized.get("company")) or f"unknown-company-{record.record_id}-{index}",
                _key_text(normalized.get("title")) or "unknown-title",
            )
            grouped.setdefault(key, []).append(
                MergeValue("experience", normalized, record, index)
            )

    experiences: list[Experience] = []
    for index, key in enumerate(sorted(grouped)):
        merged = _merge_dict_fields(
            grouped[key],
            fields=["company", "title", "start", "end", "summary"],
            base_field=f"experience[{index}]",
            provenance=provenance,
        )
        experiences.append(Experience(**merged))

    return experiences


def _merge_education(records: list[SourceRecord], provenance: list[Provenance]) -> list[Education]:
    grouped: dict[tuple[str, str], list[MergeValue]] = {}

    for record in records:
        for index, raw_education in enumerate(_as_list(record.canonical.get("education"))):
            if not isinstance(raw_education, dict):
                continue
            normalized = _normalize_education(raw_education)
            if not any(value is not None for value in normalized.values()):
                continue
            key = (
                _key_text(normalized.get("institution")) or f"unknown-institution-{record.record_id}-{index}",
                _key_text(normalized.get("degree")) or "unknown-degree",
            )
            grouped.setdefault(key, []).append(
                MergeValue("education", normalized, record, index)
            )

    education: list[Education] = []
    for index, key in enumerate(sorted(grouped)):
        merged = _merge_dict_fields(
            grouped[key],
            fields=["institution", "degree", "field", "end_year"],
            base_field=f"education[{index}]",
            provenance=provenance,
        )
        education.append(Education(**merged))

    return education


def _merge_dict_fields(
    values: list[MergeValue],
    fields: list[str],
    base_field: str,
    provenance: list[Provenance],
) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for field in fields:
        field_values = [
            MergeValue(field=field, value=item.value.get(field), record=item.record, index=item.index)
            for item in values
            if item.value.get(field) is not None
        ]
        if not field_values:
            merged[field] = None
            continue
        selected = _select_best(field_values)
        merged[field] = selected.value
        provenance.append(_provenance(f"{base_field}.{field}", selected, selected=True))
    return merged


def _normalize_experience(raw: dict[str, Any]) -> dict[str, Any]:
    start = normalize_date_to_year_month(_clean_text(raw.get("start")))
    end_value = _clean_text(raw.get("end"))
    end: str | None

    if end_value and _looks_like_date_range(end_value):
        range_start, range_end = normalize_date_range(end_value)
        start = start or range_start
        end = range_end
    elif end_value and end_value.lower() in {"present", "current", "now"}:
        end = "present"
    else:
        end = normalize_date_to_year_month(end_value, default_month=12)

    return {
        "company": _clean_text(raw.get("company")),
        "title": _clean_text(raw.get("title")),
        "start": start,
        "end": end,
        "summary": _clean_text(raw.get("summary")),
    }


def _normalize_education(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "institution": _clean_text(raw.get("institution")),
        "degree": _clean_text(raw.get("degree")),
        "field": _clean_text(raw.get("field")),
        "end_year": _clean_int(raw.get("end_year")),
    }


def _select_best(values: list[MergeValue]) -> MergeValue:
    return sorted(values, key=_merge_value_sort_key)[0]


def _merge_value_sort_key(value: MergeValue) -> tuple[Any, ...]:
    return (
        -value.priority,
        value.record.source_type,
        value.record.source_id,
        value.record.record_id,
        value.index,
        _stable_value(value.value),
    )


def _provenance(
    field: str,
    item: MergeValue,
    selected: bool,
    value: Any | None = None,
    confidence: float | None = None,
) -> Provenance:
    return Provenance(
        field=field,
        value=item.value if value is None else value,
        source=item.source,
        source_type=item.record.source_type,
        method=f"merge:{field}",
        confidence=item.confidence if confidence is None else confidence,
        selected=selected,
    )


def _candidate_id(
    full_name: str | None,
    emails: list[str],
    phones: list[str],
    records: list[SourceRecord],
) -> str:
    if emails:
        seed = f"email:{emails[0]}"
    elif phones:
        seed = f"phone:{phones[0]}"
    elif full_name:
        seed = f"name:{full_name.casefold()}"
    else:
        seed = "|".join(record.record_id for record in records)
    return "candidate_" + sha256(seed.encode("utf-8")).hexdigest()[:16]


def _overall_confidence(provenance: list[Provenance]) -> float:
    return score_overall_from_provenance(provenance)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clean_int(value: Any) -> int | None:
    if value in {None, ""}:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _key_text(value: Any) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def _stable_value(value: Any) -> str:
    return repr(value)


def _looks_like_date_range(value: str) -> bool:
    return bool(re.search(r"\s(?:-|–|—|to)\s", value, flags=re.IGNORECASE))


def _is_populated(value: Any) -> bool:
    if value is None or value == "":
        return False
    if isinstance(value, (list, tuple, set, dict)) and not value:
        return False
    return True

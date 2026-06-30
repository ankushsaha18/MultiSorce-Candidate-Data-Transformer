from __future__ import annotations

import json

import pytest

from candidate_transformer.models import Candidate, Provenance, Skill
from candidate_transformer.projection import (
    ProjectionConfigError,
    load_projection_config,
    project_candidate,
)


def _candidate() -> Candidate:
    return Candidate(
        candidate_id="candidate_123",
        full_name="Ada Lovelace",
        emails=["ada@example.com", "ada.work@example.com"],
        phones=["+14155552671"],
        skills=[
            Skill(name="Python", confidence=0.925, sources=["csv:row_2", "resume:document"]),
            Skill(name="SQL", confidence=0.90, sources=["csv:row_2"]),
        ],
        provenance=[
            Provenance(
                field="full_name",
                value="Ada Lovelace",
                source="resume:document",
                source_type="resume_pdf",
                method="merge:full_name",
                confidence=0.95,
                selected=True,
            ),
            Provenance(
                field="emails[0]",
                value="ada@example.com",
                source="resume:document",
                source_type="resume_pdf",
                method="merge:emails[0]",
                confidence=0.925,
                selected=True,
            ),
            Provenance(
                field="skills[0].name",
                value="Python",
                source="resume:document",
                source_type="resume_pdf",
                method="merge:skills[0].name",
                confidence=0.925,
                selected=True,
            ),
        ],
        overall_confidence=0.9333,
    )


def test_load_projection_config_reads_json(tmp_path):
    path = tmp_path / "projection.json"
    path.write_text(
        json.dumps({"fields": [{"path": "full_name", "type": "string"}]}),
        encoding="utf-8",
    )

    assert load_projection_config(path)["fields"][0]["path"] == "full_name"


def test_project_candidate_selects_renames_and_maps_fields_without_mutation():
    candidate = _candidate()
    before = candidate.model_dump()
    config = {
        "fields": [
            {"path": "name", "from": "full_name", "type": "string"},
            {"path": "primary_email", "from": "emails[0]", "type": "string"},
            {"path": "skills", "from": "skills[].name", "type": "string[]"},
        ],
        "include_confidence": False,
        "include_provenance": False,
        "on_missing": "null",
    }

    projected = project_candidate(candidate, config)

    assert projected == {
        "name": "Ada Lovelace",
        "primary_email": "ada@example.com",
        "skills": ["Python", "SQL"],
    }
    assert candidate.model_dump() == before


def test_project_candidate_includes_confidence_and_provenance():
    projected = project_candidate(
        _candidate(),
        {
            "fields": [
                {"path": "name", "from": "full_name", "type": "string"},
                {"path": "skills", "from": "skills[].name", "type": "string[]"},
            ],
            "include_confidence": True,
            "include_provenance": True,
            "on_missing": "null",
        },
    )

    assert projected["confidence"]["name"] == 0.95
    assert projected["confidence"]["skills"] == 0.925
    assert projected["overall_confidence"] == 0.9333
    assert [item["field"] for item in projected["provenance"]] == [
        "full_name",
        "skills[0].name",
    ]


def test_project_candidate_missing_behaviour_null_and_omit():
    candidate = _candidate()
    null_projected = project_candidate(
        candidate,
        {
            "fields": [{"path": "github", "from": "links.github", "type": "string"}],
            "on_missing": "null",
        },
    )
    omit_projected = project_candidate(
        candidate,
        {
            "fields": [{"path": "github", "from": "links.github", "type": "string"}],
            "on_missing": "omit",
        },
    )

    assert null_projected == {"github": None}
    assert omit_projected == {}


def test_project_candidate_missing_behaviour_error():
    with pytest.raises(ProjectionConfigError):
        project_candidate(
            _candidate(),
            {
                "fields": [{"path": "github", "from": "links.github", "type": "string"}],
                "on_missing": "error",
            },
        )


def test_project_candidate_applies_normalization_options():
    candidate = _candidate()
    projected = project_candidate(
        candidate,
        {
            "fields": [
                {"path": "phone", "from": "phones[0]", "type": "string", "normalize": "E164"},
                {"path": "first_skill", "from": "skills[0].name", "type": "string", "normalize": "canonical"},
            ],
            "on_missing": "null",
        },
    )

    assert projected["phone"] == "+14155552671"
    assert projected["first_skill"] == "Python"


def test_project_candidate_validates_projected_type():
    with pytest.raises(ProjectionConfigError):
        project_candidate(
            _candidate(),
            {
                "fields": [{"path": "emails", "from": "emails", "type": "string"}],
                "on_missing": "null",
            },
        )


def test_load_projection_config_returns_meaningful_errors(tmp_path):
    missing_path = tmp_path / "missing.json"
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text("{not json", encoding="utf-8")

    with pytest.raises(ProjectionConfigError, match="does not exist"):
        load_projection_config(missing_path)
    with pytest.raises(ProjectionConfigError, match="Invalid projection config JSON"):
        load_projection_config(invalid_path)


def test_project_candidate_supports_nested_destination_paths():
    projected = project_candidate(
        _candidate(),
        {
            "fields": [
                {"path": "profile.name", "from": "full_name", "type": "string"},
                {"path": "profile.contact.email", "from": "emails[0]", "type": "string"},
            ],
            "on_missing": "null",
        },
    )

    assert projected == {
        "profile": {
            "name": "Ada Lovelace",
            "contact": {"email": "ada@example.com"},
        }
    }

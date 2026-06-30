from __future__ import annotations

from candidate_transformer.validation import validate_candidate, validate_projected_output


def test_validate_projected_output_accepts_valid_output():
    config = {
        "fields": [
            {"path": "name", "from": "full_name", "type": "string", "required": True},
            {"path": "skills", "from": "skills[].name", "type": "string[]"},
        ],
        "include_confidence": True,
        "include_provenance": True,
        "on_missing": "null",
    }
    output = {
        "name": "Ada Lovelace",
        "skills": ["Python", "SQL"],
        "confidence": {"name": 0.95, "skills": 0.925},
        "overall_confidence": 0.9333,
        "provenance": [
            {
                "field": "full_name",
                "value": "Ada Lovelace",
                "source": "resume:document",
                "source_type": "resume_pdf",
                "method": "merge:full_name",
                "confidence": 0.95,
                "selected": True,
            }
        ],
    }

    result = validate_projected_output(output, config)

    assert result.is_valid
    assert result.errors == []


def test_validate_projected_output_returns_meaningful_type_errors():
    config = {
        "fields": [
            {"path": "name", "type": "string", "required": True},
            {"path": "skills", "type": "string[]"},
        ],
        "on_missing": "null",
    }
    output = {
        "name": 123,
        "skills": ["Python", 42],
    }

    result = validate_projected_output(output, config)

    assert not result.is_valid
    assert {error.field for error in result.errors} == {"name", "skills.1"}
    assert all(error.message for error in result.errors)


def test_validate_projected_output_returns_missing_required_error():
    config = {
        "fields": [{"path": "name", "type": "string", "required": True}],
        "on_missing": "null",
    }

    result = validate_projected_output({}, config)

    assert not result.is_valid
    assert result.errors[0].field == "name"
    assert "Field required" in result.errors[0].message


def test_validate_projected_output_rejects_extra_fields():
    config = {
        "fields": [{"path": "name", "type": "string"}],
        "on_missing": "null",
    }

    result = validate_projected_output({"name": "Ada", "unexpected": True}, config)

    assert not result.is_valid
    assert result.errors[0].field == "unexpected"
    assert result.errors[0].error_type == "extra_forbidden"


def test_validate_projected_output_returns_config_errors_without_crashing():
    result = validate_projected_output({}, {"fields": [{"path": "name", "type": "bogus"}]})

    assert not result.is_valid
    assert result.errors[0].field == "config"
    assert result.errors[0].error_type == "config_error"


def test_validate_projected_output_validates_metadata_blocks():
    config = {
        "fields": [{"path": "name", "type": "string"}],
        "include_confidence": True,
        "include_provenance": True,
        "on_missing": "null",
    }
    output = {
        "name": "Ada",
        "confidence": {},
        "overall_confidence": "high",
        "provenance": [{"field": "name"}],
    }

    result = validate_projected_output(output, config)

    assert not result.is_valid
    fields = {error.field for error in result.errors}
    assert "overall_confidence" in fields
    assert "provenance.0.source" in fields


def test_validate_projected_output_handles_non_object_output_without_crashing():
    result = validate_projected_output(
        ["not", "an", "object"],
        {"fields": [{"path": "name", "type": "string"}]},
    )

    assert not result.is_valid
    assert result.errors[0].field == "output"
    assert "must be an object" in result.errors[0].message


def test_validate_candidate_returns_structured_errors():
    result = validate_candidate(
        {
            "candidate_id": "",
            "emails": ["not-an-email"],
            "overall_confidence": 1.5,
        }
    )

    assert not result.is_valid
    fields = {error.field for error in result.errors}
    assert "candidate_id" in fields
    assert "emails" in fields
    assert "overall_confidence" in fields

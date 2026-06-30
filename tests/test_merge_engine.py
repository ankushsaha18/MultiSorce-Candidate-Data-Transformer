from __future__ import annotations

from candidate_transformer.merge import merge_candidate_records, merge_two_candidate_records
from candidate_transformer.models import SourceRecord


def _record(source_type: str, canonical: dict, record_id: str) -> SourceRecord:
    return SourceRecord(
        source_type=source_type,
        source_id=f"{source_type}.fixture",
        record_id=record_id,
        canonical=canonical,
    )


def test_merge_prefers_resume_for_singleton_conflicts():
    csv = _record(
        "recruiter_csv",
        {
            "full_name": "Ada L.",
            "headline": "Engineer",
            "emails": ["ada@example.com"],
        },
        "csv:row_2",
    )
    resume = _record(
        "resume_pdf",
        {
            "full_name": "Ada Lovelace",
            "headline": "Senior Backend Engineer",
            "emails": ["ada@example.com"],
        },
        "resume:document",
    )

    candidate = merge_two_candidate_records(csv, resume)

    assert candidate.full_name == "Ada Lovelace"
    assert candidate.headline == "Senior Backend Engineer"
    assert candidate.emails == ["ada@example.com"]
    rejected_names = [
        item for item in candidate.provenance if item.field == "full_name" and not item.selected
    ]
    assert rejected_names[0].value == "Ada L."


def test_merge_removes_duplicate_emails_and_phones():
    csv = _record(
        "recruiter_csv",
        {
            "full_name": "Ada Lovelace",
            "emails": ["ADA@example.com"],
            "phones": ["415-555-2671"],
        },
        "csv:row_2",
    )
    resume = _record(
        "resume_pdf",
        {
            "emails": ["ada@example.com", "ada.work@example.com"],
            "phones": ["+1 415 555 2671"],
        },
        "resume:document",
    )

    candidate = merge_candidate_records([csv, resume])

    assert candidate.emails == ["ada@example.com", "ada.work@example.com"]
    assert candidate.phones == ["+14155552671"]


def test_merge_skills_by_canonical_name():
    csv = _record(
        "recruiter_csv",
        {
            "full_name": "Ada Lovelace",
            "emails": ["ada@example.com"],
            "skills": [{"name": "py", "confidence": 0.2, "sources": []}, {"name": "SQL"}],
        },
        "csv:row_2",
    )
    resume = _record(
        "resume_pdf",
        {
            "skills": [{"name": "Python"}, {"name": "distributed systems"}],
        },
        "resume:document",
    )

    candidate = merge_candidate_records([csv, resume])

    assert [skill.name for skill in candidate.skills] == [
        "Distributed Systems",
        "Python",
        "SQL",
    ]
    python_skill = next(skill for skill in candidate.skills if skill.name == "Python")
    assert python_skill.sources == ["csv:row_2", "resume:document"]


def test_merge_experience_combines_matching_roles_with_resume_priority():
    csv = _record(
        "recruiter_csv",
        {
            "full_name": "Ada Lovelace",
            "emails": ["ada@example.com"],
            "experience": [
                {
                    "company": "Analytical Engines Inc",
                    "title": "Engineer",
                    "start": None,
                    "end": None,
                    "summary": None,
                }
            ],
        },
        "csv:row_2",
    )
    resume = _record(
        "resume_pdf",
        {
            "experience": [
                {
                    "company": "Analytical Engines Inc",
                    "title": "Engineer",
                    "start": "Jan 2022",
                    "end": "Present",
                    "summary": "Built deterministic pipelines.",
                }
            ],
        },
        "resume:document",
    )

    candidate = merge_candidate_records([csv, resume])

    assert len(candidate.experience) == 1
    assert candidate.experience[0].company == "Analytical Engines Inc"
    assert candidate.experience[0].title == "Engineer"
    assert candidate.experience[0].start == "2022-01"
    assert candidate.experience[0].end == "present"
    assert candidate.experience[0].summary == "Built deterministic pipelines."


def test_merge_education_combines_matching_entries_with_resume_priority():
    csv = _record(
        "recruiter_csv",
        {
            "full_name": "Ada Lovelace",
            "emails": ["ada@example.com"],
            "education": [
                {
                    "institution": "University of London",
                    "degree": "BS",
                    "field": None,
                    "end_year": None,
                }
            ],
        },
        "csv:row_2",
    )
    resume = _record(
        "resume_pdf",
        {
            "education": [
                {
                    "institution": "University of London",
                    "degree": "BS",
                    "field": "Mathematics",
                    "end_year": 2020,
                }
            ],
        },
        "resume:document",
    )

    candidate = merge_candidate_records([csv, resume])

    assert len(candidate.education) == 1
    assert candidate.education[0].institution == "University of London"
    assert candidate.education[0].degree == "BS"
    assert candidate.education[0].field == "Mathematics"
    assert candidate.education[0].end_year == 2020


def test_merge_is_deterministic_regardless_of_input_order():
    csv = _record(
        "recruiter_csv",
        {
            "full_name": "Ada L.",
            "emails": ["ada@example.com"],
            "phones": ["415-555-2671"],
        },
        "csv:row_2",
    )
    resume = _record(
        "resume_pdf",
        {
            "full_name": "Ada Lovelace",
            "emails": ["ada@example.com"],
            "phones": ["+1 415 555 2671"],
        },
        "resume:document",
    )

    first = merge_candidate_records([csv, resume])
    second = merge_candidate_records([resume, csv])

    assert first.model_dump() == second.model_dump()
    assert first.candidate_id == second.candidate_id


def test_merge_generates_provenance_for_selected_fields():
    csv = _record(
        "recruiter_csv",
        {
            "full_name": "Ada Lovelace",
            "emails": ["ada@example.com"],
            "phones": ["415-555-2671"],
        },
        "csv:row_2",
    )
    resume = _record(
        "resume_pdf",
        {
            "skills": [{"name": "Python"}],
        },
        "resume:document",
    )

    candidate = merge_candidate_records([csv, resume])
    selected_fields = {item.field for item in candidate.provenance if item.selected}

    assert "full_name" in selected_fields
    assert "emails[0]" in selected_fields
    assert "phones[0]" in selected_fields
    assert "skills[0].name" in selected_fields


def test_merge_confidence_uses_fixed_source_and_average_rules():
    csv = _record(
        "recruiter_csv",
        {
            "full_name": "Ada L.",
            "emails": ["ada@example.com"],
            "skills": [{"name": "py"}],
        },
        "csv:row_2",
    )
    resume = _record(
        "resume_pdf",
        {
            "full_name": "Ada Lovelace",
            "emails": ["ada@example.com"],
            "skills": [{"name": "Python"}],
        },
        "resume:document",
    )

    candidate = merge_candidate_records([csv, resume])

    assert next(item for item in candidate.provenance if item.field == "full_name" and item.selected).confidence == 0.95
    assert next(item for item in candidate.provenance if item.field == "emails[0]").confidence == 0.925
    assert candidate.skills[0].confidence == 0.925
    assert candidate.overall_confidence == 0.9333


def test_merge_keeps_distinct_experience_and_education_entries():
    csv = _record(
        "recruiter_csv",
        {
            "full_name": "Ada Lovelace",
            "emails": ["ada@example.com"],
            "experience": [
                {
                    "company": "Analytical Engines Inc",
                    "title": "Engineer",
                    "start": "2020",
                    "end": "2021",
                    "summary": None,
                }
            ],
            "education": [
                {
                    "institution": "University of London",
                    "degree": "BS",
                    "field": "Mathematics",
                    "end_year": 2020,
                }
            ],
        },
        "csv:row_2",
    )
    resume = _record(
        "resume_pdf",
        {
            "experience": [
                {
                    "company": "Different Data Co",
                    "title": "Senior Engineer",
                    "start": "Jan 2022",
                    "end": "Present",
                    "summary": "Built pipelines.",
                }
            ],
            "education": [
                {
                    "institution": "Oxford University",
                    "degree": "MS",
                    "field": "Computer Science",
                    "end_year": 2022,
                }
            ],
        },
        "resume:document",
    )

    candidate = merge_candidate_records([csv, resume])

    assert [experience.company for experience in candidate.experience] == [
        "Analytical Engines Inc",
        "Different Data Co",
    ]
    assert [education.institution for education in candidate.education] == [
        "Oxford University",
        "University of London",
    ]

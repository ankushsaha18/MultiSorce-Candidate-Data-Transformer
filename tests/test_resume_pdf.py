from __future__ import annotations

import logging

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from candidate_transformer.sources.resume_pdf import ResumePdfParser


def _write_pdf(path, lines: list[str]) -> None:
    pdf = canvas.Canvas(str(path), pagesize=letter)
    _, height = letter
    y = height - 72
    for line in lines:
        pdf.drawString(72, y, line)
        y -= 16
    pdf.save()


def test_parse_resume_pdf_extracts_structured_source_record(tmp_path):
    pdf_path = tmp_path / "resume.pdf"
    _write_pdf(
        pdf_path,
        [
            "Ada Lovelace",
            "Senior Backend Engineer",
            "ada@example.com | +1 415 555 2671",
            "Skills",
            "Python, SQL, Distributed Systems",
            "Experience",
            "Analytical Engines Inc",
            "Backend Engineer",
            "Jan 2022 - Present",
            "Built deterministic data pipelines.",
            "Education",
            "University of London",
            "Bachelor of Science in Mathematics, 2020",
        ],
    )

    records = ResumePdfParser().parse(pdf_path)

    assert len(records) == 1
    record = records[0]
    assert record.source_type == "resume_pdf"
    assert record.source_id == "resume.pdf"
    assert record.record_id == "resume.pdf:document"
    assert record.canonical["full_name"] == "Ada Lovelace"
    assert record.canonical["headline"] == "Senior Backend Engineer"
    assert record.canonical["emails"] == ["ada@example.com"]
    assert record.canonical["phones"] == ["+1 415 555 2671"]
    assert [skill["name"] for skill in record.canonical["skills"]] == [
        "Python",
        "SQL",
        "Distributed Systems",
    ]
    assert record.canonical["experience"] == [
            {
                "company": "Analytical Engines Inc",
                "title": "Backend Engineer",
                "start": "2022-01",
                "end": "present",
                "summary": "Built deterministic data pipelines.",
            }
        ]
    assert record.canonical["education"] == [
        {
            "institution": "University of London",
            "degree": "Bachelor of Science",
            "field": "Mathematics",
            "end_year": 2020,
        }
    ]
    assert "Ada Lovelace" in record.raw["text"]
    assert record.warnings == []


def test_parse_resume_pdf_logs_missing_file(tmp_path, caplog):
    pdf_path = tmp_path / "missing.pdf"

    with caplog.at_level(logging.WARNING):
        records = ResumePdfParser().parse(pdf_path)

    assert records == []
    assert "file does not exist" in caplog.text


def test_parse_resume_pdf_handles_malformed_pdf(tmp_path, caplog):
    pdf_path = tmp_path / "bad.pdf"
    pdf_path.write_text("not a real pdf", encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        records = ResumePdfParser().parse(pdf_path)

    assert records == []
    assert "malformed or unreadable" in caplog.text


def test_parse_resume_pdf_returns_record_with_warnings_for_sparse_pdf(tmp_path):
    pdf_path = tmp_path / "sparse.pdf"
    _write_pdf(pdf_path, ["Skills", "Python"])

    records = ResumePdfParser().parse(pdf_path)

    assert len(records) == 1
    assert records[0].canonical["skills"][0]["name"] == "Python"
    assert "missing_full_name" not in records[0].warnings
    assert "missing full_name" in records[0].warnings
    assert "missing email" in records[0].warnings


def test_parse_resume_pdf_handles_blank_pdf_without_crashing(tmp_path, caplog):
    pdf_path = tmp_path / "blank.pdf"
    pdf = canvas.Canvas(str(pdf_path), pagesize=letter)
    pdf.showPage()
    pdf.save()

    with caplog.at_level(logging.WARNING):
        records = ResumePdfParser().parse(pdf_path)

    assert len(records) == 1
    assert records[0].canonical == {}
    assert "resume PDF has no usable candidate values" in records[0].warnings
    assert "contains no extractable text" in caplog.text

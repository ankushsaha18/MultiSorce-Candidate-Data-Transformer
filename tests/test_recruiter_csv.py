from __future__ import annotations

import logging

from candidate_transformer.sources.recruiter_csv import RecruiterCsvParser


def test_parse_recruiter_csv_returns_source_records(tmp_path):
    csv_path = tmp_path / "recruiter.csv"
    csv_path.write_text(
        "name,email,phone,current_company,title\n"
        "Ada Lovelace,ADA@Example.com,+14155552671,Analytical Engines,Engineer\n",
        encoding="utf-8",
    )

    records = RecruiterCsvParser().parse(csv_path)

    assert len(records) == 1
    record = records[0]
    assert record.source_type == "recruiter_csv"
    assert record.source_id == "recruiter.csv"
    assert record.record_id == "recruiter.csv:row_2"
    assert record.canonical == {
        "full_name": "Ada Lovelace",
        "emails": ["ADA@Example.com"],
        "phones": ["+14155552671"],
        "experience": [
            {
                "company": "Analytical Engines",
                "title": "Engineer",
                "start": None,
                "end": None,
                "summary": None,
            }
        ],
        "headline": "Engineer",
    }
    assert record.raw["email"] == "ADA@Example.com"
    assert record.warnings == []


def test_parse_recruiter_csv_logs_missing_columns(tmp_path, caplog):
    csv_path = tmp_path / "partial.csv"
    csv_path.write_text("name,email\nGrace Hopper,grace@example.com\n", encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        records = RecruiterCsvParser().parse(csv_path)

    assert len(records) == 1
    assert records[0].canonical["full_name"] == "Grace Hopper"
    assert records[0].canonical["emails"] == ["grace@example.com"]
    assert "missing expected column: phone" in caplog.text
    assert "missing expected column: current_company" in caplog.text
    assert "missing expected column: title" in caplog.text


def test_parse_recruiter_csv_handles_unrecognizable_file(tmp_path, caplog):
    csv_path = tmp_path / "unknown.csv"
    csv_path.write_text("foo,bar\none,two\n", encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        records = RecruiterCsvParser().parse(csv_path)

    assert records == []
    assert "has no recognizable candidate columns" in caplog.text


def test_parse_recruiter_csv_handles_empty_file(tmp_path, caplog):
    csv_path = tmp_path / "empty.csv"
    csv_path.write_text("", encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        records = RecruiterCsvParser().parse(csv_path)

    assert records == []
    assert "file is empty" in caplog.text


def test_parse_recruiter_csv_handles_missing_file(tmp_path, caplog):
    csv_path = tmp_path / "missing.csv"

    with caplog.at_level(logging.WARNING):
        records = RecruiterCsvParser().parse(csv_path)

    assert records == []
    assert "file does not exist" in caplog.text


def test_parse_recruiter_csv_handles_malformed_csv(tmp_path, caplog):
    csv_path = tmp_path / "malformed.csv"
    csv_path.write_bytes(b"\xff\xfe\x00")

    with caplog.at_level(logging.WARNING):
        records = RecruiterCsvParser().parse(csv_path)

    assert records == []
    assert "could not be decoded as text" in caplog.text


def test_parse_recruiter_csv_handles_unparseable_rows(tmp_path, caplog):
    csv_path = tmp_path / "unparseable.csv"
    csv_path.write_text('name,email\n"unclosed quote row\n', encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        records = RecruiterCsvParser().parse(csv_path)

    assert records == []


def test_parse_recruiter_csv_preserves_row_warnings_for_empty_candidate_row(tmp_path):
    csv_path = tmp_path / "blank_row.csv"
    csv_path.write_text(
        "name,email,phone,current_company,title\n"
        ",,,,\n",
        encoding="utf-8",
    )

    records = RecruiterCsvParser().parse(csv_path)

    assert len(records) == 1
    assert records[0].canonical == {}
    assert "missing email" in records[0].warnings
    assert "missing full_name" in records[0].warnings
    assert "row 2 has no usable candidate values" in records[0].warnings

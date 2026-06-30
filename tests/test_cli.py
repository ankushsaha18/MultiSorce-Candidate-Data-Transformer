from __future__ import annotations

import json

from candidate_transformer.app.cli import main


def test_cli_writes_projected_output_from_csv(tmp_path, capsys):
    csv_path = tmp_path / "recruiter.csv"
    csv_path.write_text(
        "name,email,phone,current_company,title\n"
        "Ada Lovelace,ada@example.com,415-555-2671,Analytical Engines,Engineer\n",
        encoding="utf-8",
    )
    config_path = tmp_path / "projection.json"
    config_path.write_text(
        json.dumps(
            {
                "fields": [
                    {"path": "name", "from": "full_name", "type": "string"},
                    {"path": "primary_email", "from": "emails[0]", "type": "string"},
                    {"path": "phone", "from": "phones[0]", "type": "string"},
                ],
                "include_confidence": True,
                "include_provenance": False,
                "on_missing": "null",
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "result.json"

    exit_code = main(
        [
            "--csv",
            str(csv_path),
            "--config",
            str(config_path),
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    output = json.loads(output_path.read_text(encoding="utf-8"))
    assert output["name"] == "Ada Lovelace"
    assert output["primary_email"] == "ada@example.com"
    assert output["phone"] == "+14155552671"
    assert output["confidence"]["name"] == 0.9
    summary = capsys.readouterr().out
    assert "Execution summary" in summary
    assert "status: success" in summary


def test_cli_handles_no_usable_records_without_crashing(tmp_path, capsys):
    config_path = tmp_path / "projection.json"
    config_path.write_text(
        json.dumps({"fields": [{"path": "name", "from": "full_name", "type": "string"}]}),
        encoding="utf-8",
    )
    output_path = tmp_path / "result.json"

    exit_code = main(
        [
            "--csv",
            str(tmp_path / "missing.csv"),
            "--config",
            str(config_path),
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 1
    output = json.loads(output_path.read_text(encoding="utf-8"))
    assert output["status"] == "failed"
    assert "No usable records" in output["errors"][0]["message"]
    assert "status: failed" in capsys.readouterr().out


def test_cli_fails_when_no_input_sources_are_provided(tmp_path, capsys):
    config_path = tmp_path / "projection.json"
    config_path.write_text(
        json.dumps({"fields": [{"path": "name", "from": "full_name", "type": "string"}]}),
        encoding="utf-8",
    )
    output_path = tmp_path / "result.json"

    exit_code = main(
        [
            "--config",
            str(config_path),
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 1
    output = json.loads(output_path.read_text(encoding="utf-8"))
    assert output["status"] == "failed"
    assert "No input sources provided" in output["errors"][0]["message"]
    assert "status: failed" in capsys.readouterr().out


def test_cli_merges_csv_and_resume_end_to_end(tmp_path, capsys):
    csv_path = tmp_path / "recruiter.csv"
    csv_path.write_text(
        "name,email,phone,current_company,title\n"
        "Ada Lovelace,ada@example.com,415-555-2671,Analytical Engines,Engineer\n",
        encoding="utf-8",
    )
    config_path = tmp_path / "projection.json"
    config_path.write_text(
        json.dumps(
            {
                "fields": [
                    {"path": "name", "from": "full_name", "type": "string"},
                    {"path": "skills", "from": "skills[].name", "type": "string[]"},
                ],
                "include_confidence": True,
                "include_provenance": True,
                "on_missing": "null",
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "result.json"

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ImportError:
        import pytest

        pytest.skip("reportlab is required for resume PDF CLI integration test")

    pdf_path = tmp_path / "resume.pdf"
    pdf = canvas.Canvas(str(pdf_path), pagesize=letter)
    _, height = letter
    for index, line in enumerate(
        [
            "Ada Lovelace",
            "Senior Backend Engineer",
            "ada@example.com | +1 415 555 2671",
            "Skills",
            "Python, SQL",
        ]
    ):
        pdf.drawString(72, height - 72 - (index * 16), line)
    pdf.save()

    exit_code = main(
        [
            "--csv",
            str(csv_path),
            "--resume",
            str(pdf_path),
            "--config",
            str(config_path),
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    output = json.loads(output_path.read_text(encoding="utf-8"))
    assert output["name"] == "Ada Lovelace"
    assert "Python" in output["skills"]
    assert "provenance" in output
    assert "status: success" in capsys.readouterr().out


def test_cli_handles_invalid_projection_config_without_crashing(tmp_path, capsys):
    csv_path = tmp_path / "recruiter.csv"
    csv_path.write_text(
        "name,email,phone,current_company,title\n"
        "Ada Lovelace,ada@example.com,415-555-2671,Analytical Engines,Engineer\n",
        encoding="utf-8",
    )
    config_path = tmp_path / "projection.json"
    config_path.write_text(
        json.dumps({"fields": [{"path": "name", "type": "bogus"}]}),
        encoding="utf-8",
    )
    output_path = tmp_path / "result.json"

    exit_code = main(
        [
            "--csv",
            str(csv_path),
            "--config",
            str(config_path),
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 1
    output = json.loads(output_path.read_text(encoding="utf-8"))
    assert output["status"] == "failed"
    assert "Projection failed" in output["errors"][0]["message"]
    assert "status: failed" in capsys.readouterr().out

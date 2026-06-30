"""Command-line interface for the candidate transformer."""

from __future__ import annotations

from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Sequence
import json
import logging
import sys

from candidate_transformer.config import configure_logging
from candidate_transformer.merge import merge_candidate_records
from candidate_transformer.projection import (
    ProjectionConfigError,
    load_projection_config,
    project_candidate,
)
from candidate_transformer.sources.recruiter_csv import RecruiterCsvParser
from candidate_transformer.sources.resume_pdf import ResumePdfParser
from candidate_transformer.validation import validate_projected_output

logger = logging.getLogger(__name__)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        configure_logging(args.log_config)
    except Exception as exc:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
        logger.warning("Could not configure logging from %s: %s", args.log_config, exc)

    try:
        summary = _run(args)
    except Exception as exc:
        logger.exception("Transformer run failed")
        _print_summary(
            {
                "status": "failed",
                "error": str(exc),
                "records_parsed": 0,
                "output": str(args.output),
            }
        )
        return 1

    _print_summary(summary)
    return 0 if summary["status"] == "success" else 1


def _build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Multi-source candidate data transformer")
    parser.add_argument("--csv", type=Path, help="Path to recruiter CSV input")
    parser.add_argument("--resume", type=Path, help="Path to resume PDF input")
    parser.add_argument("--config", type=Path, required=True, help="Path to projection JSON config")
    parser.add_argument("--output", type=Path, required=True, help="Path to output JSON file")
    parser.add_argument(
        "--log-config",
        type=Path,
        default=Path("configs/logging.yaml"),
        help="Path to logging YAML/JSON config",
    )
    return parser


def _run(args: Namespace) -> dict:
    source_records = []
    source_counts = {"recruiter_csv": 0, "resume_pdf": 0}

    if args.csv:
        logger.info("Parsing recruiter CSV: %s", args.csv)
        csv_records = RecruiterCsvParser().parse(args.csv)
        source_counts["recruiter_csv"] = len(csv_records)
        source_records.extend(csv_records)

    if args.resume:
        logger.info("Parsing resume PDF: %s", args.resume)
        resume_records = ResumePdfParser().parse(args.resume)
        source_counts["resume_pdf"] = len(resume_records)
        source_records.extend(resume_records)

    if not args.csv and not args.resume:
        return _write_error(args.output, "No input sources provided", source_counts)

    if not source_records:
        return _write_error(args.output, "No usable records parsed from inputs", source_counts)

    logger.info("Merging %d source record(s)", len(source_records))
    candidate = merge_candidate_records(source_records)

    logger.info("Loading projection config: %s", args.config)
    try:
        projection_config = load_projection_config(args.config)
        projected = project_candidate(candidate, projection_config)
    except ProjectionConfigError as exc:
        return _write_error(args.output, f"Projection failed: {exc}", source_counts)

    validation = validate_projected_output(projected, projection_config)
    if not validation.is_valid:
        errors = [error.model_dump() for error in validation.errors]
        logger.warning("Projected output validation failed: %s", errors)
        _write_json(
            args.output,
            {
                "status": "validation_failed",
                "errors": errors,
                "projected_output": projected,
            },
        )
        return {
            "status": "validation_failed",
            "records_parsed": len(source_records),
            "csv_records": source_counts["recruiter_csv"],
            "resume_records": source_counts["resume_pdf"],
            "validation_errors": len(errors),
            "output": str(args.output),
        }

    _write_json(args.output, projected)
    logger.info("Wrote projected output: %s", args.output)
    return {
        "status": "success",
        "records_parsed": len(source_records),
        "csv_records": source_counts["recruiter_csv"],
        "resume_records": source_counts["resume_pdf"],
        "candidate_id": candidate.candidate_id,
        "overall_confidence": candidate.overall_confidence,
        "output": str(args.output),
    }


def _write_error(output_path: Path, message: str, source_counts: dict[str, int]) -> dict:
    logger.warning(message)
    payload = {
        "status": "failed",
        "errors": [{"message": message}],
    }
    _write_json(output_path, payload)
    return {
        "status": "failed",
        "error": message,
        "records_parsed": sum(source_counts.values()),
        "csv_records": source_counts["recruiter_csv"],
        "resume_records": source_counts["resume_pdf"],
        "output": str(output_path),
    }


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _print_summary(summary: dict) -> None:
    print("Execution summary")
    print(f"  status: {summary.get('status')}")
    print(f"  records_parsed: {summary.get('records_parsed', 0)}")
    if "csv_records" in summary:
        print(f"  csv_records: {summary['csv_records']}")
    if "resume_records" in summary:
        print(f"  resume_records: {summary['resume_records']}")
    if "candidate_id" in summary:
        print(f"  candidate_id: {summary['candidate_id']}")
    if "overall_confidence" in summary:
        print(f"  overall_confidence: {summary['overall_confidence']}")
    if "validation_errors" in summary:
        print(f"  validation_errors: {summary['validation_errors']}")
    if "error" in summary:
        print(f"  error: {summary['error']}")
    print(f"  output: {summary.get('output')}")


if __name__ == "__main__":
    sys.exit(main())

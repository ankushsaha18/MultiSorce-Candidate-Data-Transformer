"""Recruiter CSV source adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import logging

import pandas as pd

from candidate_transformer.models import SourceRecord

logger = logging.getLogger(__name__)


class RecruiterCsvParser:
    """Parse recruiter CSV exports into canonical intermediate records."""

    source_type = "recruiter_csv"

    COLUMN_ALIASES: dict[str, str] = {
        "name": "full_name",
        "full_name": "full_name",
        "candidate_name": "full_name",
        "email": "emails",
        "emails": "emails",
        "phone": "phones",
        "phones": "phones",
        "current_company": "current_company",
        "company": "current_company",
        "title": "title",
        "current_title": "title",
    }

    EXPECTED_COLUMNS = frozenset(
        {"name", "email", "phone", "current_company", "title"}
    )

    def parse(self, path: str | Path) -> list[SourceRecord]:
        csv_path = Path(path)
        source_id = csv_path.name

        dataframe = self._read_csv(csv_path)
        if dataframe is None or dataframe.empty:
            return []

        normalized_columns = {
            column: self._normalize_column_name(str(column))
            for column in dataframe.columns
        }
        canonical_columns = {
            original: self.COLUMN_ALIASES[normalized]
            for original, normalized in normalized_columns.items()
            if normalized in self.COLUMN_ALIASES
        }

        missing_columns = sorted(self.EXPECTED_COLUMNS - set(normalized_columns.values()))
        for column in missing_columns:
            logger.warning("Recruiter CSV %s is missing expected column: %s", csv_path, column)

        if not canonical_columns:
            logger.warning("Recruiter CSV %s has no recognizable candidate columns", csv_path)
            return []

        records: list[SourceRecord] = []
        for row_number, (_, row) in enumerate(dataframe.iterrows(), start=2):
            raw_row = self._row_to_raw_dict(row)
            canonical, row_warnings = self._row_to_canonical(row, canonical_columns)
            if not canonical:
                warning = f"row {row_number} has no usable candidate values"
                row_warnings.append(warning)
                logger.warning("Recruiter CSV %s %s", csv_path, warning)

            records.append(
                SourceRecord(
                    source_type=self.source_type,
                    source_id=source_id,
                    record_id=f"{source_id}:row_{row_number}",
                    canonical=canonical,
                    raw=raw_row,
                    warnings=row_warnings,
                )
            )

        return records

    def _read_csv(self, path: Path) -> pd.DataFrame | None:
        if not path.exists():
            logger.warning("Recruiter CSV file does not exist: %s", path)
            return None

        try:
            return pd.read_csv(
                path,
                dtype="string",
                keep_default_na=False,
                engine="python",
                on_bad_lines="skip",
            )
        except pd.errors.EmptyDataError:
            logger.warning("Recruiter CSV file is empty: %s", path)
        except pd.errors.ParserError as exc:
            logger.warning("Recruiter CSV file is malformed and could not be parsed: %s: %s", path, exc)
        except UnicodeDecodeError as exc:
            logger.warning("Recruiter CSV file could not be decoded as text: %s: %s", path, exc)
        except OSError as exc:
            logger.warning("Recruiter CSV file could not be read: %s: %s", path, exc)
        return None

    def _row_to_canonical(
        self,
        row: pd.Series,
        canonical_columns: dict[Any, str],
    ) -> tuple[dict[str, Any], list[str]]:
        canonical: dict[str, Any] = {}
        warnings: list[str] = []

        full_name = self._first_scalar(row, canonical_columns, "full_name")
        if full_name:
            canonical["full_name"] = full_name

        email = self._first_scalar(row, canonical_columns, "emails")
        if email:
            canonical["emails"] = [email]

        phone = self._first_scalar(row, canonical_columns, "phones")
        if phone:
            canonical["phones"] = [phone]

        company = self._first_scalar(row, canonical_columns, "current_company")
        title = self._first_scalar(row, canonical_columns, "title")
        if company or title:
            canonical["experience"] = [
                {
                    "company": company,
                    "title": title,
                    "start": None,
                    "end": None,
                    "summary": None,
                }
            ]
            if title:
                canonical["headline"] = title

        if not email:
            warnings.append("missing email")
        if not full_name:
            warnings.append("missing full_name")

        return canonical, warnings

    def _first_scalar(
        self,
        row: pd.Series,
        canonical_columns: dict[Any, str],
        canonical_field: str,
    ) -> str | None:
        for original_column, mapped_field in canonical_columns.items():
            if mapped_field != canonical_field:
                continue
            value = self._clean_value(row.get(original_column))
            if value:
                return value
        return None

    def _row_to_raw_dict(self, row: pd.Series) -> dict[str, Any]:
        raw: dict[str, Any] = {}
        for key, value in row.to_dict().items():
            raw[str(key)] = self._clean_value(value)
        return raw

    def _clean_value(self, value: Any) -> str | None:
        if value is None or pd.isna(value):
            return None
        text = str(value).strip()
        return text or None

    def _normalize_column_name(self, column: str) -> str:
        return column.strip().lower().replace(" ", "_").replace("-", "_")


def parse_recruiter_csv(path: str | Path) -> list[SourceRecord]:
    """Convenience function for parsing a recruiter CSV file."""
    return RecruiterCsvParser().parse(path)

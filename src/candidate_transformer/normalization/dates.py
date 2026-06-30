"""Date normalization helpers."""

from __future__ import annotations

from datetime import datetime
import re

_YEAR_MONTH_RE = re.compile(r"^(?P<year>\d{4})-(?P<month>0[1-9]|1[0-2])$")
_YEAR_RE = re.compile(r"^(?P<year>\d{4})$")
_MONTH_YEAR_RE = re.compile(
    r"^(?P<month>jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?)\.?\s+(?P<year>\d{4})$",
    re.IGNORECASE,
)
_NUMERIC_MONTH_YEAR_RE = re.compile(r"^(?P<month>0?[1-9]|1[0-2])[/.-](?P<year>\d{4})$")
_YEAR_NUMERIC_MONTH_RE = re.compile(r"^(?P<year>\d{4})[/.-](?P<month>0?[1-9]|1[0-2])$")

_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def normalize_date_to_year_month(value: str | None, default_month: int = 1) -> str | None:
    """Normalize common resume date formats to ``YYYY-MM``.

    Returns ``None`` for empty, unsupported, or invalid dates. Year-only values
    use ``default_month`` so the result still fits the canonical ``YYYY-MM``
    shape deterministically.
    """
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    lowered = text.lower()
    if lowered in {"present", "current", "now"}:
        return None

    match = _YEAR_MONTH_RE.fullmatch(text)
    if match:
        return _format_year_month(int(match.group("year")), int(match.group("month")))

    match = _MONTH_YEAR_RE.fullmatch(text)
    if match:
        month_key = match.group("month").lower().rstrip(".")
        return _format_year_month(int(match.group("year")), _MONTHS[month_key])

    match = _NUMERIC_MONTH_YEAR_RE.fullmatch(text)
    if match:
        return _format_year_month(int(match.group("year")), int(match.group("month")))

    match = _YEAR_NUMERIC_MONTH_RE.fullmatch(text)
    if match:
        return _format_year_month(int(match.group("year")), int(match.group("month")))

    match = _YEAR_RE.fullmatch(text)
    if match:
        return _format_year_month(int(match.group("year")), default_month)

    return None


def normalize_date_range(
    value: str | None,
    default_start_month: int = 1,
    default_end_month: int = 12,
) -> tuple[str | None, str | None]:
    """Normalize a human date range into ``(start, end)`` year-month values."""
    if value is None:
        return None, None

    parts = re.split(r"\s*(?:-|–|—|to)\s*", str(value).strip(), maxsplit=1, flags=re.IGNORECASE)
    if len(parts) == 1:
        return normalize_date_to_year_month(parts[0], default_month=default_start_month), None

    start = normalize_date_to_year_month(parts[0], default_month=default_start_month)
    end_text = parts[1].strip().lower()
    end = None if end_text in {"present", "current", "now"} else normalize_date_to_year_month(parts[1], default_month=default_end_month)
    return start, end


def is_valid_year_month(value: str) -> bool:
    """Return whether a value is a valid canonical ``YYYY-MM`` date."""
    normalized = normalize_date_to_year_month(value)
    return normalized == value


def _format_year_month(year: int, month: int) -> str | None:
    try:
        datetime(year=year, month=month, day=1)
    except ValueError:
        return None
    return f"{year:04d}-{month:02d}"

"""Phone number normalization helpers."""

from __future__ import annotations

import phonenumbers


def normalize_phone_to_e164(value: str | None, default_region: str | None = "US") -> str | None:
    """Normalize a phone number to E.164 format.

    Returns ``None`` when the input is empty, malformed, or not a valid phone
    number for the provided region. ``default_region`` should be an ISO-3166
    alpha-2 country code and is only used for numbers without an international
    prefix.
    """
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    region = default_region.upper() if default_region else None
    try:
        parsed = phonenumbers.parse(text, region)
    except phonenumbers.NumberParseException:
        return None

    if not phonenumbers.is_valid_number(parsed):
        return None
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def normalize_phones_to_e164(
    values: list[str] | tuple[str, ...],
    default_region: str | None = "US",
) -> list[str]:
    """Normalize and de-duplicate phone numbers while preserving first-seen order."""
    normalized: list[str] = []
    seen: set[str] = set()

    for value in values:
        phone = normalize_phone_to_e164(value, default_region=default_region)
        if phone and phone not in seen:
            normalized.append(phone)
            seen.add(phone)

    return normalized

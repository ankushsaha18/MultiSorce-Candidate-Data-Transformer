"""Backward-compatible phone normalization exports."""

from candidate_transformer.normalization.phone import (
    normalize_phone_to_e164,
    normalize_phones_to_e164,
)

__all__ = ["normalize_phone_to_e164", "normalize_phones_to_e164"]

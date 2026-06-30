"""Deterministic merge and conflict resolution helpers."""

from candidate_transformer.merge.resolver import (
    merge_candidate_records,
    merge_two_candidate_records,
)

__all__ = ["merge_candidate_records", "merge_two_candidate_records"]

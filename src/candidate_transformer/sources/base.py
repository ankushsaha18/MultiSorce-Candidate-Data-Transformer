"""Base source parser interfaces."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from candidate_transformer.models import SourceRecord


class SourceParser(Protocol):
    """Common protocol for source parsers."""

    source_type: str

    def parse(self, path: str | Path) -> list[SourceRecord]:
        """Parse a source file into intermediate source records."""

from __future__ import annotations

from candidate_transformer.confidence import (
    score_merged_list,
    score_overall_from_provenance,
    score_source_field,
)
from candidate_transformer.models import Provenance


def test_score_source_field_uses_fixed_source_rules():
    assert score_source_field("resume_pdf") == 0.95
    assert score_source_field("recruiter_csv") == 0.90
    assert score_source_field("unknown") == 0.50


def test_score_merged_list_averages_contributing_confidences():
    assert score_merged_list([0.95, 0.90]) == 0.925
    assert score_merged_list([0.95]) == 0.95
    assert score_merged_list([]) == 0.0


def test_score_overall_from_provenance_averages_populated_selected_fields():
    provenance = [
        Provenance(
            field="full_name",
            value="Ada Lovelace",
            source="resume:document",
            source_type="resume_pdf",
            method="merge:full_name",
            confidence=0.95,
            selected=True,
        ),
        Provenance(
            field="headline",
            value="Engineer",
            source="csv:row_2",
            source_type="recruiter_csv",
            method="merge:headline",
            confidence=0.90,
            selected=True,
        ),
        Provenance(
            field="headline",
            value="Old Engineer",
            source="csv:row_3",
            source_type="recruiter_csv",
            method="merge:headline",
            confidence=0.90,
            selected=False,
        ),
        Provenance(
            field="empty",
            value=None,
            source="csv:row_2",
            source_type="recruiter_csv",
            method="merge:empty",
            confidence=0.90,
            selected=True,
        ),
    ]

    assert score_overall_from_provenance(provenance) == 0.925

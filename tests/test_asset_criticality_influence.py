"""Controlled I-27 checks for the documented criticality context term."""
from __future__ import annotations

import pytest

from analytics.fusion.evidence_fusion import FusionInputs, calculate_priority_components
from backend.models.ruleset import DEFAULT_AUTHORITATIVE_RULESET_V1


def _score(criticality: str, *, signals: int = 2, zscore: float = 1.5, persistence: float = 0.5):
    return calculate_priority_components(
        FusionInputs(
            signal_count=signals,
            max_peer_zscore=zscore,
            persistence_ratio=persistence,
            asset_criticality_tier=criticality,
            data_quality_score=1.0,
        ),
        ruleset=DEFAULT_AUTHORITATIVE_RULESET_V1,
    )[0]


def test_equal_evidence_criticality_changes_only_the_context_component():
    critical = _score("CRITICAL")
    low = _score("LOW")

    # 0.15 fusion weight × (1.00 critical - 0.25 low).
    assert critical - low == pytest.approx(0.1125)


def test_strong_low_criticality_evidence_outranks_weak_high_criticality_evidence():
    strong_low = _score("LOW", signals=3, zscore=3.0, persistence=1.0)
    weak_critical = _score("CRITICAL", signals=0, zscore=0.0, persistence=0.0)

    assert strong_low > weak_critical


def test_removing_or_perturbing_criticality_weight_has_the_expected_effect_only():
    no_criticality = DEFAULT_AUTHORITATIVE_RULESET_V1.fusion_weights.to_dict()
    no_criticality["asset_criticality_weight"] = 0.0
    high_criticality = DEFAULT_AUTHORITATIVE_RULESET_V1.fusion_weights.to_dict()
    high_criticality["asset_criticality_weight"] = 0.30

    same_evidence = dict(
        signal_count=2,
        max_peer_zscore=1.5,
        persistence_ratio=0.5,
        data_quality_score=1.0,
    )
    removed_critical, _ = calculate_priority_components(
        FusionInputs(asset_criticality_tier="CRITICAL", **same_evidence), no_criticality
    )
    removed_low, _ = calculate_priority_components(
        FusionInputs(asset_criticality_tier="LOW", **same_evidence), no_criticality
    )
    perturbed_critical, _ = calculate_priority_components(
        FusionInputs(asset_criticality_tier="CRITICAL", **same_evidence), high_criticality
    )
    perturbed_low, _ = calculate_priority_components(
        FusionInputs(asset_criticality_tier="LOW", **same_evidence), high_criticality
    )

    assert removed_critical == removed_low
    assert perturbed_critical - perturbed_low == pytest.approx(0.225)

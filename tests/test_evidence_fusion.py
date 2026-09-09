"""
Unit tests for Evidence Fusion & Priority Scoring (§10.5).
"""
from analytics.fusion.evidence_fusion import FusionInputs, calculate_priority_components


def test_priority_components_calculation():
    inputs = FusionInputs(
        signal_count=3,
        max_peer_zscore=3.0,
        persistence_ratio=1.0,
        asset_criticality_tier="CRITICAL",
        data_quality_score=1.0,  # Uncertainty = 0.0
    )
    score, comps = calculate_priority_components(inputs)

    # 0.30*1.0 + 0.25*1.0 + 0.20*1.0 + 0.15*1.0 - 0.10*0.0 = 0.90
    assert abs(score - 0.90) < 1e-3
    assert comps["signal_strength"] == 1.0
    assert comps["peer_deviation"] == 1.0
    assert comps["persistence"] == 1.0
    assert comps["asset_criticality"] == 1.0
    assert comps["data_uncertainty"] == 0.0


def test_uncertainty_penalty_reduces_score():
    inputs_high_dq = FusionInputs(
        signal_count=2,
        max_peer_zscore=2.0,
        persistence_ratio=0.5,
        asset_criticality_tier="HIGH",
        data_quality_score=0.95,
    )
    inputs_low_dq = FusionInputs(
        signal_count=2,
        max_peer_zscore=2.0,
        persistence_ratio=0.5,
        asset_criticality_tier="HIGH",
        data_quality_score=0.40,
    )

    score_high, _ = calculate_priority_components(inputs_high_dq)
    score_low, _ = calculate_priority_components(inputs_low_dq)

    assert score_high > score_low

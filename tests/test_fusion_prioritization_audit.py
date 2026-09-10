"""
Comprehensive Audit & Boundary Tests for Evidence Fusion & Prioritization (SRS §10.5).

Verifies:
1. All five fusion components: T, D, B, C, A
2. Normalization & clamping to [0.0, 1.0]
3. Weights sourced directly from versioned AnalyticalRuleset (w_T, w_D, w_B, w_C, w_A)
4. Priority tier calculation occurs strictly after fusion
5. Explicit thresholds (HIGH >= 0.75, MEDIUM >= 0.50)
6. Preservation of component-level scores and weights
7. Complete mathematical reconstructability from finding artifacts
8. Deterministic boundary conditions:
   - Score exactly at threshold (0.75, 0.50)
   - Score just below threshold (0.7499, 0.4999)
   - Score just above threshold (0.7501, 0.5001)
   - Missing evidence (independent_signals < 2)
   - Low DQ (DQ < 0.60)
9. Repeatable determinism: same input + same ruleset -> identical result
"""
import pytest
from uuid import uuid4
from datetime import datetime, timezone

from analytics.fusion.evidence_fusion import (
    FusionInputs,
    EvidenceFusionEngine,
    calculate_priority_components,
    compute_priority_tier,
    reconstruct_finding_fusion,
    determine_evidence_sufficiency_state,
)
from backend.models.canonical import (
    Finding,
    FindingType,
    EvidenceSufficiencyState,
    ExpectationBasis,
    DataQualityScore,
    DataQualityComponents,
    EvidenceRef,
)
from backend.models.ruleset import (
    DEFAULT_AUTHORITATIVE_RULESET_V1,
    AnalyticalRuleset,
    FusionWeights,
    PriorityThresholds,
)
from analytics.data_quality.quality_score import DataQualityResult, DataQualityComponents as DQCompScore


# =====================================================================
# 1. Five Fusion Components & Normalization Verification (T, D, B, C, A)
# =====================================================================

def test_five_fusion_components_and_normalization():
    """
    Verifies that all five components (T, D, B, C, A) are computed,
    strictly normalized into [0.0, 1.0], and exposed in the components dictionary.
    """
    # Test typical values
    inputs = FusionInputs(
        signal_count=3,
        max_peer_zscore=3.0,
        persistence_ratio=0.8,
        asset_criticality_tier="CRITICAL",
        data_quality_score=0.9,
    )
    score, comps = calculate_priority_components(inputs)

    # 1. T (Signal Strength): 3 / 3 = 1.0
    assert comps["T"] == 1.0
    assert comps["signal_strength"] == 1.0

    # 2. D (Peer Deviation): 3.0 / 3.0 = 1.0
    assert comps["D"] == 1.0
    assert comps["peer_deviation"] == 1.0

    # 3. B (Persistence): 0.8
    assert comps["B"] == 0.8
    assert comps["persistence"] == 0.8

    # 4. C (Asset Criticality): CRITICAL -> 1.0
    assert comps["C"] == 1.0
    assert comps["asset_criticality"] == 1.0

    # 5. A (Data Uncertainty): 1.0 - 0.9 = 0.1
    assert comps["A"] == 0.1
    assert comps["data_uncertainty"] == 0.1

    # Raw score calculation:
    # 0.30*1.0 + 0.25*1.0 + 0.20*0.8 + 0.15*1.0 + (-0.10)*0.1
    # = 0.30 + 0.25 + 0.16 + 0.15 - 0.01 = 0.85
    expected_raw = 0.85
    assert comps["raw_score"] == pytest.approx(expected_raw, abs=1e-4)
    assert score == pytest.approx(expected_raw, abs=1e-4)
    assert comps["fused_score"] == pytest.approx(expected_raw, abs=1e-4)


def test_normalization_caps_and_clamping():
    """
    Verifies that values exceeding caps are correctly clamped to 1.0,
    and negative/sub-zero values are clamped to 0.0.
    """
    # Over-cap inputs
    inputs_high = FusionInputs(
        signal_count=10,  # Cap is 3 -> 1.0
        max_peer_zscore=8.5,  # Cap is 3.0 -> 1.0
        persistence_ratio=1.5,  # Clamped to 1.0
        asset_criticality_tier="CRITICAL",  # 1.0
        data_quality_score=0.0,  # Uncertainty = 1.0
    )
    score_high, comps_high = calculate_priority_components(inputs_high)
    assert comps_high["T"] == 1.0
    assert comps_high["D"] == 1.0
    assert comps_high["B"] == 1.0
    assert comps_high["C"] == 1.0
    assert comps_high["A"] == 1.0
    # Raw = 0.30 + 0.25 + 0.20 + 0.15 - 0.10 = 0.80
    assert score_high == pytest.approx(0.80, abs=1e-4)

    # Zero/minimal inputs
    inputs_low = FusionInputs(
        signal_count=0,
        max_peer_zscore=0.0,
        persistence_ratio=-0.5,  # Clamped to 0.0
        asset_criticality_tier="LOW",  # 0.25
        data_quality_score=1.0,  # Uncertainty = 0.0
    )
    score_low, comps_low = calculate_priority_components(inputs_low)
    assert comps_low["T"] == 0.0
    assert comps_low["D"] == 0.0
    assert comps_low["B"] == 0.0
    assert comps_low["C"] == 0.25
    assert comps_low["A"] == 0.0
    # Raw = 0.15 * 0.25 = 0.0375
    assert score_low == pytest.approx(0.0375, abs=1e-4)


def test_criticality_tier_normalization_mapping():
    """
    Verifies that all asset criticality tiers map to their exact normalized values:
    CRITICAL -> 1.0, HIGH -> 0.75, MEDIUM -> 0.50, LOW -> 0.25
    """
    tiers = {
        "CRITICAL": 1.0,
        "critical": 1.0,
        "HIGH": 0.75,
        "high": 0.75,
        "MEDIUM": 0.50,
        "medium": 0.50,
        "LOW": 0.25,
        "low": 0.25,
        "UNKNOWN": 0.50,  # default fallback
    }
    for tier_str, expected_norm in tiers.items():
        inp = FusionInputs(
            signal_count=0,
            max_peer_zscore=0.0,
            persistence_ratio=0.0,
            asset_criticality_tier=tier_str,
            data_quality_score=1.0,
        )
        _, comps = calculate_priority_components(inp)
        assert comps["C"] == expected_norm


# =====================================================================
# 2. Weights Sourced From Versioned Ruleset
# =====================================================================

def test_fusion_weights_from_authoritative_ruleset():
    """
    Verifies that default calculation uses authoritative V1 ruleset weights.
    """
    inp = FusionInputs(
        signal_count=1,
        max_peer_zscore=1.0,
        persistence_ratio=0.5,
        asset_criticality_tier="HIGH",
        data_quality_score=0.8,
    )
    score, comps = calculate_priority_components(inp, ruleset=DEFAULT_AUTHORITATIVE_RULESET_V1)

    assert comps["w_T"] == 0.30
    assert comps["w_D"] == 0.25
    assert comps["w_B"] == 0.20
    assert comps["w_C"] == 0.15
    assert comps["w_A"] == -0.10


def test_custom_versioned_ruleset_drives_fusion():
    """
    Verifies that a custom versioned ruleset with modified weights alters the calculation as expected.
    """
    custom_weights = FusionWeights(
        signal_strength_weight=0.50,
        peer_deviation_weight=0.10,
        persistence_weight=0.20,
        asset_criticality_weight=0.10,
        data_uncertainty_weight=-0.20,
        signal_strength_cap=2,
        peer_deviation_zscore_cap=2.0,
    )
    custom_ruleset = AnalyticalRuleset(
        ruleset_id=uuid4(),
        version="V2_CUSTOM",
        name="Custom Fusion Ruleset",
        is_active=True,
        effective_timestamp=datetime.now(timezone.utc),
        author="Audit Team",
        rationale="Modified weights for testing",
        fusion_weights=custom_weights,
        thresholds=PriorityThresholds(
            high_priority_score_threshold=0.80,
            medium_priority_score_threshold=0.60,
        ),
    )

    inp = FusionInputs(
        signal_count=2,  # 2/2 = 1.0
        max_peer_zscore=2.0,  # 2/2 = 1.0
        persistence_ratio=1.0,  # 1.0
        asset_criticality_tier="CRITICAL",  # 1.0
        data_quality_score=0.5,  # 1 - 0.5 = 0.5
    )
    score, comps = calculate_priority_components(inp, ruleset=custom_ruleset)

    assert comps["w_T"] == 0.50
    assert comps["w_D"] == 0.10
    assert comps["w_B"] == 0.20
    assert comps["w_C"] == 0.10
    assert comps["w_A"] == -0.20

    # Expected raw: 0.50*1.0 + 0.10*1.0 + 0.20*1.0 + 0.10*1.0 + (-0.20)*0.5
    # = 0.50 + 0.10 + 0.20 + 0.10 - 0.10 = 0.80
    assert score == pytest.approx(0.80, abs=1e-4)


# =====================================================================
# 3. Post-Fusion Prioritization & Explicit Threshold Boundary Tests
# =====================================================================

def test_priority_tier_boundary_exact_threshold():
    """
    Test score exactly at threshold:
    - score == 0.75 with sufficient signals and DQ -> 'HIGH'
    - score == 0.50 with sufficient signals and DQ -> 'MEDIUM'
    """
    # 0.75 exact
    tier_high, gating_high = compute_priority_tier(
        priority_score=0.75,
        independent_signals_count=2,
        data_quality_score=0.80,
    )
    assert tier_high == "HIGH"
    assert gating_high["high_priority_gating_passed"] is True
    assert gating_high["high_priority_threshold"] == 0.75

    # 0.50 exact
    tier_med, gating_med = compute_priority_tier(
        priority_score=0.50,
        independent_signals_count=2,
        data_quality_score=0.80,
    )
    assert tier_med == "MEDIUM"
    assert gating_med["medium_priority_threshold"] == 0.50


def test_priority_tier_boundary_just_below_threshold():
    """
    Test score just below threshold:
    - score == 0.7499 -> 'MEDIUM'
    - score == 0.4999 -> 'LOW'
    """
    tier_just_below_high, gating_1 = compute_priority_tier(
        priority_score=0.7499,
        independent_signals_count=3,
        data_quality_score=0.90,
    )
    assert tier_just_below_high == "MEDIUM"
    assert gating_1["high_priority_gating_passed"] is False

    tier_just_below_med, gating_2 = compute_priority_tier(
        priority_score=0.4999,
        independent_signals_count=2,
        data_quality_score=0.90,
    )
    assert tier_just_below_med == "LOW"


def test_priority_tier_boundary_just_above_threshold():
    """
    Test score just above threshold:
    - score == 0.7501 -> 'HIGH'
    - score == 0.5001 -> 'MEDIUM'
    """
    tier_just_above_high, gating_1 = compute_priority_tier(
        priority_score=0.7501,
        independent_signals_count=2,
        data_quality_score=0.85,
    )
    assert tier_just_above_high == "HIGH"
    assert gating_1["high_priority_gating_passed"] is True

    tier_just_above_med, gating_2 = compute_priority_tier(
        priority_score=0.5001,
        independent_signals_count=2,
        data_quality_score=0.85,
    )
    assert tier_just_above_med == "MEDIUM"


def test_priority_tier_gating_missing_evidence():
    """
    Test that even if priority score is very high (e.g. 0.90),
    if independent_signals < 2, the finding is gated down from HIGH to MEDIUM.
    """
    tier, gating = compute_priority_tier(
        priority_score=0.90,
        independent_signals_count=1,  # Missing corroborating evidence
        data_quality_score=0.95,
    )
    assert tier == "MEDIUM"
    assert gating["high_priority_gating_passed"] is False
    assert gating["observed_independent_signals"] == 1
    assert gating["min_independent_signals"] == 2


def test_priority_tier_gating_low_dq():
    """
    Test that even if priority score is high (e.g. 0.85) and signals >= 2:
    - if data_quality < 0.60, it cannot be promoted to HIGH (gated to MEDIUM)
    - if evidence_state is NOT_ASSESSABLE, it cannot be HIGH
    """
    tier_low_dq, gating_dq = compute_priority_tier(
        priority_score=0.85,
        independent_signals_count=3,
        data_quality_score=0.55,  # Low DQ (< 0.60)
        evidence_state=EvidenceSufficiencyState.WEAKLY_SUPPORTED,
    )
    assert tier_low_dq == "MEDIUM"
    assert gating_dq["high_priority_gating_passed"] is False
    assert gating_dq["observed_data_quality"] == 0.55
    assert gating_dq["min_data_quality"] == 0.60

    tier_not_assessable, gating_na = compute_priority_tier(
        priority_score=0.85,
        independent_signals_count=3,
        data_quality_score=0.85,
        evidence_state=EvidenceSufficiencyState.NOT_ASSESSABLE,
    )
    assert tier_not_assessable == "MEDIUM"
    assert gating_na["high_priority_gating_passed"] is False


# =====================================================================
# 4. Mathematical Reconstruction & Full Traceability Verification
# =====================================================================

def test_finding_fusion_reconstructability():
    """
    Verifies that a Finding object exposes all components, weights, thresholds,
    and supporting evidence to allow exact mathematical reconstruction without loss.
    """
    inputs = FusionInputs(
        signal_count=3,
        max_peer_zscore=2.5,
        persistence_ratio=0.75,
        asset_criticality_tier="HIGH",
        data_quality_score=0.85,
    )
    score, comps = calculate_priority_components(inputs)

    finding = Finding(
        finding_id=uuid4(),
        cse_id=uuid4(),
        reporting_period_id=uuid4(),
        finding_type=FindingType.FAST_CLOSURE,
        priority_score=round(score, 4),
        priority_components=comps,
        evidentiary_confidence=0.88,
        data_quality_status=DataQualityScore(
            dataset_version_id=uuid4(),
            score=0.85,
            components=DataQualityComponents(
                completeness_ratio=0.9,
                consistency_ratio=0.9,
                coverage_ratio=0.9,
                sample_sufficiency_ratio=0.8,
            ),
            ruleset_version="V1",
            computed_at=datetime.now(timezone.utc),
        ),
        evidence_state=EvidenceSufficiencyState.SUPPORTED,
        expectation_basis=ExpectationBasis.STATISTICAL_BASELINE,
        expected_behavior="Expected ~25m closure duration",
        observed_behavior="Observed 3 cases closed under 5m",
        supporting_signals=[
            "3 alerts closed below peer baseline",
            "Peer deviation |z| = 2.5",
        ],
        contradicting_signals=[],
        peer_context="Peer median: 25.0m",
        temporal_context="Concentrated in morning triage",
        evidence_refs=[
            EvidenceRef(entity_type="Alert", entity_id=uuid4(), source_record_ref="AL-1"),
            EvidenceRef(entity_type="Alert", entity_id=uuid4(), source_record_ref="AL-2"),
        ],
        analytical_method="Peer MAD",
        ruleset_version="V1",
        dataset_version_id=uuid4(),
        analysis_run_id=uuid4(),
        created_at=datetime.now(timezone.utc),
    )

    reconstruction = reconstruct_finding_fusion(finding, DEFAULT_AUTHORITATIVE_RULESET_V1)

    assert reconstruction["is_mathematically_exact"] is True
    assert reconstruction["reconstructed_fused_score"] == finding.priority_score
    assert reconstruction["components"]["T"] == comps["T"]
    assert reconstruction["components"]["D"] == comps["D"]
    assert reconstruction["components"]["B"] == comps["B"]
    assert reconstruction["components"]["C"] == comps["C"]
    assert reconstruction["components"]["A"] == comps["A"]
    assert reconstruction["weights"]["w_T"] == 0.30
    assert reconstruction["weights"]["w_D"] == 0.25
    assert reconstruction["weights"]["w_B"] == 0.20
    assert reconstruction["weights"]["w_C"] == 0.15
    assert reconstruction["weights"]["w_A"] == -0.10
    assert reconstruction["priority_label"] in ["HIGH", "MEDIUM", "LOW"]
    assert reconstruction["evidence_record_count"] == 2


# =====================================================================
# 5. Deterministic Guarantee: Same Input + Same Ruleset = Same Result
# =====================================================================

def test_fusion_prioritization_strict_determinism():
    """
    SUCCESS CONDITION TEST:
    Verifies that running fusion and prioritization 100 times with identical inputs
    and ruleset produces 100% identical bit-for-bit results.
    """
    inp = FusionInputs(
        signal_count=2,
        max_peer_zscore=2.1234,
        persistence_ratio=0.6789,
        asset_criticality_tier="CRITICAL",
        data_quality_score=0.8123,
    )

    initial_score, initial_comps = calculate_priority_components(inp, ruleset=DEFAULT_AUTHORITATIVE_RULESET_V1)
    initial_tier, initial_gating = compute_priority_tier(
        priority_score=initial_score,
        independent_signals_count=inp.signal_count,
        data_quality_score=inp.data_quality_score,
        thresholds=DEFAULT_AUTHORITATIVE_RULESET_V1.thresholds,
    )

    for _ in range(100):
        iter_score, iter_comps = calculate_priority_components(inp, ruleset=DEFAULT_AUTHORITATIVE_RULESET_V1)
        iter_tier, iter_gating = compute_priority_tier(
            priority_score=iter_score,
            independent_signals_count=inp.signal_count,
            data_quality_score=inp.data_quality_score,
            thresholds=DEFAULT_AUTHORITATIVE_RULESET_V1.thresholds,
        )

        assert iter_score == initial_score
        assert iter_comps == initial_comps
        assert iter_tier == initial_tier
        assert iter_gating == initial_gating

"""
INNOVATION PHASE 5: SUPERVISORY DECISION STABILITY ANALYSIS — Tests
Tests deterministic behavior, normalization, overlap calculations,
threshold crossings, and read-only non-mutation properties.
"""
import copy
from datetime import datetime, timezone
from uuid import uuid4

from analytics.evaluation.stability import (
    compute_spearman,
    generate_perturbations,
    StabilityAnalyzer,
)
from backend.models.canonical import (
    Finding,
    FindingType,
    EvidenceSufficiencyState,
    DataQualityScore,
    DataQualityComponents,
    ExpectationBasis,
)


def _make_finding(
    priority: float,
    components: dict[str, float],
    cse_id=None,
    finding_type=FindingType.FAST_CLOSURE,
) -> Finding:
    now = datetime.now(timezone.utc)
    return Finding(
        finding_id=uuid4(),
        cse_id=cse_id or uuid4(),
        reporting_period_id=uuid4(),
        finding_type=finding_type,
        priority_score=priority,
        priority_components=components,
        evidentiary_confidence=0.9,
        data_quality_status=DataQualityScore(
            dataset_version_id=uuid4(), score=0.95,
            components=DataQualityComponents(
                completeness_ratio=0.95, consistency_ratio=0.95,
                coverage_ratio=0.95, sample_sufficiency_ratio=0.95,
            ),
            ruleset_version="V1", computed_at=now,
        ),
        expectation_basis=ExpectationBasis.STATISTICAL_BASELINE,
        expected_behavior="Expected",
        observed_behavior="Observed",
        supporting_signals=[],
        evidence_refs=[],
        evidence_state=EvidenceSufficiencyState.SUPPORTED,
        analytical_method="Test",
        ruleset_version="V1",
        dataset_version_id=uuid4(),
        analysis_run_id=uuid4(),
        created_at=now,
    )


def test_spearman_calculation():
    # Identical
    assert compute_spearman([1, 2, 3], [1, 2, 3]) == 1.0
    # Reversed
    assert compute_spearman([1, 2, 3], [3, 2, 1]) == -1.0
    # Single element
    assert compute_spearman([1], [1]) == 1.0
    # Empty
    assert compute_spearman([], []) == 1.0


def test_perturbation_validity():
    base = {
        "signal_strength_weight": 0.30,
        "peer_deviation_weight": 0.25,
        "persistence_weight": 0.20,
        "asset_criticality_weight": 0.15,
        "data_uncertainty_weight": -0.10,
    }
    configs = generate_perturbations(base, [0.05, 0.10, 0.15, 0.20])
    
    for c in configs:
        w = c.weights
        assert w["data_uncertainty_weight"] == -0.10
        # Positive weights should sum to 0.90 (due to L1 normalization logic where we subtracted exact offset)
        pos_sum = (w["signal_strength_weight"] + w["peer_deviation_weight"] +
                   w["persistence_weight"] + w["asset_criticality_weight"])
        # Float math precision
        assert abs(pos_sum - 0.90) < 1e-6
        # No negative weights for the main 4
        for k in ["signal_strength_weight", "peer_deviation_weight", "persistence_weight", "asset_criticality_weight"]:
            assert w[k] >= 0.0


def test_stability_analyzer_empty():
    analyzer = StabilityAnalyzer()
    report = analyzer.analyze([], uuid4())
    assert report.population_size == 0
    assert len(report.results) == 16 # 4 keys * 4 magnitudes


def test_stability_analyzer_one_finding():
    analyzer = StabilityAnalyzer()
    f1 = _make_finding(0.8, {"T": 1.0, "D": 0.5, "B": 0.5, "C": 1.0, "A": 0.0})
    report = analyzer.analyze([f1], uuid4(), budgets=[1])
    assert report.population_size == 1
    for r in report.results:
        assert r.rank_metrics.spearman_rho == 1.0
        assert r.review_set_metrics[1].overlap_percentage == 1.0


def test_stability_analyzer_no_mutation():
    analyzer = StabilityAnalyzer()
    f1 = _make_finding(0.8, {"T": 1.0, "D": 0.5, "B": 0.5, "C": 1.0, "A": 0.0})
    original_f1 = copy.deepcopy(f1)
    
    analyzer.analyze([f1], uuid4())
    
    # Assert finding was not mutated
    assert f1.priority_score == original_f1.priority_score
    assert f1.priority_components == original_f1.priority_components


def test_stability_analyzer_threshold_crossing():
    analyzer = StabilityAnalyzer()
    # Baseline score = 0.3*0.8 + 0.25*1.0 + 0.2*1.0 + 0.15*0.5 - 0.1*0.0 = 0.24 + 0.25 + 0.2 + 0.075 = 0.765 (HIGH)
    f1 = _make_finding(0.765, {"T": 0.8, "D": 1.0, "B": 1.0, "C": 0.5, "A": 0.0})
    report = analyzer.analyze([f1], uuid4(), magnitudes=[0.20])
    
    crossings = sum(r.high_tier_crossings_out for r in report.results)
    # With a 20% shift away from D and B towards C (where C is only 0.5), score drops below 0.75
    assert crossings > 0


def test_review_set_overlap_with_ties():
    analyzer = StabilityAnalyzer(optimizer_seed=42)
    # 5 findings with identical priority and components, differing only by cse_id
    findings = [
        _make_finding(0.8, {"T": 1.0, "D": 1.0, "B": 1.0, "C": 1.0, "A": 0.0}, cse_id=uuid4())
        for _ in range(5)
    ]
    report = analyzer.analyze(findings, uuid4(), budgets=[3])
    for r in report.results:
        # Since all components are 1.0, any valid perturbation keeping pos_sum=0.9 will result in the same identical scores!
        # Thus the review set must overlap perfectly (1.0).
        assert r.review_set_metrics[3].overlap_percentage == 1.0


def test_sensitive_scenario_near_ties():
    analyzer = StabilityAnalyzer()
    # Create findings that are extremely close, but have vastly different structural components.
    # f1 relies entirely on T.
    f1 = _make_finding(0.80, {"T": 1.0, "D": 0.0, "B": 0.0, "C": 0.0, "A": 0.0}, cse_id=uuid4()) # actual score under base = 0.3
    f1.priority_score = 0.3 
    
    # f2 relies entirely on D.
    f2 = _make_finding(0.30, {"T": 0.0, "D": 1.0, "B": 0.0, "C": 0.0, "A": 0.0}, cse_id=uuid4()) # actual score under base = 0.25
    f2.priority_score = 0.25

    report = analyzer.analyze([f1, f2], uuid4(), budgets=[1], magnitudes=[0.20])
    
    # We should see rank inversions for the perturbation that boosts D and penalizes T.
    inversions = sum(r.rank_metrics.inversions for r in report.results)
    assert inversions > 0

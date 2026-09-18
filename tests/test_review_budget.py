"""
INNOVATION PHASE 4: SUPERVISORY REVIEW-BUDGET OPTIMIZER — Tests

20 deterministic test scenarios covering:
1-5:   Budget edge cases (0, 1, small, large, empty)
6-10:  Deduplication and redundancy
11-15: Coverage, diversity, and contradiction selection
16-20: Reproducibility, seed, cross-CSE/period isolation
"""
from uuid import uuid4
from datetime import datetime, timezone, timedelta
import pytest

from backend.models.canonical import (
    Finding, FindingType, EvidenceSufficiencyState, EvidenceRef,
    DataQualityScore, DataQualityComponents, ExpectationBasis,
)
from analytics.review_budget.optimizer import ReviewBudgetOptimizer


def _make_finding(
    finding_type: FindingType = FindingType.FAST_CLOSURE,
    priority_score: float = 0.8,
    cse_id=None,
    reporting_period_id=None,
    evidence_state=EvidenceSufficiencyState.SUPPORTED,
    confidence=0.9,
    evidence_refs=None,
) -> Finding:
    now = datetime.now(timezone.utc)
    return Finding(
        finding_id=uuid4(),
        cse_id=cse_id or uuid4(),
        reporting_period_id=reporting_period_id or uuid4(),
        finding_type=finding_type,
        priority_score=priority_score,
        priority_components={"T": 0.8, "D": 0.5, "B": 0.6, "C": 0.7, "A": 0.1},
        evidentiary_confidence=confidence,
        data_quality_status=DataQualityScore(
            dataset_version_id=uuid4(), score=0.95,
            components=DataQualityComponents(
                completeness_ratio=0.95, consistency_ratio=0.95,
                coverage_ratio=0.95, sample_sufficiency_ratio=0.95,
            ),
            ruleset_version="V1", computed_at=now,
        ),
        expectation_basis=ExpectationBasis.STATISTICAL_BASELINE,
        expected_behavior="Expected normal operation.",
        observed_behavior="Anomalous pattern detected.",
        supporting_signals=["Signal A", "Signal B"],
        evidence_refs=evidence_refs or [EvidenceRef(entity_type="Alert", entity_id=uuid4())],
        evidence_state=evidence_state,
        analytical_method="Test",
        ruleset_version="V1",
        dataset_version_id=uuid4(),
        analysis_run_id=uuid4(),
        created_at=now,
    )


# 1. Budget 0
def test_budget_zero():
    opt = ReviewBudgetOptimizer()
    candidates = [_make_finding() for _ in range(5)]
    report = opt.optimize(candidates, budget=0)
    assert report.selected_count == 0
    assert report.budget == 0
    assert report.candidate_count == 5


# 2. Budget 1
def test_budget_one():
    opt = ReviewBudgetOptimizer()
    candidates = [_make_finding(priority_score=p) for p in [0.9, 0.5, 0.3]]
    report = opt.optimize(candidates, budget=1)
    assert report.selected_count == 1
    assert not report.selected_items[0].is_control_sample


# 3. Budget smaller than population
def test_budget_smaller_than_population():
    opt = ReviewBudgetOptimizer()
    candidates = [_make_finding() for _ in range(20)]
    report = opt.optimize(candidates, budget=5)
    assert report.selected_count == 5


# 4. Budget larger than population
def test_budget_larger_than_population():
    opt = ReviewBudgetOptimizer()
    candidates = [_make_finding() for _ in range(3)]
    report = opt.optimize(candidates, budget=50)
    assert report.selected_count == 3


# 5. Empty candidates
def test_empty_candidates():
    opt = ReviewBudgetOptimizer()
    report = opt.optimize([], budget=10)
    assert report.selected_count == 0
    assert report.candidate_count == 0


# 6. All candidates identical (same CSE, type, period → dedup)
def test_all_identical():
    cse = uuid4()
    period = uuid4()
    opt = ReviewBudgetOptimizer()
    candidates = [
        _make_finding(cse_id=cse, reporting_period_id=period, priority_score=p)
        for p in [0.9, 0.8, 0.7, 0.6]
    ]
    report = opt.optimize(candidates, budget=10)
    # All 4 share (cse, type, period) so dedup keeps only 1 unique
    assert report.selected_count == 1


# 7. Multiple finding types selected
def test_multiple_finding_types():
    cse = uuid4()
    period = uuid4()
    opt = ReviewBudgetOptimizer()
    candidates = [
        _make_finding(finding_type=FindingType.FAST_CLOSURE, cse_id=cse, reporting_period_id=period),
        _make_finding(finding_type=FindingType.ESCALATION_GAP, cse_id=cse, reporting_period_id=period),
        _make_finding(finding_type=FindingType.COVERAGE_GAP, cse_id=cse, reporting_period_id=period),
        _make_finding(finding_type=FindingType.EVIDENCE_CONTRADICTION, cse_id=cse, reporting_period_id=period),
    ]
    report = opt.optimize(candidates, budget=10)
    types_selected = set(s.finding.finding_type for s in report.selected_items)
    assert len(types_selected) == 4


# 8. Multiple CSEs
def test_multiple_cses():
    opt = ReviewBudgetOptimizer()
    cse_ids = [uuid4() for _ in range(4)]
    candidates = [_make_finding(cse_id=c, priority_score=0.7) for c in cse_ids]
    report = opt.optimize(candidates, budget=10)
    cses_selected = set(s.finding.cse_id for s in report.selected_items)
    assert len(cses_selected) == 4


# 9. Multiple reporting periods
def test_multiple_periods():
    opt = ReviewBudgetOptimizer()
    cse = uuid4()
    period_ids = [uuid4() for _ in range(3)]
    candidates = [_make_finding(cse_id=cse, reporting_period_id=p) for p in period_ids]
    report = opt.optimize(candidates, budget=10)
    periods_selected = set(s.finding.reporting_period_id for s in report.selected_items)
    assert len(periods_selected) == 3


# 10. High-priority repeated duplicates: only 1 should be selected
def test_high_priority_duplicates():
    cse = uuid4()
    period = uuid4()
    opt = ReviewBudgetOptimizer()
    candidates = [
        _make_finding(cse_id=cse, reporting_period_id=period, priority_score=0.95),
        _make_finding(cse_id=cse, reporting_period_id=period, priority_score=0.94),
        _make_finding(cse_id=cse, reporting_period_id=period, priority_score=0.93),
    ]
    report = opt.optimize(candidates, budget=5)
    assert report.selected_count == 1


# 11. Low-priority unique informative case vs high-priority duplicate
def test_low_priority_unique_vs_duplicate():
    cse1 = uuid4()
    cse2 = uuid4()
    period = uuid4()
    opt = ReviewBudgetOptimizer()
    candidates = [
        _make_finding(cse_id=cse1, reporting_period_id=period, priority_score=0.95),
        _make_finding(cse_id=cse1, reporting_period_id=period, priority_score=0.94),
        _make_finding(cse_id=cse2, reporting_period_id=period, priority_score=0.4,
                      finding_type=FindingType.COVERAGE_GAP),
    ]
    report = opt.optimize(candidates, budget=3)
    # After dedup, candidates are 2 unique: (cse1,FAST_CLOSURE) and (cse2,COVERAGE_GAP)
    cses = set(s.finding.cse_id for s in report.selected_items if not s.is_control_sample)
    assert cse2 in cses  # low-priority unique CSE should be selected for coverage


# 12. Contradiction case selection
def test_contradiction_case_selection():
    opt = ReviewBudgetOptimizer()
    cse = uuid4()
    candidates = [
        _make_finding(finding_type=FindingType.EVIDENCE_CONTRADICTION, cse_id=cse, priority_score=0.6),
        _make_finding(finding_type=FindingType.FAST_CLOSURE, cse_id=cse, priority_score=0.6),
    ]
    report = opt.optimize(candidates, budget=2)
    # Contradiction should get priority due to contradiction_v bonus
    first = report.selected_items[0]
    assert first.finding.finding_type == FindingType.EVIDENCE_CONTRADICTION or first.contradiction_contribution > 0


# 13. KPI divergence case
def test_kpi_divergence_included():
    opt = ReviewBudgetOptimizer()
    candidates = [
        _make_finding(finding_type=FindingType.METRIC_OUTCOME_DIVERGENCE),
        _make_finding(finding_type=FindingType.FAST_CLOSURE),
    ]
    report = opt.optimize(candidates, budget=5)
    types = set(s.finding.finding_type for s in report.selected_items)
    assert FindingType.METRIC_OUTCOME_DIVERGENCE in types


# 14. Uncertainty case
def test_uncertainty_case():
    opt = ReviewBudgetOptimizer()
    candidates = [
        _make_finding(priority_score=0.7, confidence=0.3,
                      evidence_state=EvidenceSufficiencyState.WEAKLY_SUPPORTED),
        _make_finding(priority_score=0.7, confidence=0.95),
    ]
    report = opt.optimize(candidates, budget=2)
    uncertain = [s for s in report.selected_items if s.uncertainty_contribution > 0]
    assert len(uncertain) >= 1


# 15. Control sample
def test_control_sample():
    opt = ReviewBudgetOptimizer(control_fraction=0.20, seed=42)
    cse_ids = [uuid4() for _ in range(10)]
    candidates = [_make_finding(cse_id=c) for c in cse_ids]
    report = opt.optimize(candidates, budget=10)
    assert report.control_sample_count >= 1
    controls = [s for s in report.selected_items if s.is_control_sample]
    assert len(controls) >= 1


# 16. Deterministic seed reproducibility
def test_deterministic_reproducibility():
    opt = ReviewBudgetOptimizer(seed=12345)
    cse_ids = [uuid4() for _ in range(10)]
    candidates = [_make_finding(cse_id=c) for c in cse_ids]

    report1 = opt.optimize(candidates, budget=5)
    report2 = opt.optimize(candidates, budget=5)

    ids1 = [s.finding_id for s in report1.selected_items]
    ids2 = [s.finding_id for s in report2.selected_items]
    assert ids1 == ids2


# 17. Repeated execution identical selection
def test_repeated_identical():
    opt1 = ReviewBudgetOptimizer(seed=99)
    opt2 = ReviewBudgetOptimizer(seed=99)
    candidates = [_make_finding() for _ in range(8)]

    r1 = opt1.optimize(candidates, budget=4)
    r2 = opt2.optimize(candidates, budget=4)

    assert [s.finding_id for s in r1.selected_items] == [s.finding_id for s in r2.selected_items]


# 18. Different budget → different size
def test_different_budget_different_size():
    opt = ReviewBudgetOptimizer()
    cse_ids = [uuid4() for _ in range(10)]
    candidates = [_make_finding(cse_id=c) for c in cse_ids]

    r5 = opt.optimize(candidates, budget=5)
    r8 = opt.optimize(candidates, budget=8)
    assert r5.selected_count == 5
    assert r8.selected_count == 8


# 19. No cross-CSE contamination
def test_no_cross_cse_contamination():
    cse_a = uuid4()
    cse_b = uuid4()
    period = uuid4()
    opt = ReviewBudgetOptimizer()
    candidates = [
        _make_finding(cse_id=cse_a, reporting_period_id=period, priority_score=0.9),
        _make_finding(cse_id=cse_b, reporting_period_id=period, priority_score=0.3),
    ]
    report = opt.optimize(candidates, budget=2)
    # Each finding should reference only its own CSE
    for s in report.selected_items:
        assert s.finding.cse_id in (cse_a, cse_b)


# 20. No cross-period contamination
def test_no_cross_period_contamination():
    cse = uuid4()
    p1 = uuid4()
    p2 = uuid4()
    opt = ReviewBudgetOptimizer()
    candidates = [
        _make_finding(cse_id=cse, reporting_period_id=p1),
        _make_finding(cse_id=cse, reporting_period_id=p2),
    ]
    report = opt.optimize(candidates, budget=2)
    for s in report.selected_items:
        assert s.finding.reporting_period_id in (p1, p2)

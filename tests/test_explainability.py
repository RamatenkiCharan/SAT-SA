"""
Unit tests for Explainability Template Substitution Engine.
"""
from datetime import datetime, timezone
from uuid import uuid4

from analytics.explainability.templates import generate_finding_explanation
from backend.models.canonical import (
    DataQualityComponents,
    DataQualityScore,
    EvidenceRef,
    ExpectationBasis,
    Finding,
    FindingType,
)


def test_explainability_renders_deterministic_template():
    now = datetime.now(timezone.utc)
    ver_id = uuid4()
    dq = DataQualityScore(
        dataset_version_id=ver_id,
        score=0.92,
        components=DataQualityComponents(
            completeness_ratio=0.95,
            consistency_ratio=0.98,
            coverage_ratio=0.88,
            sample_sufficiency_ratio=0.90,
        ),
        ruleset_version="V1",
        computed_at=now,
    )

    finding = Finding(
        finding_id=uuid4(),
        cse_id=uuid4(),
        reporting_period_id=uuid4(),
        finding_type=FindingType.FAST_CLOSURE,
        priority_score=0.85,
        priority_components={
            "signal_strength": 0.8,
            "peer_deviation": 0.9,
            "persistence": 0.7,
            "asset_criticality": 1.0,
            "data_uncertainty": 0.08,
        },
        evidentiary_confidence=0.94,
        data_quality_status=dq,
        expectation_basis=ExpectationBasis.STATISTICAL_BASELINE,
        expected_behavior="Expected ~45 min median duration",
        observed_behavior="Observed 14 critical cases closed in <4 min",
        supporting_signals=["14 critical alerts closed rapidly"],
        contradicting_signals=[],
        evidence_refs=[EvidenceRef(entity_type="alert", entity_id=uuid4())],
        analytical_method="Peer MAD",
        ruleset_version="V1",
        dataset_version_id=ver_id,
        analysis_run_id=uuid4(),
        created_at=now,
    )

    exp = generate_finding_explanation(finding)
    assert exp["priority_label"] == "HIGH"
    assert "Rapid-Closure Execution Gap" in exp["title"]
    assert exp["data_quality_breakdown"]["overall_score"] == 92.0
    assert exp["data_quality_breakdown"]["completeness"] == 95.0
    assert "supervisory" in exp["recommended_action"].lower()

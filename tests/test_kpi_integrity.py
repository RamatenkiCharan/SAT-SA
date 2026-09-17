import pytest
from uuid import uuid4
from datetime import datetime, timezone
from backend.models.canonical import KPIClaim, ExpectationBasis, Severity, EvidenceSufficiencyState, FindingType
from analytics.kpi_integrity.divergence_detector import ClaimEvidenceDivergenceDetector
from analytics.data_quality.quality_score import DataQualityResult, DataQualityComponents
from backend.models.ruleset import DEFAULT_AUTHORITATIVE_RULESET_V1
from analytics.synthetic_generator import generate_synthetic_soc_benchmark
from backend.services.ingestion import validate_and_canonicalize_bundle
from analytics.workflow.workflow_reconstruction import ReconstructedDataset

def test_kpi_divergence_detector():
    now = datetime.now(timezone.utc)
    ver_id = uuid4()
    
    # Generate bundle with KPI claims
    raw_bundle, _ = generate_synthetic_soc_benchmark()
    
    # Make sure kpi_claims exist
    assert "kpi_claims" in raw_bundle
    assert len(raw_bundle["kpi_claims"]) > 0
    raw_bundle["kpi_claims"] = raw_bundle["kpi_claims"][:1]
    
    # Set the reported value high so it diverges from actual
    raw_bundle["kpi_claims"][0]["reported_value"] = 0.99
    
    canonical_ds, summary = validate_and_canonicalize_bundle(raw_bundle, ver_id, now)
    reconstructed_ds = ReconstructedDataset(canonical_ds)
    
    dq_result = DataQualityResult(
        score=0.9,
        components=DataQualityComponents(completeness_ratio=1.0, consistency_ratio=1.0, coverage_ratio=0.8, sample_sufficiency_ratio=1.0),
        warnings=[],
        dataset_version_id=ver_id,
        ruleset_version="1.0",
        computed_at=now
    )
    
    detector = ClaimEvidenceDivergenceDetector(ruleset=DEFAULT_AUTHORITATIVE_RULESET_V1)
    
    # 1. Run detector
    findings = detector.detect(canonical_ds, reconstructed_ds, dq_result, uuid4())
    
    assert len(findings) == 1
    f = findings[0]
    assert f.finding_type == FindingType.SUPERVISORY_DIVERGENCE
    assert f.evidence_state == EvidenceSufficiencyState.SUPPORTED
    
    # 2. Test low DQ (should yield Insufficient Evidence)
    dq_result_low = DataQualityResult(
        score=0.5,
        components=DataQualityComponents(completeness_ratio=0.5, consistency_ratio=0.5, coverage_ratio=0.5, sample_sufficiency_ratio=0.5),
        warnings=[],
        dataset_version_id=ver_id,
        ruleset_version="1.0",
        computed_at=now
    )
    findings_low = detector.detect(canonical_ds, reconstructed_ds, dq_result_low, uuid4())
    assert len(findings_low) == 1
    f_low = findings_low[0]
    assert f_low.finding_type == FindingType.SUPERVISORY_DIVERGENCE
    assert f_low.evidence_state == EvidenceSufficiencyState.INSUFFICIENT_EVIDENCE

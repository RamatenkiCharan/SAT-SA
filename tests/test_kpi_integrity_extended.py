import pytest
from uuid import uuid4
from datetime import datetime, timezone

from backend.models.canonical import (
    KPIClaim,
    Severity,
    EvidenceSufficiencyState,
    FindingType,
    Alert,
    AlertStatus,
    Case,
    Closure,
    CSE
)
from backend.models.ruleset import DEFAULT_AUTHORITATIVE_RULESET_V1
from analytics.data_quality.quality_score import DataQualityResult, DataQualityComponents
from analytics.canonicalization.canonicalization import CanonicalDataset
from analytics.workflow.workflow_reconstruction import ReconstructedDataset
from analytics.kpi_integrity.divergence_detector import ClaimEvidenceDivergenceDetector
from analytics.kpi_integrity.metric_reconstruction import MetricReconstructionEngine

@pytest.fixture
def kpi_setup():
    now = datetime.now(timezone.utc)
    ver_id = uuid4()
    cse_id = uuid4()
    rep_id = uuid4()
    
    ds = CanonicalDataset(dataset_version_id=ver_id)
    ds.cse_list.append(CSE(
        cse_id=cse_id, name="Test CSE", sector="IT", scale="small", 
        reporting_period_id=rep_id, dataset_version_id=ver_id, source_record_ref="cse", ingest_time=now
    ))
    
    dq = DataQualityResult(
        score=1.0,
        components=DataQualityComponents(1.0, 1.0, 1.0, 1.0),
        warnings=[],
        dataset_version_id=ver_id,
        ruleset_version="1.0",
        computed_at=now
    )
    
    detector = ClaimEvidenceDivergenceDetector(ruleset=DEFAULT_AUTHORITATIVE_RULESET_V1)
    
    return ds, dq, detector, cse_id, rep_id, ver_id, now

def create_closure_chain(ds, cse_id, rep_id, duration_minutes):
    now = datetime.now(timezone.utc)
    a_id = uuid4()
    c_id = uuid4()
    clo_id = uuid4()
    
    import datetime as dt
    event_time = now - dt.timedelta(minutes=100)
    closed_at = event_time + dt.timedelta(minutes=duration_minutes)
    
    ds.alerts.append(Alert(
        alert_id=a_id, cse_id=cse_id, asset_id=uuid4(), reporting_period_id=rep_id,
        event_time=event_time, severity=Severity.HIGH, alert_category="test", source="test", status=AlertStatus.CLOSED,
        dataset_version_id=ds.dataset_version_id, ingest_time=now
    ))
    ds.cases.append(Case(
        case_id=c_id, alert_id=a_id, status="CLOSED", title="test", priority=Severity.HIGH,
        dataset_version_id=ds.dataset_version_id, ingest_time=now, opened_at=event_time, severity=Severity.HIGH
    ))
    ds.closures.append(Closure(
        closure_id=clo_id, case_id=c_id, closed_at=closed_at, reason="resolved",
        dataset_version_id=ds.dataset_version_id, ingest_time=now, source_record_ref=f"closure_{clo_id}"
    ))

def test_kpi_fully_supported(kpi_setup):
    ds, dq, detector, cse_id, rep_id, ver_id, now = kpi_setup
    
    # 10 compliant closures (30 mins < 60 mins)
    for _ in range(10):
        create_closure_chain(ds, cse_id, rep_id, 30)
        
    ds.kpi_claims.append(KPIClaim(
        claim_id=uuid4(), cse_id=cse_id, reporting_period_id=rep_id, metric_name="SLA Compliance",
        reported_value=1.0, target_value=60.0, population="All", context="", dataset_version_id=ver_id, ingest_time=now
    ))
    
    findings = detector.detect(ds, ReconstructedDataset(ds), dq, uuid4())
    assert len(findings) == 0 # Fully supported, no divergence

def test_missing_closure_evidence(kpi_setup):
    ds, dq, detector, cse_id, rep_id, ver_id, now = kpi_setup
    
    # Empty dataset -> compliant_count = 0, total_count = 0 -> metric is 0.0
    # But wait! If reported is 0.99, is that divergence?
    ds.kpi_claims.append(KPIClaim(
        claim_id=uuid4(), cse_id=cse_id, reporting_period_id=rep_id, metric_name="SLA Compliance",
        reported_value=0.99, target_value=60.0, population="All", context="", dataset_version_id=ver_id, ingest_time=now
    ))
    
    findings = detector.detect(ds, ReconstructedDataset(ds), dq, uuid4())
    assert len(findings) == 1
    assert findings[0].finding_type == FindingType.SUPERVISORY_DIVERGENCE
    assert any("Evaluated Closures: 0" in sig for sig in findings[0].supporting_signals)

def test_small_numerical_variation(kpi_setup):
    ds, dq, detector, cse_id, rep_id, ver_id, now = kpi_setup
    
    # 9 compliant, 1 non-compliant -> actual = 0.90
    for _ in range(9):
        create_closure_chain(ds, cse_id, rep_id, 30)
    create_closure_chain(ds, cse_id, rep_id, 90)
    
    # Report 0.94 -> diff is 0.04 (<= 0.05) -> no finding
    ds.kpi_claims.append(KPIClaim(
        claim_id=uuid4(), cse_id=cse_id, reporting_period_id=rep_id, metric_name="SLA Compliance",
        reported_value=0.94, target_value=60.0, population="All", context="", dataset_version_id=ver_id, ingest_time=now
    ))
    
    findings = detector.detect(ds, ReconstructedDataset(ds), dq, uuid4())
    assert len(findings) == 0

def test_boundary_divergence_threshold(kpi_setup):
    ds, dq, detector, cse_id, rep_id, ver_id, now = kpi_setup
    
    # 9 compliant, 1 non-compliant -> actual = 0.90
    for _ in range(9):
        create_closure_chain(ds, cse_id, rep_id, 30)
    create_closure_chain(ds, cse_id, rep_id, 90)
    
    # Report 0.95 -> diff is 0.05. It should NOT emit finding because condition is > threshold.
    ds.kpi_claims.append(KPIClaim(
        claim_id=uuid4(), cse_id=cse_id, reporting_period_id=rep_id, metric_name="SLA Compliance",
        reported_value=0.95, target_value=60.0, population="All", context="", dataset_version_id=ver_id, ingest_time=now
    ))
    findings = detector.detect(ds, ReconstructedDataset(ds), dq, uuid4())
    assert len(findings) == 0
    
    # Report 0.951 -> diff is 0.051 > 0.05. Should emit finding.
    ds.kpi_claims[0].reported_value = 0.951
    findings = detector.detect(ds, ReconstructedDataset(ds), dq, uuid4())
    assert len(findings) == 1

def test_population_reporting_window_mismatch(kpi_setup):
    ds, dq, detector, cse_id, rep_id, ver_id, now = kpi_setup
    
    # Closure belongs to a DIFFERENT reporting period or CSE
    other_rep_id = uuid4()
    for _ in range(10):
        create_closure_chain(ds, cse_id, other_rep_id, 30) # All compliant but wrong period
        
    ds.kpi_claims.append(KPIClaim(
        claim_id=uuid4(), cse_id=cse_id, reporting_period_id=rep_id, metric_name="SLA Compliance",
        reported_value=1.0, target_value=60.0, population="All", context="", dataset_version_id=ver_id, ingest_time=now
    ))
    
    # Engine will see 0 applicable closures for `rep_id`. Actual = 0.0. Divergence = 1.0 > 0.05.
    findings = detector.detect(ds, ReconstructedDataset(ds), dq, uuid4())
    assert len(findings) == 1
    assert any("Evaluated Closures: 0" in sig for sig in findings[0].supporting_signals)

def test_provenance_linkage(kpi_setup):
    ds, dq, detector, cse_id, rep_id, ver_id, now = kpi_setup
    
    create_closure_chain(ds, cse_id, rep_id, 120)
    
    claim = KPIClaim(
        claim_id=uuid4(), cse_id=cse_id, reporting_period_id=rep_id, metric_name="SLA Compliance",
        reported_value=1.0, target_value=60.0, population="All", context="", dataset_version_id=ver_id, ingest_time=now
    )
    ds.kpi_claims.append(claim)
    
    analysis_run_id = uuid4()
    findings = detector.detect(ds, ReconstructedDataset(ds), dq, analysis_run_id)
    assert len(findings) == 1
    f = findings[0]
    
    assert f.dataset_version_id == ver_id
    assert f.analysis_run_id == analysis_run_id
    assert f.ruleset_version == "V1"
    
    types = [ref.entity_type for ref in f.evidence_refs]
    assert "KPIClaim" in types
    assert "Closure" in types
    
    claim_ref = next(ref for ref in f.evidence_refs if ref.entity_type == "KPIClaim")
    assert claim_ref.entity_id == claim.claim_id

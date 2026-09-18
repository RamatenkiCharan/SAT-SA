from uuid import uuid4
from datetime import datetime, timezone, timedelta
import pytest

from backend.models.canonical import Alert, Case, Investigation, Action, Escalation, Severity, AlertStatus, ReportingPeriod, CSE, KPIClaim
from analytics.canonicalization.canonicalization import CanonicalDataset
from analytics.workflow.workflow_reconstruction import ReconstructedDataset
from analytics.data_quality.quality_score import DataQualityResult, DataQualityComponents
from backend.models.ruleset import DEFAULT_AUTHORITATIVE_RULESET_V1
from analytics.contradiction.evidence_contradiction import EvidenceContradictionEngine

def create_base_entities():
    cse_id = uuid4()
    rep_id = uuid4()
    now = datetime.now(timezone.utc)
    cse = CSE(
        cse_id=cse_id, name="Test CSE", sector="Energy", scale="large",
        reporting_period_id=rep_id, dataset_version_id=uuid4(), ingest_time=now
    )
    rep = ReportingPeriod(
        reporting_period_id=rep_id, cse_id=cse_id,
        period_start=now - timedelta(days=30), period_end=now
    )
    return cse, rep

# 1. fully consistent workflow
def test_fully_consistent_workflow():
    cse, rep = create_base_entities()
    now = datetime.now(timezone.utc)
    alt_id, case_id = uuid4(), uuid4()
    
    canonical_ds = CanonicalDataset(dataset_version_id=uuid4())
    canonical_ds.cse_list = [cse]
    canonical_ds.reporting_periods = [rep]
    
    canonical_ds.alerts = [Alert(
        alert_id=alt_id, cse_id=cse.cse_id, asset_id=uuid4(), reporting_period_id=rep.reporting_period_id,
        event_time=now, severity=Severity.MEDIUM, alert_category="Test", source="Test", status=AlertStatus.CLOSED,
        dataset_version_id=uuid4(), ingest_time=now
    )]
    canonical_ds.cases = [Case(
        case_id=case_id, alert_id=alt_id, opened_at=now, closed_at=now+timedelta(minutes=10),
        severity=Severity.MEDIUM, dataset_version_id=uuid4(), ingest_time=now
    )]
    
    reconstructed_ds = ReconstructedDataset(canonical_ds)
    dq_result = DataQualityResult(
        dataset_version_id=uuid4(), score=1.0, 
        components=DataQualityComponents(completeness_ratio=1.0, consistency_ratio=1.0, coverage_ratio=1.0, sample_sufficiency_ratio=1.0),
        ruleset_version="V1", computed_at=now
    )
    
    engine = EvidenceContradictionEngine(DEFAULT_AUTHORITATIVE_RULESET_V1)
    findings = engine.detect(canonical_ds, reconstructed_ds, dq_result, uuid4())
    assert len(findings) == 0

# 2. alert closed + case open
def test_alert_closed_case_open():
    cse, rep = create_base_entities()
    now = datetime.now(timezone.utc)
    alt_id, case_id = uuid4(), uuid4()
    
    canonical_ds = CanonicalDataset(dataset_version_id=uuid4())
    canonical_ds.cse_list = [cse]
    canonical_ds.alerts = [Alert(
        alert_id=alt_id, cse_id=cse.cse_id, asset_id=uuid4(), reporting_period_id=rep.reporting_period_id,
        event_time=now, severity=Severity.MEDIUM, alert_category="Test", source="Test", status=AlertStatus.CLOSED,
        dataset_version_id=uuid4(), ingest_time=now
    )]
    canonical_ds.cases = [Case(
        case_id=case_id, alert_id=alt_id, opened_at=now, closed_at=None,
        severity=Severity.MEDIUM, dataset_version_id=uuid4(), ingest_time=now
    )]
    
    reconstructed_ds = ReconstructedDataset(canonical_ds)
    dq_result = DataQualityResult(
        dataset_version_id=uuid4(), score=1.0, 
        components=DataQualityComponents(completeness_ratio=1.0, consistency_ratio=1.0, coverage_ratio=1.0, sample_sufficiency_ratio=1.0),
        ruleset_version="V1", computed_at=now
    )
    
    engine = EvidenceContradictionEngine(DEFAULT_AUTHORITATIVE_RULESET_V1)
    findings = engine.detect(canonical_ds, reconstructed_ds, dq_result, uuid4())
    assert len(findings) == 1
    assert "LIFECYCLE_CONFLICT" in findings[0].supporting_signals[0]

# 3. explicit escalation conflict
def test_explicit_escalation_conflict():
    cse, rep = create_base_entities()
    now = datetime.now(timezone.utc)
    alt_id = uuid4()
    
    canonical_ds = CanonicalDataset(dataset_version_id=uuid4())
    canonical_ds.cse_list = [cse]
    canonical_ds.alerts = [Alert(
        alert_id=alt_id, cse_id=cse.cse_id, asset_id=uuid4(), reporting_period_id=rep.reporting_period_id,
        event_time=now, severity=Severity.MEDIUM, alert_category="Test", source="Test", status=AlertStatus.ESCALATED,
        dataset_version_id=uuid4(), ingest_time=now
    )]
    
    reconstructed_ds = ReconstructedDataset(canonical_ds)
    dq_result = DataQualityResult(
        dataset_version_id=uuid4(), score=1.0, 
        components=DataQualityComponents(completeness_ratio=1.0, consistency_ratio=1.0, coverage_ratio=1.0, sample_sufficiency_ratio=1.0),
        ruleset_version="V1", computed_at=now
    )
    
    engine = EvidenceContradictionEngine(DEFAULT_AUTHORITATIVE_RULESET_V1)
    findings = engine.detect(canonical_ds, reconstructed_ds, dq_result, uuid4())
    assert len(findings) == 1
    assert "ESCALATION_CONFLICT" in findings[0].supporting_signals[0]

# 4. response completed + case unresolved
def test_response_completed_case_unresolved():
    cse, rep = create_base_entities()
    now = datetime.now(timezone.utc)
    alt_id, case_id = uuid4(), uuid4()
    
    canonical_ds = CanonicalDataset(dataset_version_id=uuid4())
    canonical_ds.cse_list = [cse]
    canonical_ds.alerts = [Alert(
        alert_id=alt_id, cse_id=cse.cse_id, asset_id=uuid4(), reporting_period_id=rep.reporting_period_id,
        event_time=now, severity=Severity.MEDIUM, alert_category="Test", source="Test", status=AlertStatus.OPEN,
        dataset_version_id=uuid4(), ingest_time=now
    )]
    canonical_ds.cases = [Case(
        case_id=case_id, alert_id=alt_id, opened_at=now, closed_at=None,
        severity=Severity.MEDIUM, dataset_version_id=uuid4(), ingest_time=now
    )]
    canonical_ds.actions = [Action(
        action_id=uuid4(), case_id=case_id, action_type="Remediate", performed_at=now, outcome="SUCCESS",
        dataset_version_id=uuid4(), ingest_time=now
    )]
    
    reconstructed_ds = ReconstructedDataset(canonical_ds)
    dq_result = DataQualityResult(
        dataset_version_id=uuid4(), score=1.0, 
        components=DataQualityComponents(completeness_ratio=1.0, consistency_ratio=1.0, coverage_ratio=1.0, sample_sufficiency_ratio=1.0),
        ruleset_version="V1", computed_at=now
    )
    
    engine = EvidenceContradictionEngine(DEFAULT_AUTHORITATIVE_RULESET_V1)
    findings = engine.detect(canonical_ds, reconstructed_ds, dq_result, uuid4())
    assert len(findings) == 1
    assert "RESPONSE_STATE_CONFLICT" in findings[0].supporting_signals[0]

# 5. KPI/report says resolved + case open
def test_kpi_claim_contradiction():
    cse, rep = create_base_entities()
    now = datetime.now(timezone.utc)
    alt_id, case_id = uuid4(), uuid4()
    
    canonical_ds = CanonicalDataset(dataset_version_id=uuid4())
    canonical_ds.cse_list = [cse]
    canonical_ds.alerts = [Alert(
        alert_id=alt_id, cse_id=cse.cse_id, asset_id=uuid4(), reporting_period_id=rep.reporting_period_id,
        event_time=now, severity=Severity.CRITICAL, alert_category="Test", source="Test", status=AlertStatus.OPEN,
        dataset_version_id=uuid4(), ingest_time=now
    )]
    canonical_ds.cases = [Case(
        case_id=case_id, alert_id=alt_id, opened_at=now, closed_at=None,
        severity=Severity.CRITICAL, dataset_version_id=uuid4(), ingest_time=now
    )]
    canonical_ds.kpi_claims = [KPIClaim(
        claim_id=uuid4(), cse_id=cse.cse_id, reporting_period_id=rep.reporting_period_id,
        metric_name="Resolution Rate", reported_value=0.99, target_value=0.95,
        dataset_version_id=uuid4(), ingest_time=now
    )]
    
    reconstructed_ds = ReconstructedDataset(canonical_ds)
    dq_result = DataQualityResult(
        dataset_version_id=uuid4(), score=1.0, 
        components=DataQualityComponents(completeness_ratio=1.0, consistency_ratio=1.0, coverage_ratio=1.0, sample_sufficiency_ratio=1.0),
        ruleset_version="V1", computed_at=now
    )
    
    engine = EvidenceContradictionEngine(DEFAULT_AUTHORITATIVE_RULESET_V1)
    findings = engine.detect(canonical_ds, reconstructed_ds, dq_result, uuid4())
    assert len(findings) == 1
    assert "CLAIM_EVIDENCE_CONFLICT" in findings[0].supporting_signals[0]

# 9. missing evidence with sufficient Data Trust
def test_missing_evidence_not_contradiction():
    cse, rep = create_base_entities()
    now = datetime.now(timezone.utc)
    alt_id = uuid4()
    
    canonical_ds = CanonicalDataset(dataset_version_id=uuid4())
    canonical_ds.cse_list = [cse]
    # Alert is open, case is missing entirely. This is missing evidence, NOT a contradiction of states (e.g., closed alert vs open case).
    canonical_ds.alerts = [Alert(
        alert_id=alt_id, cse_id=cse.cse_id, asset_id=uuid4(), reporting_period_id=rep.reporting_period_id,
        event_time=now, severity=Severity.MEDIUM, alert_category="Test", source="Test", status=AlertStatus.OPEN,
        dataset_version_id=uuid4(), ingest_time=now
    )]
    
    reconstructed_ds = ReconstructedDataset(canonical_ds)
    dq_result = DataQualityResult(
        dataset_version_id=uuid4(), score=1.0, 
        components=DataQualityComponents(completeness_ratio=1.0, consistency_ratio=1.0, coverage_ratio=1.0, sample_sufficiency_ratio=1.0),
        ruleset_version="V1", computed_at=now
    )
    
    engine = EvidenceContradictionEngine(DEFAULT_AUTHORITATIVE_RULESET_V1)
    findings = engine.detect(canonical_ds, reconstructed_ds, dq_result, uuid4())
    # Should be 0 contradiction findings because missing evidence isn't a contradiction.
    assert len(findings) == 0

# 10. low Data Trust
def test_low_data_trust():
    cse, rep = create_base_entities()
    now = datetime.now(timezone.utc)
    
    canonical_ds = CanonicalDataset(dataset_version_id=uuid4())
    canonical_ds.cse_list = [cse]
    
    reconstructed_ds = ReconstructedDataset(canonical_ds)
    dq_result = DataQualityResult(
        dataset_version_id=uuid4(), score=0.5, 
        components=DataQualityComponents(completeness_ratio=0.5, consistency_ratio=0.5, coverage_ratio=0.5, sample_sufficiency_ratio=0.5),
        ruleset_version="V1", computed_at=now
    )
    
    engine = EvidenceContradictionEngine(DEFAULT_AUTHORITATIVE_RULESET_V1)
    findings = engine.detect(canonical_ds, reconstructed_ds, dq_result, uuid4())
    assert len(findings) == 1
    assert findings[0].evidence_state.value == "INSUFFICIENT_EVIDENCE"

# 12. different CSE / 13. different reporting period
def test_different_cse_no_cross_pollution():
    cse1, rep1 = create_base_entities()
    cse2, rep2 = create_base_entities()
    now = datetime.now(timezone.utc)
    
    canonical_ds = CanonicalDataset(dataset_version_id=uuid4())
    canonical_ds.cse_list = [cse1, cse2]
    
    # CSE 1 has closed case
    canonical_ds.alerts.append(Alert(
        alert_id=uuid4(), cse_id=cse1.cse_id, asset_id=uuid4(), reporting_period_id=rep1.reporting_period_id,
        event_time=now, severity=Severity.MEDIUM, alert_category="Test", source="Test", status=AlertStatus.CLOSED,
        dataset_version_id=uuid4(), ingest_time=now
    ))
    
    # CSE 2 has open alert but it has nothing to do with CSE 1
    canonical_ds.alerts.append(Alert(
        alert_id=uuid4(), cse_id=cse2.cse_id, asset_id=uuid4(), reporting_period_id=rep2.reporting_period_id,
        event_time=now, severity=Severity.CRITICAL, alert_category="Test", source="Test", status=AlertStatus.OPEN,
        dataset_version_id=uuid4(), ingest_time=now
    ))
    
    # KPI claim on CSE 1 is very good
    canonical_ds.kpi_claims = [KPIClaim(
        claim_id=uuid4(), cse_id=cse1.cse_id, reporting_period_id=rep1.reporting_period_id,
        metric_name="Resolution Rate", reported_value=0.99, target_value=0.95,
        dataset_version_id=uuid4(), ingest_time=now
    )]
    
    reconstructed_ds = ReconstructedDataset(canonical_ds)
    dq_result = DataQualityResult(
        dataset_version_id=uuid4(), score=1.0, 
        components=DataQualityComponents(completeness_ratio=1.0, consistency_ratio=1.0, coverage_ratio=1.0, sample_sufficiency_ratio=1.0),
        ruleset_version="V1", computed_at=now
    )
    
    engine = EvidenceContradictionEngine(DEFAULT_AUTHORITATIVE_RULESET_V1)
    findings = engine.detect(canonical_ds, reconstructed_ds, dq_result, uuid4())
    # Should be 0 contradiction findings because the KPI is on CSE 1 but the open critical alert is on CSE 2.
    assert len(findings) == 0


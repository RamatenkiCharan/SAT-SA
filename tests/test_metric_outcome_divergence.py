import pytest
from uuid import uuid4
from datetime import datetime, timezone

from backend.models.canonical import (
    KPIClaim,
    Closure,
    Case,
    Alert,
    Severity,
    Asset,
    FindingType,
    EvidenceSufficiencyState,
    EvidenceRef
)
from analytics.canonicalization.canonicalization import CanonicalDataset
from analytics.workflow.workflow_reconstruction import ReconstructedDataset
from analytics.data_quality.quality_score import DataQualityResult, DataQualityComponents
from analytics.peer_benchmark.benchmarks import PeerBenchmarkEngine, PeerBenchmarkResult, CSEOperationalMetrics, MetricDistribution, PeerFallbackState
from analytics.kpi_integrity.outcome_divergence import MetricOutcomeDivergenceDetector
from backend.models.ruleset import AnalyticalRuleset, DetectorConfig

class MockPeerBenchmarkEngine:
    def __init__(self, metrics: dict):
        self._metrics = metrics
        self._bms = {}
        
    def get_benchmark_for_cse(self, cse_id):
        if cse_id not in self._metrics:
            return None
            
        if cse_id in self._bms:
            return self._bms[cse_id]
            
        m = self._metrics[cse_id]
        
        bm = PeerBenchmarkResult(
            peer_group_id=cse_id,
            sector="Power",
            scale="large",
            group_size=10,
            is_fallback_global=False,
            closure_duration_dist=MetricDistribution(median=3600.0, mad=600.0, p25=3000.0, p75=4200.0, count=10),
            evidence_count_dist=MetricDistribution(median=5.0, mad=1.0, p25=4.0, p75=6.0, count=10),
            escalation_ratio_dist=MetricDistribution(median=0.50, mad=0.10, p25=0.40, p75=0.60, count=10),
            cse_metrics={cse_id: m},
            fallback_state=PeerFallbackState.DIRECT
        )
        self._bms[cse_id] = bm
        return bm
        
    def compute_peer_deviation_zscore(self, cse_id, val, metric_name):
        bm = self.get_benchmark_for_cse(cse_id)
        if not bm: return 0.0
        
        if metric_name == "evidence_count":
            dist = bm.evidence_count_dist
        elif metric_name == "escalation_ratio":
            dist = bm.escalation_ratio_dist
        else:
            return 0.0
            
        if dist.mad < 1e-4: return 0.0
        return (val - dist.median) / dist.mad

@pytest.fixture
def base_setup():
    cse_id = uuid4()
    rep_id = uuid4()
    ver_id = uuid4()
    now = datetime.now(timezone.utc)
    
    ds = CanonicalDataset(dataset_version_id=ver_id, cse_list=[], reporting_periods=[], assets=[], alerts=[], investigations=[], cases=[], escalations=[], actions=[], closures=[], kpi_claims=[])
    ds.kpi_claims.append(KPIClaim(
        claim_id=uuid4(), cse_id=cse_id, reporting_period_id=rep_id, metric_name="SLA Compliance",
        reported_value=0.95, target_value=0.90, population="All", dataset_version_id=ver_id, ingest_time=now
    ))
    
    dq = DataQualityResult(
        dataset_version_id=ver_id, score=1.0,
        components=DataQualityComponents(1.0, 1.0, 1.0, 1.0),
        ruleset_version="V1",
        computed_at=now
    )
    from backend.models.ruleset import DEFAULT_AUTHORITATIVE_RULESET_V1
    detector = MetricOutcomeDivergenceDetector(ruleset=DEFAULT_AUTHORITATIVE_RULESET_V1)
    
    return ds, dq, detector, cse_id

def test_supported_improvement(base_setup):
    ds, dq, detector, cse_id = base_setup
    
    # Outcomes are good (above or near median)
    metrics = {
        cse_id: CSEOperationalMetrics(
            cse_id=cse_id, cse_name="Test", sector="Power", scale="large", total_alerts=100, critical_alerts_count=10,
            median_critical_closure_duration=3500.0, p25_critical_closure_duration=2000.0,
            median_evidence_count=5.0, p25_evidence_count=4.0, critical_escalation_ratio=0.50,
            repeat_alert_rate=0.10, sla_compliance_rate=0.95
        )
    }
    engine = MockPeerBenchmarkEngine(metrics)
    
    findings = detector.detect(ds, ReconstructedDataset(ds), dq, engine, uuid4())
    assert len(findings) == 0  # Supported, no divergence

def test_investigation_depth_divergence(base_setup):
    ds, dq, detector, cse_id = base_setup
    
    # Evidence count is abnormally low: median=5, mad=1. Val=3.0 -> Z=-2.0
    metrics = {
        cse_id: CSEOperationalMetrics(
            cse_id=cse_id, cse_name="Test", sector="Power", scale="large", total_alerts=100, critical_alerts_count=10,
            median_critical_closure_duration=3500.0, p25_critical_closure_duration=2000.0,
            median_evidence_count=3.0, p25_evidence_count=1.0, critical_escalation_ratio=0.50,
            repeat_alert_rate=0.10, sla_compliance_rate=0.95
        )
    }
    engine = MockPeerBenchmarkEngine(metrics)
    
    findings = detector.detect(ds, ReconstructedDataset(ds), dq, engine, uuid4())
    assert len(findings) == 1
    f = findings[0]
    assert f.finding_type == FindingType.METRIC_OUTCOME_DIVERGENCE
    assert "investigation depth" in f.observed_behavior

def test_escalation_divergence(base_setup):
    ds, dq, detector, cse_id = base_setup
    
    # Escalation ratio is abnormally low: median=0.50, mad=0.10. Val=0.20 -> Z=-3.0
    metrics = {
        cse_id: CSEOperationalMetrics(
            cse_id=cse_id, cse_name="Test", sector="Power", scale="large", total_alerts=100, critical_alerts_count=10,
            median_critical_closure_duration=3500.0, p25_critical_closure_duration=2000.0,
            median_evidence_count=5.0, p25_evidence_count=4.0, critical_escalation_ratio=0.20,
            repeat_alert_rate=0.10, sla_compliance_rate=0.95
        )
    }
    engine = MockPeerBenchmarkEngine(metrics)
    
    findings = detector.detect(ds, ReconstructedDataset(ds), dq, engine, uuid4())
    assert len(findings) == 1
    assert "escalation behavior" in findings[0].observed_behavior

def test_unresolved_divergence(base_setup):
    ds, dq, detector, cse_id = base_setup
    
    metrics = {
        cse_id: CSEOperationalMetrics(
            cse_id=cse_id, cse_name="Test", sector="Power", scale="large", total_alerts=100, critical_alerts_count=10,
            median_critical_closure_duration=3500.0, p25_critical_closure_duration=2000.0,
            median_evidence_count=5.0, p25_evidence_count=4.0, critical_escalation_ratio=0.50,
            repeat_alert_rate=0.40,  # > 0.30
            sla_compliance_rate=0.95
        )
    }
    engine = MockPeerBenchmarkEngine(metrics)
    
    findings = detector.detect(ds, ReconstructedDataset(ds), dq, engine, uuid4())
    assert len(findings) == 1
    assert "repeated unresolved rate" in findings[0].observed_behavior

def test_insufficient_evidence(base_setup):
    ds, dq, detector, cse_id = base_setup
    
    now = datetime.now(timezone.utc)
    dq_bad = DataQualityResult(
        dataset_version_id=dq.dataset_version_id, score=0.50,
        components=dq.components,
        ruleset_version="V1",
        computed_at=now
    )
    
    metrics = {
        cse_id: CSEOperationalMetrics(
            cse_id=cse_id, cse_name="Test", sector="Power", scale="large", total_alerts=100, critical_alerts_count=10,
            median_critical_closure_duration=3500.0, p25_critical_closure_duration=2000.0,
            median_evidence_count=2.0, p25_evidence_count=1.0, critical_escalation_ratio=0.10,
            repeat_alert_rate=0.50, sla_compliance_rate=0.95
        )
    }
    engine = MockPeerBenchmarkEngine(metrics)
    
    findings = detector.detect(ds, ReconstructedDataset(ds), dq_bad, engine, uuid4())
    assert len(findings) == 1
    assert findings[0].evidence_state == EvidenceSufficiencyState.INSUFFICIENT_EVIDENCE
    assert "Data Quality Score is 0.50" in findings[0].observed_behavior

def test_normal_operational_variation(base_setup):
    # Hard Negative E: KPI stable/improves + normal operational variation -> NO divergence
    ds, dq, detector, cse_id = base_setup
    
    # Z-score of -1.0 is normal variation, not divergence (threshold is -1.5)
    metrics = {
        cse_id: CSEOperationalMetrics(
            cse_id=cse_id, cse_name="Test", sector="Power", scale="large", total_alerts=100, critical_alerts_count=10,
            median_critical_closure_duration=3500.0, p25_critical_closure_duration=2000.0,
            median_evidence_count=4.0, p25_evidence_count=3.0, # Z = (4 - 5) / 1 = -1.0
            critical_escalation_ratio=0.40, # Z = (0.40 - 0.50) / 0.10 = -1.0
            repeat_alert_rate=0.10, sla_compliance_rate=0.95
        )
    }
    engine = MockPeerBenchmarkEngine(metrics)
    
    findings = detector.detect(ds, ReconstructedDataset(ds), dq, engine, uuid4())
    assert len(findings) == 0

def test_tiny_sample(base_setup):
    # Hard Negative H: tiny sample -> no strong divergence
    ds, dq, detector, cse_id = base_setup
    
    metrics = {
        cse_id: CSEOperationalMetrics(
            cse_id=cse_id, cse_name="Test", sector="Power", scale="large", total_alerts=100, critical_alerts_count=10,
            median_critical_closure_duration=3500.0, p25_critical_closure_duration=2000.0,
            median_evidence_count=2.0, p25_evidence_count=1.0, critical_escalation_ratio=0.10,
            repeat_alert_rate=0.10, sla_compliance_rate=0.95
        )
    }
    engine = MockPeerBenchmarkEngine(metrics)
    # Mock engine gives count=10 by default, let's override the count to 3
    bm = engine.get_benchmark_for_cse(cse_id)
    bm.evidence_count_dist.count = 3
    bm.escalation_ratio_dist.count = 3
    
    findings = detector.detect(ds, ReconstructedDataset(ds), dq, engine, uuid4())
    assert len(findings) == 0

def test_deterioration_without_kpi_improvement(base_setup):
    # Hard Negative L: operational deterioration without KPI improvement -> NO divergence
    ds, dq, detector, cse_id = base_setup
    
    # Make KPI fail target (reported=0.80, target=0.90)
    ds.kpi_claims[0].reported_value = 0.80
    
    metrics = {
        cse_id: CSEOperationalMetrics(
            cse_id=cse_id, cse_name="Test", sector="Power", scale="large", total_alerts=100, critical_alerts_count=10,
            median_critical_closure_duration=3500.0, p25_critical_closure_duration=2000.0,
            median_evidence_count=1.0, p25_evidence_count=1.0, critical_escalation_ratio=0.10,
            repeat_alert_rate=0.50, sla_compliance_rate=0.80
        )
    }
    engine = MockPeerBenchmarkEngine(metrics)
    
    findings = detector.detect(ds, ReconstructedDataset(ds), dq, engine, uuid4())
    assert len(findings) == 0  # Should skip because KPI did not improve/meet target


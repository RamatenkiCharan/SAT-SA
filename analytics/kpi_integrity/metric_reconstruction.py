import logging
from typing import Optional
from backend.models.canonical import Finding, FindingType, Severity, KPIClaim, EvidenceRef
from backend.models.ruleset import AnalyticalRuleset
from analytics.canonicalization.canonicalization import CanonicalDataset
from analytics.workflow.workflow_reconstruction import ReconstructedDataset
from analytics.data_quality.quality_score import DataQualityResult

logger = logging.getLogger("satsa.kpi_integrity")

class MetricReconstructionEngine:
    """
    Reconstructs true operational metrics from the canonical dataset.
    """
    def __init__(self, canonical_ds: CanonicalDataset, reconstructed_ds: ReconstructedDataset):
        self.canonical_ds = canonical_ds
        self.reconstructed_ds = reconstructed_ds

    def calculate_sla_compliance(self, target_minutes: float, claim: KPIClaim) -> tuple[float, list[str]]:
        """
        Calculates SLA compliance from canonical closures that belong to the claim's scope.
        Returns (compliance_ratio, [evidence_source_refs]).
        """
        if not self.canonical_ds.closures:
            return 0.0, []

        compliant_count = 0
        total_count = 0
        evidence_refs = []

        # In SAT-SA, closure duration is calculated from alert event time to closed_at.
        # We need to join closures with cases, and cases with alerts.
        alert_map = {a.alert_id: a for a in self.canonical_ds.alerts}
        case_map = {c.case_id: c for c in self.canonical_ds.cases}
        
        for clo in self.canonical_ds.closures:
            case = case_map.get(clo.case_id)
            if not case:
                continue
                
            alert = alert_map.get(case.alert_id)
            if not alert:
                continue
                
            # Filter by entity scope and reporting period
            if alert.cse_id != claim.cse_id or alert.reporting_period_id != claim.reporting_period_id:
                continue
                
            if clo.source_record_ref:
                evidence_refs.append(clo.source_record_ref)
                
            total_count += 1
            duration_delta = clo.closed_at - alert.event_time
            duration_minutes = duration_delta.total_seconds() / 60.0
            
            if duration_minutes <= target_minutes:
                compliant_count += 1
                
        if total_count == 0:
            return 0.0, evidence_refs
            
        return compliant_count / total_count, evidence_refs

    def reconstruct_metric(self, claim: KPIClaim) -> tuple[Optional[float], list[str]]:
        """
        Returns the reconstructed metric value and the evidence refs.
        Currently supports 'SLA Compliance' and similar strings.
        """
        name_lower = claim.metric_name.lower()
        if "sla" in name_lower or "compliance" in name_lower:
            # We assume a default SLA target of 60 minutes if not specified, 
            # though it should ideally be parameterized by ruleset/peer-group.
            # Usually target_value contains the target SLA e.g. 0.95 (95%), 
            # but we need the target minutes to calculate compliance.
            # If target_value is not minutes, we use 60.
            target_minutes = 60.0 
            return self.calculate_sla_compliance(target_minutes, claim)
            
        return None, []

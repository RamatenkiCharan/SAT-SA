from uuid import UUID, uuid4
from datetime import datetime, timezone

from backend.models.canonical import Finding, FindingType, EvidenceSufficiencyState, EvidenceRef, DataQualityScore, ExpectationBasis
from analytics.canonicalization.canonicalization import CanonicalDataset
from analytics.workflow.workflow_reconstruction import ReconstructedDataset
from analytics.data_quality.quality_score import DataQualityResult
from analytics.peer_benchmark.benchmarks import PeerBenchmarkEngine
from backend.models.ruleset import AnalyticalRuleset

class MetricOutcomeDivergenceDetector:
    """
    INNOVATION PHASE 2: METRIC-OUTCOME DIVERGENCE
    Evaluates whether the underlying operational behavior moves consistently 
    with the improvement represented by the KPI.
    """
    def __init__(self, ruleset: AnalyticalRuleset):
        self.ruleset = ruleset

    def detect(
        self,
        canonical_ds: CanonicalDataset,
        reconstructed_ds: ReconstructedDataset,
        dq_result: DataQualityResult,
        benchmark_engine: PeerBenchmarkEngine,
        analysis_run_id: UUID,
    ) -> list[Finding]:
        findings = []
        now = datetime.now(timezone.utc)
        
        # Determine DataQualityScore value
        dq_status = DataQualityScore(
            dataset_version_id=dq_result.dataset_version_id,
            score=dq_result.score,
            components={
                "completeness_ratio": dq_result.components.completeness_ratio,
                "consistency_ratio": dq_result.components.consistency_ratio,
                "coverage_ratio": dq_result.components.coverage_ratio,
                "sample_sufficiency_ratio": dq_result.components.sample_sufficiency_ratio
            },
            ruleset_version=dq_result.ruleset_version,
            computed_at=dq_result.computed_at
        )
            
        # 1. Data Trust gating
        if dq_result.score < 0.6:
            for claim in canonical_ds.kpi_claims:
                target = claim.target_value if claim.target_value is not None else 0.90
                is_positive = False
                if claim.metric_name in ["Mean Time To Resolve", "Repeat Alert Rate"]:
                    is_positive = claim.reported_value <= target
                else:
                    is_positive = claim.reported_value >= target
                    
                if is_positive:
                    f = Finding(
                        finding_id=uuid4(),
                        cse_id=claim.cse_id,
                        reporting_period_id=claim.reporting_period_id,
                        dataset_version_id=canonical_ds.dataset_version_id,
                        analysis_run_id=analysis_run_id,
                        finding_type=FindingType.METRIC_OUTCOME_DIVERGENCE,
                        priority_score=0.8,
                        priority_components={"SignalStrength": 0.8, "PeerDeviation": 0.0, "Persistence": 0.0, "AssetCriticality": 0.0, "DataUncertainty": 1.0},
                        evidentiary_confidence=0.0,
                        data_quality_status=dq_status,
                        expectation_basis=ExpectationBasis.HARD_REQUIREMENT,
                        expected_behavior="Data Quality Score >= 0.6 to reliably evaluate operational outcomes against KPI claims.",
                        observed_behavior=f"Data Quality Score is {dq_result.score:.2f}.",
                        supporting_signals=["Data Trust insufficient for behavioral comparison."],
                        evidence_refs=[EvidenceRef(entity_id=claim.claim_id, entity_type="KPIClaim")],
                        evidence_state=EvidenceSufficiencyState.INSUFFICIENT_EVIDENCE,
                        analytical_method="Metric-Outcome Divergence Engine",
                        ruleset_version=self.ruleset.version,
                        computed_at=now,
                        created_at=now
                    )
                    findings.append(f)
            return findings

        # 2. Proceed with behavior baseline comparison
        for claim in canonical_ds.kpi_claims:
            target = claim.target_value if claim.target_value is not None else 0.90
            
            is_positive_claim = False
            if claim.metric_name in ["Mean Time To Resolve", "Repeat Alert Rate"]:
                is_positive_claim = claim.reported_value <= target
            else:
                is_positive_claim = claim.reported_value >= target
                
            if not is_positive_claim:
                continue
                
            cse_id = claim.cse_id
            bm = benchmark_engine.get_benchmark_for_cse(cse_id)
            if not bm:
                continue
                
            cse_metrics = bm.cse_metrics.get(cse_id)
            if not cse_metrics:
                continue

            # Check divergence in outcomes
            ev_dist = bm.evidence_count_dist
            ev_val = cse_metrics.median_evidence_count
            ev_z = benchmark_engine.compute_peer_deviation_zscore(cse_id, ev_val, "evidence_count")
            
            esc_dist = bm.escalation_ratio_dist
            esc_val = cse_metrics.critical_escalation_ratio
            esc_z = benchmark_engine.compute_peer_deviation_zscore(cse_id, esc_val, "escalation_ratio")

            repeat_rate = cse_metrics.repeat_alert_rate

            divergences = []
            signals = []
            
            if ev_z <= -1.5 and ev_dist.count >= 5:
                divergences.append("investigation depth")
                signals.append(f"Median evidence count {ev_val:.1f} is abnormally low vs peer median {ev_dist.median:.1f} (Z={ev_z:.2f})")
                
            if esc_z <= -1.5 and esc_dist.count >= 5:
                divergences.append("escalation behavior")
                signals.append(f"Critical escalation ratio {esc_val:.2f} is abnormally low vs peer median {esc_dist.median:.2f} (Z={esc_z:.2f})")
                
            if repeat_rate > 0.30: 
                divergences.append("repeated unresolved rate")
                signals.append(f"Repeat alert rate is highly elevated at {repeat_rate*100:.1f}%")
                
            if not divergences:
                continue
                
            div_str = ", ".join(divergences)
            desc = f"Reported {claim.metric_name} meets/exceeds target ({claim.reported_value}), but operational outcomes ({div_str}) have deteriorated relative to peer baseline."
            
            refs = [EvidenceRef(entity_id=claim.claim_id, entity_type="KPIClaim")]
            
            # Find an example workflow that exhibits the poor outcome to attach as evidence
            workflows = reconstructed_ds.get_workflows_for_cse(cse_id)
            example_wfs = []
            if "investigation depth" in divergences:
                # Find a fast/shallow closure
                shallow = [w for w in workflows if w.evidence_count <= ev_dist.p25]
                if shallow:
                    example_wfs.extend(shallow[:2])
            if "escalation behavior" in divergences:
                # Find a critical without escalation
                no_esc = [w for w in workflows if w.alert and w.alert.severity.value in ["CRITICAL", "HIGH"] and not w.has_escalation]
                if no_esc:
                    example_wfs.extend(no_esc[:2])
            if "repeated unresolved rate" in divergences:
                # Just take any alert from a repeat sequence (simplified, just grab any case)
                example_wfs.extend(workflows[:1])
                
            for w in example_wfs[:5]: # cap at 5
                if w.alert:
                    refs.append(EvidenceRef(entity_id=w.alert.alert_id, entity_type="Alert"))
                if w.case:
                    refs.append(EvidenceRef(entity_id=w.case.case_id, entity_type="Case"))
            
            # De-duplicate refs
            seen = set()
            unique_refs = []
            for r in refs:
                if r.entity_id not in seen:
                    unique_refs.append(r)
                    seen.add(r.entity_id)

            finding = Finding(
                finding_id=uuid4(),
                cse_id=cse_id,
                reporting_period_id=claim.reporting_period_id,
                dataset_version_id=canonical_ds.dataset_version_id,
                analysis_run_id=analysis_run_id,
                finding_type=FindingType.METRIC_OUTCOME_DIVERGENCE,
                priority_score=0.9,
                priority_components={"SignalStrength": 0.9, "PeerDeviation": 1.0, "Persistence": 0.5, "AssetCriticality": 0.5, "DataUncertainty": 0.1},
                evidentiary_confidence=0.9,
                data_quality_status=dq_status,
                expectation_basis=ExpectationBasis.STATISTICAL_BASELINE,
                expected_behavior=f"Operational outcomes should remain stable or improve alongside {claim.metric_name}.",
                observed_behavior=f"Outcome metrics ({div_str}) are diverging negatively while KPI improves.",
                supporting_signals=signals,
                evidence_refs=unique_refs,
                evidence_state=EvidenceSufficiencyState.SUPPORTED,
                analytical_method="Metric-Outcome Divergence Engine",
                ruleset_version=self.ruleset.version,
                computed_at=now,
                created_at=now
            )
            findings.append(finding)
            
        return findings

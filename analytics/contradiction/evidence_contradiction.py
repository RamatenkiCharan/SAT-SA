from uuid import UUID, uuid4
from datetime import datetime, timezone

from backend.models.canonical import Finding, FindingType, EvidenceSufficiencyState, EvidenceRef, DataQualityScore, ExpectationBasis
from analytics.canonicalization.canonicalization import CanonicalDataset
from analytics.workflow.workflow_reconstruction import ReconstructedDataset
from analytics.data_quality.quality_score import DataQualityResult
from backend.models.ruleset import AnalyticalRuleset

class EvidenceContradictionEngine:
    """
    INNOVATION PHASE 3: EVIDENCE CONTRADICTION ENGINE
    Detects situations where different canonical records, workflow stages, claims, 
    or operational artifacts imply incompatible states.
    """
    def __init__(self, ruleset: AnalyticalRuleset):
        self.ruleset = ruleset

    def detect(
        self,
        canonical_ds: CanonicalDataset,
        reconstructed_ds: ReconstructedDataset,
        dq_result: DataQualityResult,
        analysis_run_id: UUID,
    ) -> list[Finding]:
        findings = []
        now = datetime.now(timezone.utc)
        
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

        # 1. Gate on Data Trust
        if dq_result.score < 0.6:
            for cse in canonical_ds.cse_list:
                f = Finding(
                    finding_id=uuid4(),
                    cse_id=cse.cse_id,
                    reporting_period_id=cse.reporting_period_id,
                    dataset_version_id=canonical_ds.dataset_version_id,
                    analysis_run_id=analysis_run_id,
                    finding_type=FindingType.EVIDENCE_CONTRADICTION,
                    priority_score=0.8,
                    priority_components={"SignalStrength": 0.8, "PeerDeviation": 0.0, "Persistence": 0.0, "AssetCriticality": 0.0, "DataUncertainty": 1.0},
                    evidentiary_confidence=0.0,
                    data_quality_status=dq_status,
                    expectation_basis=ExpectationBasis.HARD_REQUIREMENT,
                    expected_behavior="High data quality is required to evaluate evidence contradictions.",
                    observed_behavior=f"Data Quality Score is {dq_result.score:.2f}, insufficient to establish contradiction vs missing data.",
                    supporting_signals=["Data Trust insufficient for contradiction analysis."],
                    evidence_refs=[],
                    evidence_state=EvidenceSufficiencyState.INSUFFICIENT_EVIDENCE,
                    analytical_method="Evidence Contradiction Engine",
                    ruleset_version=self.ruleset.version,
                    computed_at=now,
                    created_at=now
                )
                findings.append(f)
            return findings

        # 2. Evaluate Workflows for Contradictions
        for wf in reconstructed_ds.workflows:
            contradictions = []
            refs = []

            # LIFECYCLE_CONFLICT: Alert CLOSED but Case OPEN
            if wf.alert and wf.alert.status.value == "CLOSED":
                if wf.case and wf.case.closed_at is None:
                    contradictions.append({
                        "type": "LIFECYCLE_CONFLICT",
                        "expected": "Alert and Case closure states should align.",
                        "observed": "Alert is CLOSED but corresponding Case remains OPEN.",
                        "refs": [
                            EvidenceRef(entity_id=wf.alert.alert_id, entity_type="Alert"),
                            EvidenceRef(entity_id=wf.case.case_id, entity_type="Case")
                        ]
                    })
            
            # ESCALATION_CONFLICT: Alert ESCALATED but no escalation record
            if wf.alert and wf.alert.status.value == "ESCALATED":
                if not wf.has_escalation:
                    contradictions.append({
                        "type": "ESCALATION_CONFLICT",
                        "expected": "ESCALATED alert must have a corresponding escalation record.",
                        "observed": "Alert status is ESCALATED, but no escalation record exists.",
                        "refs": [
                            EvidenceRef(entity_id=wf.alert.alert_id, entity_type="Alert")
                        ]
                    })
            
            # RESPONSE_STATE_CONFLICT: Action COMPLETED but Case OPEN
            if wf.has_remediation_action and wf.case and wf.case.closed_at is None:
                contradictions.append({
                    "type": "RESPONSE_STATE_CONFLICT",
                    "expected": "Completed response actions should eventually lead to case closure or resolution.",
                    "observed": "Response action performed, but associated case remains operationally unresolved (OPEN).",
                    "refs": [
                        EvidenceRef(entity_id=wf.actions[0].action_id, entity_type="Action"),
                        EvidenceRef(entity_id=wf.case.case_id, entity_type="Case")
                    ]
                })

            for c_info in contradictions:
                seen = set()
                unique_refs = []
                for r in c_info["refs"]:
                    if r.entity_id not in seen:
                        unique_refs.append(r)
                        seen.add(r.entity_id)

                f = Finding(
                    finding_id=uuid4(),
                    cse_id=wf.alert.cse_id,
                    reporting_period_id=wf.alert.reporting_period_id,
                    dataset_version_id=canonical_ds.dataset_version_id,
                    analysis_run_id=analysis_run_id,
                    finding_type=FindingType.EVIDENCE_CONTRADICTION,
                    priority_score=0.9,
                    priority_components={"SignalStrength": 0.9, "PeerDeviation": 0.0, "Persistence": 0.8, "AssetCriticality": 0.5, "DataUncertainty": 0.1},
                    evidentiary_confidence=0.95,
                    data_quality_status=dq_status,
                    expectation_basis=ExpectationBasis.HARD_REQUIREMENT,
                    expected_behavior=c_info["expected"],
                    observed_behavior=c_info["observed"],
                    supporting_signals=[
                        f"Contradiction Type: {c_info['type']}",
                        "The operational records describe incompatible lifecycle states."
                    ],
                    evidence_refs=unique_refs,
                    evidence_state=EvidenceSufficiencyState.SUPPORTED,
                    analytical_method="Evidence Contradiction Engine",
                    ruleset_version=self.ruleset.version,
                    computed_at=now,
                    created_at=now
                )
                findings.append(f)

        # 3. CLAIM_EVIDENCE_CONFLICT
        for claim in canonical_ds.kpi_claims:
            target = claim.target_value if claim.target_value is not None else 0.90
            is_positive_claim = False
            if claim.metric_name in ["Mean Time To Resolve", "Repeat Alert Rate"]:
                is_positive_claim = claim.reported_value <= target
            else:
                is_positive_claim = claim.reported_value >= target
            
            if is_positive_claim:
                cse_wfs = reconstructed_ds.get_workflows_for_cse(claim.cse_id)
                open_criticals = [
                    w for w in cse_wfs 
                    if w.case and w.case.closed_at is None and w.alert and w.alert.severity.value in ["CRITICAL", "HIGH"]
                ]

                if open_criticals:
                    refs = [EvidenceRef(entity_id=claim.claim_id, entity_type="KPIClaim")]
                    for w in open_criticals[:3]:
                        refs.append(EvidenceRef(entity_id=w.case.case_id, entity_type="Case"))
                    
                    f = Finding(
                        finding_id=uuid4(),
                        cse_id=claim.cse_id,
                        reporting_period_id=claim.reporting_period_id,
                        dataset_version_id=canonical_ds.dataset_version_id,
                        analysis_run_id=analysis_run_id,
                        finding_type=FindingType.EVIDENCE_CONTRADICTION,
                        priority_score=0.95,
                        priority_components={"SignalStrength": 1.0, "PeerDeviation": 0.0, "Persistence": 0.9, "AssetCriticality": 0.9, "DataUncertainty": 0.1},
                        evidentiary_confidence=0.95,
                        data_quality_status=dq_status,
                        expectation_basis=ExpectationBasis.HARD_REQUIREMENT,
                        expected_behavior=f"Operational records should align with KPI claim ('{claim.metric_name}' is healthy).",
                        observed_behavior="KPI claim reports healthy resolution, but critical cases remain open operationally.",
                        supporting_signals=[
                            "Contradiction Type: CLAIM_EVIDENCE_CONFLICT",
                            f"Claimed {claim.metric_name} = {claim.reported_value}, but {len(open_criticals)} critical/high cases are OPEN."
                        ],
                        evidence_refs=refs,
                        evidence_state=EvidenceSufficiencyState.SUPPORTED,
                        analytical_method="Evidence Contradiction Engine",
                        ruleset_version=self.ruleset.version,
                        computed_at=now,
                        created_at=now
                    )
                    findings.append(f)

        return findings

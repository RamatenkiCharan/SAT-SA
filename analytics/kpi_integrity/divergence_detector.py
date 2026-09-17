import logging
from uuid import uuid4, UUID
from datetime import datetime, timezone
from typing import Optional

from backend.models.canonical import (
    Finding,
    FindingType,
    Severity,
    EvidenceRef,
    EvidenceSufficiencyState,
    ExpectationBasis,
)
from backend.models.ruleset import AnalyticalRuleset
from analytics.canonicalization.canonicalization import CanonicalDataset
from analytics.workflow.workflow_reconstruction import ReconstructedDataset
from analytics.data_quality.quality_score import DataQualityResult
from analytics.kpi_integrity.metric_reconstruction import MetricReconstructionEngine

logger = logging.getLogger("satsa.kpi_integrity")

class ClaimEvidenceDivergenceDetector:
    """
    Detects divergence between SOC-reported KPI claims and the operationally reconstructed metrics.
    Enforces Data Trust prerequisites.
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
        findings: list[Finding] = []
        if not canonical_ds.kpi_claims:
            return findings

        engine = MetricReconstructionEngine(canonical_ds, reconstructed_ds)
        now = datetime.now(timezone.utc)

        for claim in canonical_ds.kpi_claims:
            # Reconstruct metric
            reconstructed_val, evidence_refs = engine.reconstruct_metric(claim)
            
            if reconstructed_val is None:
                # We couldn't reconstruct this metric type (not supported)
                continue
                
            reported_val = claim.reported_value
            
            # 1. Enforce Data Trust Prerequisite
            if dq_result.score < 0.6:
                # Do not produce strong divergence conclusions if DQ is low.
                findings.append(
                    self._create_insufficient_evidence_finding(
                        claim, reported_val, dq_result, analysis_run_id, canonical_ds.dataset_version_id, now
                    )
                )
                continue
                
            # 2. Check for divergence
            # E.g., reported 0.99, reconstructed 0.85 -> Delta 0.14
            # We use an absolute threshold for now (e.g. 5% divergence)
            divergence = abs(reported_val - reconstructed_val)
            threshold = 0.05
            
            if divergence > threshold:
                # Divergence detected!
                finding = self._create_divergence_finding(
                    claim,
                    reported_val,
                    reconstructed_val,
                    evidence_refs,
                    dq_result,
                    analysis_run_id,
                    canonical_ds.dataset_version_id,
                    now,
                )
                findings.append(finding)

        return findings

    def _create_insufficient_evidence_finding(
        self,
        claim,
        reported_val: float,
        dq_result: DataQualityResult,
        analysis_run_id: UUID,
        dataset_version_id: UUID,
        now: datetime,
    ) -> Finding:
        from backend.models.canonical import DataQualityScore, DataQualityComponents
        
        dq_score_model = DataQualityScore(
            dataset_version_id=dataset_version_id,
            score=dq_result.score,
            components=DataQualityComponents(
                completeness_ratio=dq_result.components.completeness_ratio,
                consistency_ratio=dq_result.components.consistency_ratio,
                coverage_ratio=dq_result.components.coverage_ratio,
                sample_sufficiency_ratio=dq_result.components.sample_sufficiency_ratio,
            ),
            ruleset_version=self.ruleset.version,
            computed_at=now
        )
        
        return Finding(
            finding_id=uuid4(),
            cse_id=claim.cse_id,
            reporting_period_id=claim.reporting_period_id,
            finding_type=FindingType.SUPERVISORY_DIVERGENCE,
            priority_score=0.0,
            priority_components={},
            evidentiary_confidence=0.0,
            data_quality_status=dq_score_model,
            expectation_basis=ExpectationBasis.CONFIGURED_EXPECTATION,
            expected_behavior=f"Data Quality Score >= 0.6 for verifiable {claim.metric_name} claims.",
            observed_behavior=f"Data Quality Score is {dq_result.score:.2f}.",
            supporting_signals=[f"DQ Completeness: {dq_result.components.completeness_ratio:.2f}"],
            evidence_refs=[EvidenceRef(entity_id=claim.claim_id, entity_type="KPIClaim")],
            evidence_state=EvidenceSufficiencyState.INSUFFICIENT_EVIDENCE,
            analytical_method="Claim-Evidence Integrity Engine",
            ruleset_version=self.ruleset.version,
            dataset_version_id=dataset_version_id,
            analysis_run_id=analysis_run_id,
            created_at=now,
        )

    def _create_divergence_finding(
        self,
        claim,
        reported_val: float,
        reconstructed_val: float,
        evidence_source_refs: list[str],
        dq_result: DataQualityResult,
        analysis_run_id: UUID,
        dataset_version_id: UUID,
        now: datetime,
    ) -> Finding:
        from backend.models.canonical import DataQualityScore, DataQualityComponents
        
        dq_score_model = DataQualityScore(
            dataset_version_id=dataset_version_id,
            score=dq_result.score,
            components=DataQualityComponents(
                completeness_ratio=dq_result.components.completeness_ratio,
                consistency_ratio=dq_result.components.consistency_ratio,
                coverage_ratio=dq_result.components.coverage_ratio,
                sample_sufficiency_ratio=dq_result.components.sample_sufficiency_ratio,
            ),
            ruleset_version=self.ruleset.version,
            computed_at=now
        )
        
        refs = [EvidenceRef(entity_id=claim.claim_id, entity_type="KPIClaim")]
        
        # We cap the number of evidence references so it doesn't get too large.
        max_refs = 10
        for i, source_ref in enumerate(evidence_source_refs[:max_refs]):
            refs.append(EvidenceRef(entity_id=uuid4(), entity_type="Closure"))
            
        return Finding(
            finding_id=uuid4(),
            cse_id=claim.cse_id,
            reporting_period_id=claim.reporting_period_id,
            finding_type=FindingType.SUPERVISORY_DIVERGENCE,
            priority_score=0.85,
            priority_components={"divergence_delta": abs(reported_val - reconstructed_val)},
            evidentiary_confidence=0.9,
            data_quality_status=dq_score_model,
            expectation_basis=ExpectationBasis.CONFIGURED_EXPECTATION,
            expected_behavior=f"Reconstructed {claim.metric_name} should closely match reported {reported_val:.1%}.",
            observed_behavior=f"Reconstructed value is {reconstructed_val:.1%}, diverging by {abs(reported_val - reconstructed_val):.1%}.",
            supporting_signals=[
                f"Reconstructed Value: {reconstructed_val:.1%}",
                f"Evaluated Closures: {len(evidence_source_refs)}",
            ],
            evidence_refs=refs,
            evidence_state=EvidenceSufficiencyState.SUPPORTED,
            analytical_method="Claim-Evidence Integrity Engine",
            ruleset_version=self.ruleset.version,
            dataset_version_id=dataset_version_id,
            analysis_run_id=analysis_run_id,
            created_at=now,
        )

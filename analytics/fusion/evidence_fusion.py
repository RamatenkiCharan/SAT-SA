"""
Evidence Fusion & Priority Scoring Engine (SRS §10.5).
Combines multi-detector signals, peer deviations, temporal persistence, asset criticalities,
and data quality uncertainties into decomposed priority scores.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from analytics.data_quality.quality_score import DataQualityResult
from analytics.execution_gap.escalation_gap import EscalationGapSignal
from analytics.execution_gap.fast_closure import FastClosureSignal
from analytics.execution_gap.repeated_unresolved import RepeatedUnresolvedSignal
from analytics.negative_space.coverage_gap import CoverageGapSignal
from backend.models.canonical import (
    AssetCriticality,
    DataQualityComponents,
    DataQualityScore,
    EvidenceRef,
    EvidenceSufficiencyState,
    ExpectationBasis,
    Finding,
    FindingType,
)
from backend.models.ruleset import (
    DEFAULT_AUTHORITATIVE_RULESET_V1,
    AnalyticalRuleset,
    FusionWeights,
    PriorityThresholds,
)

# Safe fallback derived from authoritative baseline ruleset
_FALLBACK_FUSION_WEIGHTS = DEFAULT_AUTHORITATIVE_RULESET_V1.fusion_weights.to_dict()
_FALLBACK_THRESHOLDS = DEFAULT_AUTHORITATIVE_RULESET_V1.thresholds


@dataclass
class FusionInputs:
    """
    Inputs to the 5-component Evidence Fusion priority scoring formula (SRS §10.5).
      T: Trigger / Signal Strength / Detection Count (signal_count)
      D: Peer Deviation (|z-score|)
      B: Baseline Persistence / Temporal Recurrence Ratio (0-1)
      C: Asset Criticality Tier (CRITICAL/HIGH/MEDIUM/LOW)
      A: Accuracy / Data Uncertainty (1 - DataQualityScore)
    """
    signal_count: int
    max_peer_zscore: float
    persistence_ratio: float
    asset_criticality_tier: str
    data_quality_score: float


def calculate_priority_components(
    inputs: FusionInputs,
    weights: dict[str, Any] | FusionWeights | None = None,
    ruleset: AnalyticalRuleset | None = None,
) -> tuple[float, dict[str, float]]:
    """
    Computes the 5-component Evidence Fusion priority score (SRS v2.0 §10.5).

    Formula:
      Priority Score = (w_T * norm_T) + (w_D * norm_D) + (w_B * norm_B) + (w_C * norm_C) + (w_A * norm_A)

    Where authoritative V1 weights from ruleset are:
      w_T = 0.30 (Signal Strength)
      w_D = 0.25 (Peer Deviation)
      w_B = 0.20 (Persistence)
      w_C = 0.15 (Asset Criticality)
      w_A = -0.10 (Data Uncertainty)
    """
    if ruleset is not None:
        w = ruleset.fusion_weights.to_dict()
    elif isinstance(weights, FusionWeights):
        w = weights.to_dict()
    elif isinstance(weights, dict):
        w = weights
    else:
        w = _FALLBACK_FUSION_WEIGHTS

    # 1. T: Signal strength / Detection count (normalized by signal_strength_cap, default 3)
    cap_sig = w.get("signal_strength_cap", 3)
    norm_T = min(inputs.signal_count / max(cap_sig, 1), 1.0)

    # 2. D: Peer deviation (normalized |z-score| by peer_deviation_zscore_cap, default 3.0)
    cap_z = w.get("peer_deviation_zscore_cap", 3.0)
    norm_D = min(abs(inputs.max_peer_zscore) / max(cap_z, 0.1), 1.0)

    # 3. B: Baseline Persistence / Temporal Recurrence (normalized 0-1)
    norm_B = max(0.0, min(1.0, inputs.persistence_ratio))

    # 4. C: Asset Criticality (normalized 0-1)
    crit_map = {
        "CRITICAL": 1.0,
        "HIGH": 0.75,
        "MEDIUM": 0.5,
        "LOW": 0.25,
    }
    norm_C = crit_map.get(inputs.asset_criticality_tier.upper(), 0.5)

    # 5. A: Accuracy / Data Uncertainty (1 - DataQualityScore, normalized 0-1)
    norm_A = max(0.0, 1.0 - inputs.data_quality_score)

    w_T = float(w.get("signal_strength_weight", 0.30))
    w_D = float(w.get("peer_deviation_weight", 0.25))
    w_B = float(w.get("persistence_weight", 0.20))
    w_C = float(w.get("asset_criticality_weight", 0.15))
    w_A = float(w.get("data_uncertainty_weight", -0.10))

    raw_score = (
        w_T * norm_T
        + w_D * norm_D
        + w_B * norm_B
        + w_C * norm_C
        + w_A * norm_A
    )
    final_score = max(0.0, min(1.0, raw_score))

    components = {
        # Symbolic components (T, D, B, C, A)
        "T": round(norm_T, 4),
        "D": round(norm_D, 4),
        "B": round(norm_B, 4),
        "C": round(norm_C, 4),
        "A": round(norm_A, 4),
        # Descriptive component aliases
        "signal_strength": round(norm_T, 4),
        "peer_deviation": round(norm_D, 4),
        "persistence": round(norm_B, 4),
        "asset_criticality": round(norm_C, 4),
        "data_uncertainty": round(norm_A, 4),
        # Summary & Weights for complete auditability
        "raw_score": round(raw_score, 4),
        "fused_score": round(final_score, 4),
        "w_T": w_T,
        "w_D": w_D,
        "w_B": w_B,
        "w_C": w_C,
        "w_A": w_A,
    }

    return final_score, components


def compute_priority_tier(
    priority_score: float,
    independent_signals_count: int,
    data_quality_score: float,
    thresholds: PriorityThresholds | dict[str, Any] | None = None,
    evidence_state: EvidenceSufficiencyState | None = None,
) -> tuple[str, dict[str, Any]]:
    """
    Computes priority label ('HIGH', 'MEDIUM', 'LOW') strictly AFTER fusion.
    Explicitly checks thresholds:
      - HIGH: score >= high_priority_score_threshold (0.75)
              AND independent_signals >= min_signals (2)
              AND data_quality >= min_dq (0.60)
              AND evidence_state != NOT_ASSESSABLE
      - MEDIUM: score >= medium_priority_score_threshold (0.50)
      - LOW: score < 0.50
    """
    if isinstance(thresholds, PriorityThresholds):
        th = thresholds
    elif isinstance(thresholds, dict):
        th = PriorityThresholds.from_dict(thresholds)
    else:
        th = _FALLBACK_THRESHOLDS

    high_th = th.high_priority_score_threshold
    med_th = th.medium_priority_score_threshold
    min_sig = th.high_priority_min_independent_signals
    min_dq = th.high_priority_min_data_quality

    is_score_high = priority_score >= high_th
    is_signals_sufficient = independent_signals_count >= min_sig
    is_dq_sufficient = data_quality_score >= min_dq
    is_state_assessable = (evidence_state != EvidenceSufficiencyState.NOT_ASSESSABLE)

    gating_details = {
        "priority_score": round(priority_score, 4),
        "high_priority_threshold": high_th,
        "medium_priority_threshold": med_th,
        "min_independent_signals": min_sig,
        "observed_independent_signals": independent_signals_count,
        "min_data_quality": min_dq,
        "observed_data_quality": round(data_quality_score, 4),
        "evidence_state": evidence_state.value if evidence_state else "SUPPORTED",
        "high_priority_gating_passed": is_score_high and is_signals_sufficient and is_dq_sufficient and is_state_assessable,
    }

    if is_score_high and is_signals_sufficient and is_dq_sufficient and is_state_assessable:
        label = "HIGH"
    elif priority_score >= med_th:
        label = "MEDIUM"
    else:
        label = "LOW"

    return label, gating_details


def reconstruct_finding_fusion(
    finding: Finding,
    ruleset: AnalyticalRuleset | None = None,
) -> dict[str, Any]:
    """
    Mathematical verification & reconstruction of a finding's fusion score, priority label,
    threshold compliance, and supporting evidence linkage.
    """
    comps = finding.priority_components
    w_T = comps.get("w_T", 0.30)
    w_D = comps.get("w_D", 0.25)
    w_B = comps.get("w_B", 0.20)
    w_C = comps.get("w_C", 0.15)
    w_A = comps.get("w_A", -0.10)

    T = comps.get("T", comps.get("signal_strength", 0.0))
    D = comps.get("D", comps.get("peer_deviation", 0.0))
    B = comps.get("B", comps.get("persistence", 0.0))
    C = comps.get("C", comps.get("asset_criticality", 0.0))
    A = comps.get("A", comps.get("data_uncertainty", 0.0))

    reconstructed_raw = (w_T * T) + (w_D * D) + (w_B * B) + (w_C * C) + (w_A * A)
    reconstructed_fused = max(0.0, min(1.0, reconstructed_raw))

    dq_score = finding.data_quality_status.score if finding.data_quality_status else 1.0
    sig_count = len(finding.supporting_signals)
    th = ruleset.thresholds if ruleset else _FALLBACK_THRESHOLDS

    tier_label, gating = compute_priority_tier(
        priority_score=finding.priority_score,
        independent_signals_count=sig_count,
        data_quality_score=dq_score,
        thresholds=th,
        evidence_state=finding.evidence_state,
    )

    return {
        "finding_id": str(finding.finding_id),
        "stored_priority_score": finding.priority_score,
        "reconstructed_fused_score": round(reconstructed_fused, 4),
        "reconstructed_raw_score": round(reconstructed_raw, 4),
        "components": {"T": T, "D": D, "B": B, "C": C, "A": A},
        "weights": {"w_T": w_T, "w_D": w_D, "w_B": w_B, "w_C": w_C, "w_A": w_A},
        "priority_label": tier_label,
        "thresholds": gating,
        "is_mathematically_exact": abs(finding.priority_score - round(reconstructed_fused, 4)) < 1e-3,
        "evidence_record_count": len(finding.evidence_refs),
    }


def determine_evidence_sufficiency_state(
    finding_type: FindingType,
    dq_result: DataQualityResult,
    independent_signals_count: int,
    is_absence_based: bool,
) -> EvidenceSufficiencyState:
    """
    Rigorously determines the explicit evidentiary inference state based on Data Trust.
    Guarantees SAT-SA never converts unreliable or absent telemetry into an unjustified positive security conclusion.
    """
    dq_score = dq_result.score
    comp = dq_result.components.completeness_ratio
    cov = dq_result.components.coverage_ratio
    suff = dq_result.components.sample_sufficiency_ratio

    # 1. NOT ASSESSABLE: Degraded overall DQ, or absence-based hypothesis during severe coverage/completeness outage
    if dq_score < 0.60:
        return EvidenceSufficiencyState.NOT_ASSESSABLE
    if is_absence_based and (cov < 0.50 or comp < 0.50):
        return EvidenceSufficiencyState.NOT_ASSESSABLE

    # 2. INSUFFICIENT EVIDENCE: Very sparse sample or missing mandatory fields for correlation
    if suff < 0.35 or (is_absence_based and comp < 0.65) or independent_signals_count < 2:
        return EvidenceSufficiencyState.INSUFFICIENT_EVIDENCE

    # 3. WEAKLY SUPPORTED: Moderate DQ or borderline sufficiency
    if dq_score < 0.70 or suff < 0.60 or cov < 0.70:
        return EvidenceSufficiencyState.WEAKLY_SUPPORTED

    # 4. SUPPORTED: High DQ, corroborated signals, solid completeness and coverage
    return EvidenceSufficiencyState.SUPPORTED



class EvidenceFusionEngine:
    def __init__(
        self,
        weights: dict[str, Any] | FusionWeights | None = None,
        ruleset_version: str = "V1",
        ruleset: AnalyticalRuleset | None = None,
    ):
        if ruleset is not None:
            self.ruleset = ruleset
            self.ruleset_version = ruleset.version
            self.weights = ruleset.fusion_weights.to_dict()
        elif isinstance(weights, FusionWeights):
            self.ruleset = None
            self.ruleset_version = ruleset_version
            self.weights = weights.to_dict()
        elif isinstance(weights, dict):
            self.ruleset = None
            self.ruleset_version = ruleset_version
            self.weights = weights
        else:
            self.ruleset = DEFAULT_AUTHORITATIVE_RULESET_V1
            self.ruleset_version = DEFAULT_AUTHORITATIVE_RULESET_V1.version
            self.weights = _FALLBACK_FUSION_WEIGHTS

    def fuse_signals(
        self,
        cse_id: UUID,
        reporting_period_id: UUID,
        dataset_version_id: UUID,
        analysis_run_id: UUID,
        data_quality_result: DataQualityResult,
        fast_closures: list[FastClosureSignal],
        escalation_gaps: list[EscalationGapSignal],
        repeated_unresolved: list[RepeatedUnresolvedSignal],
        coverage_gaps: list[CoverageGapSignal],
    ) -> list[Finding]:
        findings: list[Finding] = []
        now = datetime.now(timezone.utc)
        dq_score = data_quality_result.score
        comp_ratio = data_quality_result.components.completeness_ratio
        cov_ratio = data_quality_result.components.coverage_ratio
        cons_ratio = data_quality_result.components.consistency_ratio
        suff_ratio = data_quality_result.components.sample_sufficiency_ratio

        # Convert DataQualityResult to DataQualityScore Pydantic model
        dq_model = DataQualityScore(
            dataset_version_id=data_quality_result.dataset_version_id,
            score=data_quality_result.score,
            components=DataQualityComponents(
                completeness_ratio=comp_ratio,
                consistency_ratio=cons_ratio,
                coverage_ratio=cov_ratio,
                sample_sufficiency_ratio=suff_ratio,
            ),
            ruleset_version=data_quality_result.ruleset_version,
            computed_at=data_quality_result.computed_at,
        )

        # -------------------------------------------------------------------
        # 1. Fuse Fast Closure Signals for this CSE
        # -------------------------------------------------------------------
        cse_fast = [s for s in fast_closures if s.cse_id == cse_id]
        if cse_fast:
            max_z = max((s.z_score for s in cse_fast), default=0.0)
            all_refs: list[EvidenceRef] = []
            for s in cse_fast:
                all_refs.extend(s.evidence_refs)
            unique_refs = list({f"{r.entity_type}:{r.entity_id}": r for r in all_refs}.values())

            # Contributing independent signals:
            related_esc = [s for s in escalation_gaps if s.cse_id == cse_id]
            independent_signals_count = 2 + (1 if related_esc else 0)

            crit_count = sum(1 for s in cse_fast if s.workflow.alert.severity.value == "CRITICAL")
            asset_crit = "CRITICAL" if crit_count > 0 else "HIGH"
            persistence = 0.75 if len(cse_fast) >= 3 else 0.5

            raw_score, comps = calculate_priority_components(
                FusionInputs(
                    signal_count=independent_signals_count,
                    max_peer_zscore=max_z,
                    persistence_ratio=persistence,
                    asset_criticality_tier=asset_crit,
                    data_quality_score=dq_score,
                ),
                self.weights,
            )

            # Determine explicit evidence sufficiency state
            state = determine_evidence_sufficiency_state(
                finding_type=FindingType.FAST_CLOSURE,
                dq_result=data_quality_result,
                independent_signals_count=independent_signals_count,
                is_absence_based=False,
            )

            # Calculate confidence influenced by DQ, consistency, and sample sufficiency
            base_conf = min(0.98, max_z / 4.0 * 0.45 + dq_score * 0.35 + cons_ratio * 0.20)
            conf = base_conf * (0.5 + 0.5 * suff_ratio)

            supp_signals = [
                f"{len(cse_fast)} critical/high severity alerts closed below peer baseline ({cse_fast[0].peer_median_duration/60:.1f}m median)",
                f"Investigation evidence count <= {cse_fast[0].peer_p25_evidence:.0f} across flagged cases",
                f"Peer deviation |z| = {max_z:.2f} relative to sector cohort",
            ]
            if related_esc:
                supp_signals.append(f"{len(related_esc)} concurrent critical alerts lacked expected escalation records")

            contra_signals = []
            if suff_ratio < 0.6:
                contra_signals.append("Limited sample size in current reporting window")
            if dq_score < 0.7:
                contra_signals.append("Data quality score indicates elevated uncertainty")

            # Apply state-based prioritization gating
            score = raw_score
            if state == EvidenceSufficiencyState.NOT_ASSESSABLE:
                score = min(score, 0.30)
                conf = min(conf, 0.30)
                contra_signals.append("Data trust failure: finding is not assessable for operational enforcement.")
            elif state == EvidenceSufficiencyState.INSUFFICIENT_EVIDENCE:
                score = min(score, 0.45)
                conf = min(conf, 0.45)
                contra_signals.append("Insufficient evidentiary sample / statistical volume.")
            elif state == EvidenceSufficiencyState.WEAKLY_SUPPORTED:
                score = min(score, 0.60)
                conf = min(conf, 0.65)

            avg_dur = sum(s.closure_duration_seconds for s in cse_fast) / len(cse_fast)

            f_id = uuid4()
            findings.append(
                Finding(
                    finding_id=f_id,
                    cse_id=cse_id,
                    reporting_period_id=reporting_period_id,
                    finding_type=FindingType.FAST_CLOSURE,
                    priority_score=round(score, 4),
                    priority_components=comps,
                    evidentiary_confidence=round(conf, 2),
                    data_quality_status=dq_model,
                    evidence_state=state,
                    expectation_basis=ExpectationBasis.STATISTICAL_BASELINE,
                    expected_behavior=(
                        f"Expected median critical investigation closure duration ~{cse_fast[0].peer_median_duration/60:.1f} minutes "
                        f"with >= {cse_fast[0].peer_p25_evidence:.0f} pieces of evidence attached."
                    ),
                    observed_behavior=(
                        f"Observed {len(cse_fast)} critical cases closed with average duration of {avg_dur/60:.1f} minutes "
                        f"and <= {cse_fast[0].peer_p25_evidence:.0f} evidence records (Goodhart's-law fast closure pattern)."
                    ),
                    supporting_signals=supp_signals,
                    contradicting_signals=contra_signals,
                    peer_context=f"Sector peer median closure: {cse_fast[0].peer_median_duration/60:.1f}m, MAD: {cse_fast[0].peer_mad_duration/60:.1f}m",
                    temporal_context="Pattern concentrated across critical alert intake queue",
                    evidence_refs=unique_refs,
                    analytical_method="Peer-relative MAD statistical thresholding & investigation depth fusion",
                    ruleset_version=self.ruleset_version,
                    dataset_version_id=dataset_version_id,
                    analysis_run_id=analysis_run_id,
                    created_at=now,
                )
            )

        # -------------------------------------------------------------------
        # 2. Fuse Escalation Gap Signals for this CSE
        # -------------------------------------------------------------------
        cse_esc = [s for s in escalation_gaps if s.cse_id == cse_id]
        if cse_esc:
            all_refs = []
            for s in cse_esc:
                all_refs.extend(s.evidence_refs)
            unique_refs = list({f"{r.entity_type}:{r.entity_id}": r for r in all_refs}.values())

            independent_signals_count = 2 + (1 if len(cse_esc) >= 3 else 0)
            raw_score, comps = calculate_priority_components(
                FusionInputs(
                    signal_count=independent_signals_count,
                    max_peer_zscore=2.2,
                    persistence_ratio=0.8 if len(cse_esc) >= 2 else 0.4,
                    asset_criticality_tier="CRITICAL",
                    data_quality_score=dq_score,
                ),
                self.weights,
            )

            # Determine state for absence-based escalation gap
            state = determine_evidence_sufficiency_state(
                finding_type=FindingType.ESCALATION_GAP,
                dq_result=data_quality_result,
                independent_signals_count=independent_signals_count,
                is_absence_based=True,
            )

            # Absence-based confidence: severely scaled by completeness and coverage ratios
            # Low coverage/completeness means absence of records is likely pipeline omission, NOT policy violation
            trust_factor = comp_ratio * cov_ratio * dq_score
            base_conf = min(0.95, 0.40 + 0.55 * trust_factor)
            conf = base_conf * (0.6 + 0.4 * comp_ratio)

            supp_signals = [
                f"{len(cse_esc)} critical severity alerts on critical assets lacked formal escalation records",
                f"Categories affected: {', '.join(set(s.alert_category for s in cse_esc))}",
                "Expected escalation policy was not observed in operational evidence",
            ]
            contra_signals = []
            if dq_score < 0.7:
                contra_signals.append("Potential data omission during ingestion")
            if comp_ratio < 0.7:
                contra_signals.append("Low completeness ratio reduces certainty of record absence")
            if cov_ratio < 0.7:
                contra_signals.append("Low coverage ratio indicates telemetry pipeline gaps")

            # Apply state-based prioritization gating
            score = raw_score
            if state == EvidenceSufficiencyState.NOT_ASSESSABLE:
                score = min(score, 0.30)
                conf = min(conf, 0.30)
                contra_signals.append("Data trust failure: escalation absence cannot be distinguished from ingestion failure.")
            elif state == EvidenceSufficiencyState.INSUFFICIENT_EVIDENCE:
                score = min(score, 0.45)
                conf = min(conf, 0.45)
                contra_signals.append("Insufficient data completeness to confirm unescalated incident.")
            elif state == EvidenceSufficiencyState.WEAKLY_SUPPORTED:
                score = min(score, 0.60)
                conf = min(conf, 0.65)

            findings.append(
                Finding(
                    finding_id=uuid4(),
                    cse_id=cse_id,
                    reporting_period_id=reporting_period_id,
                    finding_type=FindingType.ESCALATION_GAP,
                    priority_score=round(score, 4),
                    priority_components=comps,
                    evidentiary_confidence=round(conf, 2),
                    data_quality_status=dq_model,
                    evidence_state=state,
                    expectation_basis=ExpectationBasis.HARD_REQUIREMENT,
                    expected_behavior="Mandatory formal escalation to Tier 2 / Incident Response lead for critical infrastructure alerts.",
                    observed_behavior=f"{len(cse_esc)} critical incidents were resolved or closed at Level 1 without escalation records.",
                    supporting_signals=supp_signals,
                    contradicting_signals=contra_signals,
                    peer_context="Peer baseline maintains >85% escalation rate on matching critical categories",
                    temporal_context="Continuous absence of escalation events across reporting period",
                    evidence_refs=unique_refs,
                    analytical_method="Policy conformance evaluation & workflow state tracking",
                    ruleset_version=self.ruleset_version,
                    dataset_version_id=dataset_version_id,
                    analysis_run_id=analysis_run_id,
                    created_at=now,
                )
            )

        # -------------------------------------------------------------------
        # 3. Fuse Repeated Unresolved Alert Signals for this CSE
        # -------------------------------------------------------------------
        cse_rep = [s for s in repeated_unresolved if s.cse_id == cse_id]
        for s in cse_rep:
            unique_refs = list({f"{r.entity_type}:{r.entity_id}": r for r in s.evidence_refs}.values())

            raw_score, comps = calculate_priority_components(
                FusionInputs(
                    signal_count=2,
                    max_peer_zscore=1.8,
                    persistence_ratio=0.85,
                    asset_criticality_tier="CRITICAL",
                    data_quality_score=dq_score,
                ),
                self.weights,
            )

            state = determine_evidence_sufficiency_state(
                finding_type=FindingType.REPEATED_UNRESOLVED_ALERTS,
                dq_result=data_quality_result,
                independent_signals_count=2,
                is_absence_based=True,
            )

            # Absence of remediation actions confidence
            trust_factor = comp_ratio * cov_ratio * dq_score
            base_conf = min(0.92, 0.35 + 0.55 * trust_factor)
            conf = base_conf * (0.6 + 0.4 * comp_ratio)

            supp_signals = [
                f"{s.alert_count} alerts in category '{s.alert_category}' recurred on asset {s.asset_name}",
                f"Occurred within a {s.window_days}-day rolling window without linked remediation action",
                "Indicates underlying root cause remained unresolved despite alert triage closures",
            ]
            contra_signals = []
            if comp_ratio < 0.7:
                contra_signals.append("Low completeness ratio reduces certainty of action absence")

            score = raw_score
            if state == EvidenceSufficiencyState.NOT_ASSESSABLE:
                score = min(score, 0.30)
                conf = min(conf, 0.30)
                contra_signals.append("Data trust failure: remediation action absence is not assessable.")
            elif state == EvidenceSufficiencyState.INSUFFICIENT_EVIDENCE:
                score = min(score, 0.45)
                conf = min(conf, 0.45)
            elif state == EvidenceSufficiencyState.WEAKLY_SUPPORTED:
                score = min(score, 0.60)
                conf = min(conf, 0.65)

            findings.append(
                Finding(
                    finding_id=uuid4(),
                    cse_id=cse_id,
                    reporting_period_id=reporting_period_id,
                    finding_type=FindingType.REPEATED_UNRESOLVED_ALERTS,
                    priority_score=round(score, 4),
                    priority_components=comps,
                    evidentiary_confidence=round(conf, 2),
                    data_quality_status=dq_model,
                    evidence_state=state,
                    expectation_basis=ExpectationBasis.CONFIGURED_EXPECTATION,
                    expected_behavior="Recurring security alerts on critical assets must include permanent remediation or mitigation action.",
                    observed_behavior=f"{s.alert_count} alerts recurred on {s.asset_name} without any corrective action record.",
                    supporting_signals=supp_signals,
                    contradicting_signals=contra_signals,
                    peer_context="Asset persistence significantly exceeds normal transient noise",
                    temporal_context=f"Alert clustering observed across {s.window_days}-day window",
                    evidence_refs=unique_refs,
                    analytical_method="Time-windowed asset recurrence clustering & remediation action matching",
                    ruleset_version=self.ruleset_version,
                    dataset_version_id=dataset_version_id,
                    analysis_run_id=analysis_run_id,
                    created_at=now,
                )
            )

        # -------------------------------------------------------------------
        # 4. Fuse Coverage Gap Negative-Space Signals for this CSE
        # -------------------------------------------------------------------
        cse_cov = [s for s in coverage_gaps if s.cse_id == cse_id]
        for s in cse_cov:
            unique_refs = list({f"{r.entity_type}:{r.entity_id}": r for r in s.evidence_refs}.values())

            raw_score, comps = calculate_priority_components(
                FusionInputs(
                    signal_count=2,
                    max_peer_zscore=2.0,
                    persistence_ratio=0.9,
                    asset_criticality_tier=s.asset_criticality.value,
                    data_quality_score=dq_score,
                ),
                self.weights,
            )

            # Negative-space inference: strict evaluation
            state = determine_evidence_sufficiency_state(
                finding_type=FindingType.COVERAGE_GAP,
                dq_result=data_quality_result,
                independent_signals_count=2,
                is_absence_based=True,
            )

            # Confidence scaled heavily by Data Trust and Coverage ratio
            conf = min(0.92, dq_score * cov_ratio * 0.95)

            supp_signals = [
                f"Observed {s.observed_count:.0f} alerts vs expected {s.expected_count:.0f} (coverage ratio: {s.coverage_ratio*100:.1f}%)",
                f"Data quality score is healthy ({dq_score*100:.1f}%), ruling out pure data ingestion outage",
                f"Asset criticality is {s.asset_criticality.value} - monitoring silence represents high risk hypothesis",
            ]
            contra_signals = ["Verify sensor reachability before confirming blind spot"]

            score = raw_score
            if state == EvidenceSufficiencyState.NOT_ASSESSABLE:
                score = min(score, 0.30)
                conf = min(conf, 0.30)
                contra_signals.append("Data trust failure: silence may reflect telemetry ingestion outage.")
            elif state == EvidenceSufficiencyState.INSUFFICIENT_EVIDENCE:
                score = min(score, 0.45)
                conf = min(conf, 0.45)
            elif state == EvidenceSufficiencyState.WEAKLY_SUPPORTED:
                score = min(score, 0.60)
                conf = min(conf, 0.65)

            findings.append(
                Finding(
                    finding_id=uuid4(),
                    cse_id=cse_id,
                    reporting_period_id=reporting_period_id,
                    finding_type=FindingType.COVERAGE_GAP,
                    priority_score=round(score, 4),
                    priority_components=comps,
                    evidentiary_confidence=round(conf, 2),
                    data_quality_status=dq_model,
                    evidence_state=state,
                    expectation_basis=ExpectationBasis.CONFIGURED_EXPECTATION,
                    expected_behavior=f"Expected baseline telemetry volume (~{s.expected_count:.0f} events) for critical environment monitoring.",
                    observed_behavior=f"Severe monitoring silence: only {s.observed_count:.0f} events observed ({s.coverage_ratio*100:.1f}% of expected baseline).",
                    supporting_signals=supp_signals,
                    contradicting_signals=contra_signals,
                    peer_context="Peer entities in same sector average standard telemetry density",
                    temporal_context="Consistent coverage absence during active operational reporting cycle",
                    evidence_refs=unique_refs,
                    analytical_method="Negative-space expectation modeling & data-trust gated coverage calculation",
                    ruleset_version=self.ruleset_version,
                    dataset_version_id=dataset_version_id,
                    analysis_run_id=analysis_run_id,
                    created_at=now,
                )
            )

        return findings

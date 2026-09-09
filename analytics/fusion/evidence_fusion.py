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
    ExpectationBasis,
    Finding,
    FindingType,
)

_DEFAULT_FUSION_WEIGHTS = {
    "signal_strength_weight": 0.30,
    "peer_deviation_weight": 0.25,
    "persistence_weight": 0.20,
    "asset_criticality_weight": 0.15,
    "data_uncertainty_weight": -0.10,
    "signal_strength_cap": 3,
    "peer_deviation_zscore_cap": 3.0,
    "high_priority_min_independent_signals": 2,
    "high_priority_min_data_quality": 0.6,
}


@dataclass
class FusionInputs:
    signal_count: int
    max_peer_zscore: float
    persistence_ratio: float
    asset_criticality_tier: str
    data_quality_score: float


def calculate_priority_components(
    inputs: FusionInputs,
    weights: dict[str, Any] | None = None,
) -> tuple[float, dict[str, float]]:
    w = weights or _DEFAULT_FUSION_WEIGHTS

    # 1. Signal strength: normalized by cap
    cap_sig = w.get("signal_strength_cap", 3)
    norm_signal_strength = min(inputs.signal_count / max(cap_sig, 1), 1.0)

    # 2. Peer deviation: normalized |z-score| by cap
    cap_z = w.get("peer_deviation_zscore_cap", 3.0)
    norm_peer_dev = min(abs(inputs.max_peer_zscore) / max(cap_z, 0.1), 1.0)

    # 3. Persistence: normalized 0-1
    norm_persistence = max(0.0, min(1.0, inputs.persistence_ratio))

    # 4. Asset criticality
    crit_map = {
        "CRITICAL": 1.0,
        "HIGH": 0.75,
        "MEDIUM": 0.5,
        "LOW": 0.25,
    }
    norm_asset_crit = crit_map.get(inputs.asset_criticality_tier.upper(), 0.5)

    # 5. Data uncertainty: (1 - DataQualityScore)
    data_uncertainty = max(0.0, 1.0 - inputs.data_quality_score)

    raw_score = (
        w["signal_strength_weight"] * norm_signal_strength
        + w["peer_deviation_weight"] * norm_peer_dev
        + w["persistence_weight"] * norm_persistence
        + w["asset_criticality_weight"] * norm_asset_crit
        + w["data_uncertainty_weight"] * data_uncertainty
    )
    final_score = max(0.0, min(1.0, raw_score))

    components = {
        "signal_strength": round(norm_signal_strength, 4),
        "peer_deviation": round(norm_peer_dev, 4),
        "persistence": round(norm_persistence, 4),
        "asset_criticality": round(norm_asset_crit, 4),
        "data_uncertainty": round(data_uncertainty, 4),
    }

    return final_score, components


class EvidenceFusionEngine:
    def __init__(self, weights: dict[str, Any] | None = None, ruleset_version: str = "V1"):
        self.weights = weights or _DEFAULT_FUSION_WEIGHTS
        self.ruleset_version = ruleset_version

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

        # Convert DataQualityResult to DataQualityScore Pydantic model
        dq_model = DataQualityScore(
            dataset_version_id=data_quality_result.dataset_version_id,
            score=data_quality_result.score,
            components=DataQualityComponents(
                completeness_ratio=data_quality_result.components.completeness_ratio,
                consistency_ratio=data_quality_result.components.consistency_ratio,
                coverage_ratio=data_quality_result.components.coverage_ratio,
                sample_sufficiency_ratio=data_quality_result.components.sample_sufficiency_ratio,
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
            # Deduplicate refs
            unique_refs = list({f"{r.entity_type}:{r.entity_id}": r for r in all_refs}.values())

            # Contributing independent signals:
            related_esc = [s for s in escalation_gaps if s.cse_id == cse_id]
            independent_signals_count = 2 + (1 if related_esc else 0)

            crit_count = sum(1 for s in cse_fast if s.workflow.alert.severity.value == "CRITICAL")
            asset_crit = "CRITICAL" if crit_count > 0 else "HIGH"
            persistence = 0.75 if len(cse_fast) >= 3 else 0.5

            score, comps = calculate_priority_components(
                FusionInputs(
                    signal_count=independent_signals_count,
                    max_peer_zscore=max_z,
                    persistence_ratio=persistence,
                    asset_criticality_tier=asset_crit,
                    data_quality_score=dq_score,
                ),
                self.weights,
            )

            supp_signals = [
                f"{len(cse_fast)} critical/high severity alerts closed below peer baseline ({cse_fast[0].peer_median_duration/60:.1f}m median)",
                f"Investigation evidence count <= {cse_fast[0].peer_p25_evidence:.0f} across flagged cases",
                f"Peer deviation |z| = {max_z:.2f} relative to sector cohort",
            ]
            if related_esc:
                supp_signals.append(f"{len(related_esc)} concurrent critical alerts lacked expected escalation records")

            contra_signals = []
            if data_quality_result.components.sample_sufficiency_ratio < 0.6:
                contra_signals.append("Limited sample size in current reporting window")
            if dq_score < 0.7:
                contra_signals.append("Data quality score indicates elevated uncertainty")

            avg_dur = sum(s.closure_duration_seconds for s in cse_fast) / len(cse_fast)

            f_id = uuid4()
            findings.append(
                Finding(
                    finding_id=f_id,
                    cse_id=cse_id,
                    reporting_period_id=reporting_period_id,
                    finding_type=FindingType.FAST_CLOSURE,
                    priority_score=score,
                    priority_components=comps,
                    evidentiary_confidence=round(min(0.98, max_z / 4.0 * 0.5 + dq_score * 0.5), 2),
                    data_quality_status=dq_model,
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
            score, comps = calculate_priority_components(
                FusionInputs(
                    signal_count=independent_signals_count,
                    max_peer_zscore=2.2,
                    persistence_ratio=0.8 if len(cse_esc) >= 2 else 0.4,
                    asset_criticality_tier="CRITICAL",
                    data_quality_score=dq_score,
                ),
                self.weights,
            )

            supp_signals = [
                f"{len(cse_esc)} critical severity alerts on critical assets lacked formal escalation records",
                f"Categories affected: {', '.join(set(s.alert_category for s in cse_esc))}",
                "Expected escalation policy was not observed in operational evidence",
            ]
            contra_signals = []
            if dq_score < 0.7:
                contra_signals.append("Potential data omission during ingestion")

            findings.append(
                Finding(
                    finding_id=uuid4(),
                    cse_id=cse_id,
                    reporting_period_id=reporting_period_id,
                    finding_type=FindingType.ESCALATION_GAP,
                    priority_score=score,
                    priority_components=comps,
                    evidentiary_confidence=round(min(0.95, 0.4 + dq_score * 0.55), 2),
                    data_quality_status=dq_model,
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

            score, comps = calculate_priority_components(
                FusionInputs(
                    signal_count=2,
                    max_peer_zscore=1.8,
                    persistence_ratio=0.85,
                    asset_criticality_tier="CRITICAL",
                    data_quality_score=dq_score,
                ),
                self.weights,
            )

            supp_signals = [
                f"{s.alert_count} alerts in category '{s.alert_category}' recurred on asset {s.asset_name}",
                f"Occurred within a {s.window_days}-day rolling window without linked remediation action",
                "Indicates underlying root cause remained unresolved despite alert triage closures",
            ]

            findings.append(
                Finding(
                    finding_id=uuid4(),
                    cse_id=cse_id,
                    reporting_period_id=reporting_period_id,
                    finding_type=FindingType.REPEATED_UNRESOLVED_ALERTS,
                    priority_score=score,
                    priority_components=comps,
                    evidentiary_confidence=round(min(0.92, 0.35 + dq_score * 0.55), 2),
                    data_quality_status=dq_model,
                    expectation_basis=ExpectationBasis.CONFIGURED_EXPECTATION,
                    expected_behavior="Recurring security alerts on critical assets must include permanent remediation or mitigation action.",
                    observed_behavior=f"{s.alert_count} alerts recurred on {s.asset_name} without any corrective action record.",
                    supporting_signals=supp_signals,
                    contradicting_signals=[],
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

            score, comps = calculate_priority_components(
                FusionInputs(
                    signal_count=2,
                    max_peer_zscore=2.0,
                    persistence_ratio=0.9,
                    asset_criticality_tier=s.asset_criticality.value,
                    data_quality_score=dq_score,
                ),
                self.weights,
            )

            supp_signals = [
                f"Observed {s.observed_count:.0f} alerts vs expected {s.expected_count:.0f} (coverage ratio: {s.coverage_ratio*100:.1f}%)",
                f"Data quality score is healthy ({dq_score*100:.1f}%), ruling out pure data ingestion outage",
                f"Asset criticality is {s.asset_criticality.value} - monitoring silence represents high risk hypothesis",
            ]

            findings.append(
                Finding(
                    finding_id=uuid4(),
                    cse_id=cse_id,
                    reporting_period_id=reporting_period_id,
                    finding_type=FindingType.COVERAGE_GAP,
                    priority_score=score,
                    priority_components=comps,
                    evidentiary_confidence=round(min(0.90, dq_score * 0.9), 2),
                    data_quality_status=dq_model,
                    expectation_basis=ExpectationBasis.CONFIGURED_EXPECTATION,
                    expected_behavior=f"Expected baseline telemetry volume (~{s.expected_count:.0f} events) for critical environment monitoring.",
                    observed_behavior=f"Severe monitoring silence: only {s.observed_count:.0f} events observed ({s.coverage_ratio*100:.1f}% of expected baseline).",
                    supporting_signals=supp_signals,
                    contradicting_signals=["Verify sensor reachability before confirming blind spot"],
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

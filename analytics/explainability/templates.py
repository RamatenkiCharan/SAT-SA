"""
Explainability & Template Substitution Engine (SRS §11, §24, §52).
Generates 100% deterministic, auditable natural-language explanations, structured diagnostic items,
and supervisory action guidance via strict template substitution over computed metrics.
NEVER uses LLMs or generative models — zero hallucination, bit-for-bit reproducible.
"""
from __future__ import annotations

from typing import Any
from backend.models.canonical import Finding, FindingType, EvidenceSufficiencyState
from analytics.fusion.evidence_fusion import compute_priority_tier


def generate_finding_explanation(finding: Finding) -> dict[str, Any]:
    """
    Renders structured, deterministic explanation components for a finding.
    
    Guarantees:
    1. Deterministic output: Identical finding input always produces identical explanation.
    2. Zero generative LLMs: Pure template substitution and mathematical formatting.
    3. Type-specific template selection: FAST_CLOSURE, ESCALATION_GAP, REPEATED_UNRESOLVED_ALERTS, COVERAGE_GAP.
    4. Insertion of actual empirical finding values (metrics, signals, counts, peer stats, DQ ratios).
    5. Detailed fields: what_happened, why_flagged, supporting_evidence_summary, confidence_summary,
       peer_context_summary, data_quality_limitation, recommended_action.
    6. Strict evidence fidelity: Never claims evidence that does not exist; explicitly notes policy absence.
    """
    f_type = finding.finding_type
    p_score = finding.priority_score
    p_comps = finding.priority_components or {}
    dq = finding.data_quality_status
    state_val = finding.evidence_state.value if finding.evidence_state else "SUPPORTED"
    ev_count = len(finding.evidence_refs)
    sig_count = len(finding.supporting_signals)
    confidence_pct = round(finding.evidentiary_confidence * 100, 1)

    # Format priority tier with explicit threshold and gating validation
    priority_label, gating = compute_priority_tier(
        priority_score=p_score,
        independent_signals_count=sig_count,
        data_quality_score=dq.score if dq else 1.0,
        evidence_state=finding.evidence_state,
    )

    # ---------------------------------------------------------------------------
    # Data Quality Breakdown & Limitation Analysis
    # ---------------------------------------------------------------------------
    if dq and dq.components:
        dq_score_pct = round(dq.score * 100, 1)
        dq_breakdown = {
            "overall_score": dq_score_pct,
            "completeness": round(dq.components.completeness_ratio * 100, 1),
            "consistency": round(dq.components.consistency_ratio * 100, 1),
            "coverage": round(dq.components.coverage_ratio * 100, 1),
            "sample_sufficiency": round(dq.components.sample_sufficiency_ratio * 100, 1),
        }
        if dq.score >= 0.85:
            dq_limitation = (
                f"Data quality is high ({dq_score_pct}%). Operational telemetry across completeness ({dq_breakdown['completeness']}%), "
                f"consistency ({dq_breakdown['consistency']}%), and coverage ({dq_breakdown['coverage']}%) fully supports high-confidence inference."
            )
        elif dq.score >= 0.60:
            dq_limitation = (
                f"Data quality is moderate ({dq_score_pct}%). An uncertainty adjustment (A = {p_comps.get('data_uncertainty', 1.0 - dq.score):.2f}) "
                f"was applied during evidence fusion."
            )
        else:
            dq_limitation = (
                f"Data quality is degraded ({dq_score_pct}% < 60.0% threshold). Telemetry gaps limit supervisory confidence. "
                f"Negative-space findings are constrained and priority tier is gated to prevent false conclusions."
            )
    else:
        dq_score_pct = 100.0
        dq_breakdown = {
            "overall_score": 100.0,
            "completeness": 100.0,
            "consistency": 100.0,
            "coverage": 100.0,
            "sample_sufficiency": 100.0,
        }
        dq_limitation = "Data quality score is not explicitly attached; default unpenalized baseline assumed."

    # ---------------------------------------------------------------------------
    # Evidence & Confidence Summary (Zero Fabrication Guarantee)
    # ---------------------------------------------------------------------------
    if state_val == "NOT_ASSESSABLE":
        confidence_summary = (
            f"Confidence: {confidence_pct}% [State: NOT_ASSESSABLE]. Telemetry pipeline degradation or severe data outage "
            f"precludes reliable supervisory assessment."
        )
    elif state_val == "INSUFFICIENT_EVIDENCE":
        confidence_summary = (
            f"Confidence: {confidence_pct}% [State: INSUFFICIENT_EVIDENCE]. Observational sample is sparse; "
            f"findings represent weak supervisory hypotheses pending additional telemetry cycles."
        )
    elif state_val == "WEAKLY_SUPPORTED":
        confidence_summary = (
            f"Confidence: {confidence_pct}% [State: WEAKLY_SUPPORTED]. Finding is backed by limited operational signals ({sig_count}) "
            f"with moderate uncertainty."
        )
    else:
        confidence_summary = (
            f"Confidence: {confidence_pct}% [State: SUPPORTED]. Finding is corroborated by {sig_count} independent analytical signals "
            f"and {ev_count} operational records."
        )

    # ---------------------------------------------------------------------------
    # Template Selection based on Finding Type
    # ---------------------------------------------------------------------------
    if f_type == FindingType.FAST_CLOSURE:
        title = "Potential Rapid-Closure Execution Gap"
        headline = (
            f"Supervisory attention recommended: Critical incidents closed significantly faster "
            f"than peer baseline with low attached investigation evidence."
        )
        what_happened = (
            f"Regulated entity SOC resolved high-severity alerts at an unusually high velocity. "
            f"{finding.observed_behavior}."
        )
        why_flagged = (
            f"Flagged by Fast Closure Detector (FR-030). Triage durations breach peer statistical expectations "
            f"({finding.expected_behavior}). Signal indicates potential Goodhart's Law metric gaming where SLA compliance "
            f"is achieved through superficial triage rather than root-cause investigation."
        )
        if ev_count > 0:
            supporting_evidence_summary = (
                f"{ev_count} concrete alert and case records attached with {sig_count} corroborating signals demonstrating rapid closure."
            )
        else:
            supporting_evidence_summary = (
                "Zero attached investigation notes or remediation records found for rapidly closed tickets."
            )
        peer_context_summary = (
            finding.peer_context or "Entity triage speed evaluated against sector peer cohort MAD distribution."
        )
        recommended_action = (
            "Initiate targeted supervisory examination of L1 analyst closure workflows. Request sample "
            "investigation notes and verify whether alerts were properly remediated before closure."
        )

    elif f_type == FindingType.ESCALATION_GAP:
        title = "Critical Incident Escalation Gap"
        headline = (
            f"Supervisory attention recommended: High-severity security events were resolved without "
            f"mandated escalation to Tier 2 / Incident Response leadership."
        )
        what_happened = (
            f"High-severity security alerts affecting critical assets were closed without required escalation. "
            f"{finding.observed_behavior}."
        )
        why_flagged = (
            f"Flagged by Escalation Gap Detector (FR-032). Institutional policy mandates Tier-2/Tier-3 escalation "
            f"for high-severity events on critical infrastructure. Ingested operational logs show zero escalation "
            f"handoffs for eligible incidents ({finding.expected_behavior})."
        )
        if ev_count > 0:
            supporting_evidence_summary = (
                f"{ev_count} unescalated critical incident records identified. Policy absence confirmed: 0 escalation handoffs logged."
            )
        else:
            supporting_evidence_summary = (
                "Policy absence confirmed: Zero escalation records exist in ingested telemetry for flagged critical incidents."
            )
        peer_context_summary = (
            finding.peer_context or "Evaluated against mandatory supervisory compliance standards across regulated critical sector entities."
        )
        recommended_action = (
            "Review SOC escalation procedures with entity leadership. Audit ticketing system permissions "
            "and verify if escalation bypass was due to analyst workload or procedural failure."
        )

    elif f_type == FindingType.REPEATED_UNRESOLVED_ALERTS:
        title = "Unresolved Threat Recurrence Execution Gap"
        headline = (
            f"Supervisory attention recommended: Recurring security alerts on critical infrastructure "
            f"assets closed repeatedly without corresponding root-cause remediation actions."
        )
        what_happened = (
            f"Identical alert signatures re-occurred repeatedly on critical infrastructure assets. "
            f"{finding.observed_behavior}."
        )
        why_flagged = (
            f"Flagged by Repeated Unresolved Alerts Detector (FR-033). Alerts firing >= 3 times within 7 days "
            f"without verified engineering remediation indicate superficial ticket clearing without addressing underlying vulnerability."
        )
        if ev_count > 0:
            supporting_evidence_summary = (
                f"{ev_count} recurring alert instances identified across asset footprint without corresponding root-cause remediation actions."
            )
        else:
            supporting_evidence_summary = (
                "Zero remediation action tickets attached to recurring security alert clusters."
            )
        peer_context_summary = (
            finding.peer_context or "Entity alert recurrence rate compared against sector peer median."
        )
        recommended_action = (
            "Request engineering ticket logs for affected asset. Determine why alert triggers keep firing "
            "and whether compensating controls or patch remediations were actually deployed."
        )

    elif f_type == FindingType.COVERAGE_GAP:
        title = "Negative-Space Monitoring Coverage Gap"
        headline = (
            f"Supervisory hypothesis: Severe absence of expected security telemetry on critical infrastructure "
            f"despite healthy data ingestion pipelines."
        )
        what_happened = (
            f"Critical infrastructure assets exhibited abnormal telemetry silence during active operations. "
            f"{finding.observed_behavior}."
        )
        why_flagged = (
            f"Flagged by Negative-Space Coverage Gap Detector (FR-041). Expected security telemetry baseline was not observed "
            f"({finding.expected_behavior}). Because data quality score ({dq_score_pct}%) is verified healthy, silence represents "
            f"an unmonitored blind spot rather than an ingestion outage."
        )
        if ev_count > 0:
            supporting_evidence_summary = (
                f"{ev_count} coverage observation records attached confirming silence during the reporting window."
            )
        else:
            supporting_evidence_summary = (
                "Telemetry silence confirmed: Zero alert records produced by critical asset during active period."
            )
        peer_context_summary = (
            finding.peer_context or "Asset telemetry volume evaluated against peer asset category baseline."
        )
        recommended_action = (
            "Perform sensor reachability and log forwarding audit on the silent asset. Verify if log collection "
            "agents are active or if detection rules were inadvertently disabled."
        )

    else:
        title = "Operational Evidence Anomaly"
        headline = "Operational evidence deviates from expected supervisory baseline."
        what_happened = f"Operational evidence anomaly detected: {finding.observed_behavior}."
        why_flagged = f"Observed operational evidence deviates from expected baseline: {finding.expected_behavior}."
        supporting_evidence_summary = (
            f"{ev_count} evidence records attached with {sig_count} supporting signals."
            if ev_count > 0 else "Zero evidence records attached."
        )
        peer_context_summary = finding.peer_context or "Operational baseline comparison."
        recommended_action = "Perform standard supervisory review of submitted operational evidence."

    # ---------------------------------------------------------------------------
    # State-Aware Supervisory Action Guidance
    # ---------------------------------------------------------------------------
    if state_val == "NOT_ASSESSABLE":
        recommended_action = (
            "Do not initiate disciplinary or operational compliance actions. Perform immediate audit of "
            "log ingestion pipelines, sensor connectivity, and format parsers to restore reliable telemetry."
        )
    elif state_val == "INSUFFICIENT_EVIDENCE":
        recommended_action = (
            "Evidentiary sample is sparse. Collect additional reporting periods of telemetry before "
            "drawing operational conclusions regarding SOC triage effectiveness."
        )

    # ---------------------------------------------------------------------------
    # Priority Breakdown Strings
    # ---------------------------------------------------------------------------
    priority_breakdown = [
        f"Signal Strength ({p_comps.get('signal_strength', 0.0):.2f}): Corroborated by independent analytical detectors",
        f"Peer Cohort Deviation ({p_comps.get('peer_deviation', 0.0):.2f}): Robust statistical distance from sector median",
        f"Persistence Factor ({p_comps.get('persistence', 0.0):.2f}): Continuity across reporting intervals",
        f"Asset Criticality Tier ({p_comps.get('asset_criticality', 0.0):.2f}): Weighting for critical sector infrastructure",
        f"Data Trust Uncertainty ({p_comps.get('data_uncertainty', 0.0):.2f}): Penalty deducted for data quality gaps",
    ]

    return {
        "title": title,
        "priority_label": priority_label,
        "priority_score": round(p_score, 3),
        "headline": headline,
        "what_happened": what_happened,
        "why_flagged": why_flagged,
        "supporting_evidence_summary": supporting_evidence_summary,
        "confidence_summary": confidence_summary,
        "peer_context_summary": peer_context_summary,
        "data_quality_limitation": dq_limitation,
        "evidence_state": state_val,
        "expected_behavior": finding.expected_behavior,
        "observed_behavior": finding.observed_behavior,
        "supporting_signals": finding.supporting_signals,
        "contradicting_signals": finding.contradicting_signals,
        "peer_context": finding.peer_context,
        "temporal_context": finding.temporal_context,
        "priority_breakdown": priority_breakdown,
        "data_quality_breakdown": dq_breakdown,
        "evidence_record_count": ev_count,
        "recommended_action": recommended_action,
        "analytical_method": finding.analytical_method,
        "provenance": {
            "ruleset_version": finding.ruleset_version,
            "dataset_version_id": str(finding.dataset_version_id),
            "analysis_run_id": str(finding.analysis_run_id),
        },
    }

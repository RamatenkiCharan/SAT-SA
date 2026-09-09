"""
Explainability & Template Substitution Engine.
Generates 100% deterministic, auditable natural-language explanations and supervisory action guidance
via strict template substitution over computed metrics — NEVER using LLMs or generative text.
"""
from __future__ import annotations

from typing import Any
from backend.models.canonical import Finding, FindingType


def generate_finding_explanation(finding: Finding) -> dict[str, Any]:
    """
    Renders structured, deterministic explanation components for a finding.
    """
    f_type = finding.finding_type
    p_score = finding.priority_score
    p_comps = finding.priority_components
    dq = finding.data_quality_status
    
    # Format priority tier
    if p_score >= 0.75:
        priority_label = "HIGH"
    elif p_score >= 0.50:
        priority_label = "MEDIUM"
    else:
        priority_label = "LOW"

    # Deterministic Rationale Generator
    if f_type == FindingType.FAST_CLOSURE:
        title = "Potential Rapid-Closure Execution Gap"
        headline = (
            f"Supervisory attention recommended: Critical incidents closed significantly faster "
            f"than peer baseline with low attached investigation evidence."
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
        recommended_action = (
            "Request engineering ticket logs for affected asset. Determine why alert triggers keep firing "
            "and whether compensating controls or patch remediations were actually deployed."
        )
    elif f_type == FindingType.INVESTIGATION_INSUFFICIENCY:
        title = "Superficial Investigation Execution Gap"
        headline = (
            f"Supervisory attention recommended: High-severity security events closed with minimal "
            f"or zero attached investigation evidence, indicating low-depth analyst triage."
        )
        recommended_action = (
            "Inspect analyst investigation logs and ticketing artifacts. Determine if triage was "
            "automated superficially or if analysts lack necessary forensic tooling."
        )
    elif f_type == FindingType.WORKFLOW_SHORTCUT:
        title = "Suspicious Lifecycle Workflow Shortcut"
        headline = (
            f"Supervisory attention recommended: Security incidents bypassed mandatory lifecycle phases "
            f"(e.g., direct closure without investigation or instantaneous transition)."
        )
        recommended_action = (
            "Audit SOAR automation playbooks and manual bypass permissions. Verify why mandatory "
            "investigation gates were omitted prior to ticket closure."
        )
    elif f_type == FindingType.COVERAGE_GAP:
        title = "Negative-Space Monitoring Coverage Gap"
        headline = (
            f"Supervisory hypothesis: Severe absence of expected security telemetry on critical infrastructure "
            f"despite healthy data ingestion pipelines."
        )
        recommended_action = (
            "Perform sensor reachability and log forwarding audit on the silent asset. Verify if log collection "
            "agents are active or if detection rules were inadvertently disabled."
        )
    else:
        title = "Operational Evidence Anomaly"
        headline = "Operational evidence deviates from expected supervisory baseline."
        recommended_action = "Perform standard supervisory review of submitted operational evidence."

    # Decomposed explanation of priority components
    priority_breakdown = [
        f"Signal Strength ({p_comps.get('signal_strength', 0.0):.2f}): Corroborated by independent analytical detectors",
        f"Peer Cohort Deviation ({p_comps.get('peer_deviation', 0.0):.2f}): Robust statistical distance from sector median",
        f"Persistence Factor ({p_comps.get('persistence', 0.0):.2f}): Continuity across reporting intervals",
        f"Asset Criticality Tier ({p_comps.get('asset_criticality', 0.0):.2f}): Weighting for critical sector infrastructure",
        f"Data Trust Uncertainty ({p_comps.get('data_uncertainty', 0.0):.2f}): Penalty deducted for data quality gaps",
    ]

    # Decomposed Data Quality Breakdown
    dq_breakdown = {
        "overall_score": round(dq.score * 100, 1),
        "completeness": round(dq.components.completeness_ratio * 100, 1),
        "consistency": round(dq.components.consistency_ratio * 100, 1),
        "coverage": round(dq.components.coverage_ratio * 100, 1),
        "sample_sufficiency": round(dq.components.sample_sufficiency_ratio * 100, 1),
    }

    return {
        "title": title,
        "priority_label": priority_label,
        "priority_score": round(p_score, 3),
        "headline": headline,
        "expected_behavior": finding.expected_behavior,
        "observed_behavior": finding.observed_behavior,
        "supporting_signals": finding.supporting_signals,
        "contradicting_signals": finding.contradicting_signals,
        "peer_context": finding.peer_context,
        "temporal_context": finding.temporal_context,
        "priority_breakdown": priority_breakdown,
        "data_quality_breakdown": dq_breakdown,
        "evidence_record_count": len(finding.evidence_refs),
        "recommended_action": recommended_action,
        "analytical_method": finding.analytical_method,
        "provenance": {
            "ruleset_version": finding.ruleset_version,
            "dataset_version_id": str(finding.dataset_version_id),
            "analysis_run_id": str(finding.analysis_run_id),
        },
    }

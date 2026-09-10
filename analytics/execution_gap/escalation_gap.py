"""
Escalation Gap Execution-Gap Detector (FR-032).
Flags critical alerts and cases that warranted formal escalation under expected operational policy
but lack any corresponding escalation record.

Formula:
  flag if severity = CRITICAL
      AND escalation_expected(asset_criticality, alert_category) = TRUE
      AND no escalation record exists for the case
"""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from analytics.workflow.workflow_reconstruction import ReconstructedDataset, ReconstructedWorkflow
from backend.models.canonical import AssetCriticality, EvidenceRef, Severity
from backend.models.ruleset import EscalationGapConfig


@dataclass
class EscalationGapSignal:
    cse_id: UUID
    workflow: ReconstructedWorkflow
    severity: Severity
    asset_criticality: AssetCriticality
    alert_category: str
    evidence_refs: list[EvidenceRef] = field(default_factory=list)


class EscalationGapDetector:
    def __init__(
        self,
        applies_to_severity: list[str] | None = None,
        config: EscalationGapConfig | None = None,
    ):
        if config is not None:
            self.applies_to_severity = list(config.applies_to_severity)
            self.high_impact_categories = set(c.lower() for c in config.high_impact_categories)
        else:
            self.applies_to_severity = applies_to_severity or ["CRITICAL"]
            self.high_impact_categories = {
                "ransomware",
                "scada intrusion",
                "data exfiltration",
                "privilege escalation",
                "unauthorized access",
                "malware execution",
                "command and control",
            }

    def _is_escalation_expected(self, w: ReconstructedWorkflow) -> bool:
        # Pinned logic: Critical severity on Critical or High criticality asset,
        # or sensitive high-impact categories.
        is_crit_sev = w.alert.severity.value in self.applies_to_severity
        
        asset_crit = w.asset.criticality if w.asset else AssetCriticality.HIGH
        is_crit_asset = asset_crit in (AssetCriticality.CRITICAL, AssetCriticality.HIGH)
        is_high_impact = w.alert.alert_category.lower() in self.high_impact_categories

        return is_crit_sev and (is_crit_asset or is_high_impact)


    def detect(self, dataset: ReconstructedDataset) -> list[EscalationGapSignal]:
        signals: list[EscalationGapSignal] = []

        for w in dataset.workflows:
            if not self._is_escalation_expected(w):
                continue

            # Check if escalation record is missing
            if not w.has_escalation:
                refs: list[EvidenceRef] = [
                    EvidenceRef(entity_type="alert", entity_id=w.alert.alert_id)
                ]
                if w.case:
                    refs.append(EvidenceRef(entity_type="case", entity_id=w.case.case_id))
                if w.investigation:
                    refs.append(
                        EvidenceRef(
                            entity_type="investigation",
                            entity_id=w.investigation.investigation_id,
                        )
                    )
                if w.asset:
                    refs.append(EvidenceRef(entity_type="asset", entity_id=w.asset.asset_id))

                signals.append(
                    EscalationGapSignal(
                        cse_id=w.alert.cse_id,
                        workflow=w,
                        severity=w.alert.severity,
                        asset_criticality=w.asset.criticality if w.asset else AssetCriticality.HIGH,
                        alert_category=w.alert.alert_category,
                        evidence_refs=refs,
                    )
                )

        return signals

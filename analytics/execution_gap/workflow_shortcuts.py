"""
Suspicious Workflow Shortcut Detector (FR-034).
Flags critical and high severity alerts that skipped mandatory lifecycle phases
(e.g., closed with zero investigation record, or instantaneous transition <10s).

Formula / Logic:
  flag if alert.severity IN {CRITICAL, HIGH}
       AND (
           (alert is CLOSED and has NO investigation record)
           OR (closure_duration_seconds < 10.0)
       )
"""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from analytics.workflow.workflow_reconstruction import ReconstructedDataset, ReconstructedWorkflow
from backend.models.canonical import EvidenceRef, Severity


@dataclass
class WorkflowShortcutSignal:
    cse_id: UUID
    workflow: ReconstructedWorkflow
    shortcut_type: str  # "SKIPPED_INVESTIGATION" | "INSTANTANEOUS_CLOSURE"
    duration_seconds: float
    evidence_refs: list[EvidenceRef] = field(default_factory=list)


class WorkflowShortcutDetector:
    def __init__(self, instantaneous_threshold_seconds: float = 10.0):
        self.instantaneous_threshold_seconds = instantaneous_threshold_seconds

    def detect(self, dataset: ReconstructedDataset) -> list[WorkflowShortcutSignal]:
        signals: list[WorkflowShortcutSignal] = []

        for cse in dataset.raw_dataset.cse_list:
            wfs = dataset.get_workflows_for_cse(cse.cse_id)
            for w in wfs:
                if w.alert.severity not in (Severity.CRITICAL, Severity.HIGH):
                    continue

                refs: list[EvidenceRef] = [
                    EvidenceRef(entity_type="alert", entity_id=w.alert.alert_id)
                ]
                if w.case:
                    refs.append(EvidenceRef(entity_type="case", entity_id=w.case.case_id))
                if w.closure:
                    refs.append(EvidenceRef(entity_type="closure", entity_id=w.closure.closure_id))

                # Case 1: Closed without any investigation record
                if w.closure and not w.investigation:
                    signals.append(
                        WorkflowShortcutSignal(
                            cse_id=cse.cse_id,
                            workflow=w,
                            shortcut_type="SKIPPED_INVESTIGATION",
                            duration_seconds=w.closure_duration_seconds or 0.0,
                            evidence_refs=refs,
                        )
                    )
                # Case 2: Instantaneous closure
                elif w.closure_duration_seconds is not None and w.closure_duration_seconds < self.instantaneous_threshold_seconds:
                    if w.investigation:
                        refs.append(
                            EvidenceRef(
                                entity_type="investigation",
                                entity_id=w.investigation.investigation_id,
                            )
                        )
                    signals.append(
                        WorkflowShortcutSignal(
                            cse_id=cse.cse_id,
                            workflow=w,
                            shortcut_type="INSTANTANEOUS_CLOSURE",
                            duration_seconds=w.closure_duration_seconds,
                            evidence_refs=refs,
                        )
                    )

        return signals

"""
Workflow Reconstruction Engine.
Reconstructs the operational evidence chain from Alert -> Investigation -> Case -> Escalation -> Action -> Closure.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from analytics.canonicalization.canonicalization import CanonicalDataset
from backend.models.canonical import (
    Action,
    Alert,
    Asset,
    AssetCriticality,
    Case,
    Closure,
    CSE,
    Escalation,
    Investigation,
    Severity,
)


@dataclass
class ReconstructedWorkflow:
    alert: Alert
    asset: Optional[Asset] = None
    cse: Optional[CSE] = None
    investigation: Optional[Investigation] = None
    case: Optional[Case] = None
    escalations: list[Escalation] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)
    closure: Optional[Closure] = None

    @property
    def closure_duration_seconds(self) -> Optional[float]:
        if self.case and self.closure:
            delta = self.closure.closed_at - self.case.opened_at
            return max(0.0, delta.total_seconds())
        elif self.investigation and self.investigation.ended_at:
            delta = self.investigation.ended_at - self.investigation.started_at
            return max(0.0, delta.total_seconds())
        return None

    @property
    def evidence_count(self) -> int:
        if self.investigation:
            return self.investigation.evidence_count
        return 0

    @property
    def has_escalation(self) -> bool:
        return len(self.escalations) > 0

    @property
    def has_remediation_action(self) -> bool:
        return len(self.actions) > 0


class ReconstructedDataset:
    def __init__(self, dataset: CanonicalDataset):
        self.raw_dataset = dataset
        self.cse_by_id: dict[UUID, CSE] = {c.cse_id: c for c in dataset.cse_list}
        self.assets_by_id: dict[UUID, Asset] = {a.asset_id: a for a in dataset.assets}
        self.investigations_by_alert_id: dict[UUID, Investigation] = {
            inv.alert_id: inv for inv in dataset.investigations
        }
        self.cases_by_alert_id: dict[UUID, Case] = {
            c.alert_id: c for c in dataset.cases
        }
        
        # Group escalations, actions, closures by case_id
        self.escalations_by_case_id: dict[UUID, list[Escalation]] = {}
        for esc in dataset.escalations:
            self.escalations_by_case_id.setdefault(esc.case_id, []).append(esc)

        self.actions_by_case_id: dict[UUID, list[Action]] = {}
        for act in dataset.actions:
            self.actions_by_case_id.setdefault(act.case_id, []).append(act)

        self.closures_by_case_id: dict[UUID, Closure] = {
            clo.case_id: clo for clo in dataset.closures
        }

        # Build workflows
        self.workflows: list[ReconstructedWorkflow] = []
        for alert in dataset.alerts:
            asset = self.assets_by_id.get(alert.asset_id)
            cse = self.cse_by_id.get(alert.cse_id)
            inv = self.investigations_by_alert_id.get(alert.alert_id)
            case = self.cases_by_alert_id.get(alert.alert_id)
            
            escs = self.escalations_by_case_id.get(case.case_id, []) if case else []
            acts = self.actions_by_case_id.get(case.case_id, []) if case else []
            clo = self.closures_by_case_id.get(case.case_id) if case else None

            self.workflows.append(
                ReconstructedWorkflow(
                    alert=alert,
                    asset=asset,
                    cse=cse,
                    investigation=inv,
                    case=case,
                    escalations=escs,
                    actions=acts,
                    closure=clo,
                )
            )

    def get_workflows_for_cse(self, cse_id: UUID) -> list[ReconstructedWorkflow]:
        return [w for w in self.workflows if w.alert.cse_id == cse_id]

    def get_asset_alerts_history(
        self, asset_id: UUID, window_days: int = 30
    ) -> list[ReconstructedWorkflow]:
        asset_wfs = [w for w in self.workflows if w.alert.asset_id == asset_id]
        asset_wfs.sort(key=lambda w: w.alert.event_time)
        return asset_wfs

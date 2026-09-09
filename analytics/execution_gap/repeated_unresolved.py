"""
Repeated Unresolved Alerts Execution-Gap Detector (FR-033).
Flags clusters of alerts recurring on the same asset in the same category without remediation evidence.

Formula:
  flag if count(alerts on same asset_id, same alert_category) >= 3
      AND within a 30-day rolling window
      AND no remediation action record links to any of those alerts
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from uuid import UUID

from analytics.workflow.workflow_reconstruction import ReconstructedDataset, ReconstructedWorkflow
from backend.models.canonical import Asset, EvidenceRef


@dataclass
class RepeatedUnresolvedSignal:
    cse_id: UUID
    asset_id: UUID
    asset_name: str
    alert_category: str
    alert_count: int
    window_days: int
    workflows: list[ReconstructedWorkflow] = field(default_factory=list)
    evidence_refs: list[EvidenceRef] = field(default_factory=list)


class RepeatedUnresolvedDetector:
    def __init__(self, min_occurrences: int = 3, window_days: int = 30):
        self.min_occurrences = min_occurrences
        self.window_days = window_days

    def detect(self, dataset: ReconstructedDataset) -> list[RepeatedUnresolvedSignal]:
        signals: list[RepeatedUnresolvedSignal] = []

        # Group workflows by (cse_id, asset_id, alert_category)
        clusters: dict[tuple[UUID, UUID, str], list[ReconstructedWorkflow]] = {}
        for w in dataset.workflows:
            key = (w.alert.cse_id, w.alert.asset_id, w.alert.alert_category)
            clusters.setdefault(key, []).append(w)

        for (cse_id, asset_id, category), wfs in clusters.items():
            if len(wfs) < self.min_occurrences:
                continue

            # Sort by event time
            wfs_sorted = sorted(wfs, key=lambda w: w.alert.event_time)

            # Sliding window check
            window_delta = timedelta(days=self.window_days)
            n = len(wfs_sorted)

            for i in range(n):
                sub_wfs = [
                    w for w in wfs_sorted[i:]
                    if w.alert.event_time - wfs_sorted[i].alert.event_time <= window_delta
                ]
                if len(sub_wfs) >= self.min_occurrences:
                    # Check if ANY workflow in this cluster has a remediation action
                    has_any_remediation = any(w.has_remediation_action for w in sub_wfs)
                    if not has_any_remediation:
                        refs: list[EvidenceRef] = [
                            EvidenceRef(entity_type="asset", entity_id=asset_id)
                        ]
                        for w in sub_wfs:
                            refs.append(
                                EvidenceRef(entity_type="alert", entity_id=w.alert.alert_id)
                            )
                            if w.case:
                                refs.append(
                                    EvidenceRef(entity_type="case", entity_id=w.case.case_id)
                                )

                        asset = dataset.assets_by_id.get(asset_id)
                        asset_name = f"{asset.asset_type} ({asset.environment})" if asset else str(asset_id)

                        signals.append(
                            RepeatedUnresolvedSignal(
                                cse_id=cse_id,
                                asset_id=asset_id,
                                asset_name=asset_name,
                                alert_category=category,
                                alert_count=len(sub_wfs),
                                window_days=self.window_days,
                                workflows=sub_wfs,
                                evidence_refs=refs,
                            )
                        )
                        # Break out to avoid duplicate sub-window flags for the same cluster
                        break

        return signals

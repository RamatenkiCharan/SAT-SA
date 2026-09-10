"""
Coverage Gap Negative-Space Detector (FR-041).
Identifies critical monitoring gaps (silent assets / missing alert categories) where evidence
should exist under expected operating conditions, safely gated by data quality checks.

Formula:
  flag if observed_count / max(expected_count, 1) < coverage_ratio_threshold (0.3)
      AND DataQualityScore >= min_data_quality_to_flag (0.7)
      AND asset_criticality IN {CRITICAL, HIGH}
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

from analytics.canonicalization.canonicalization import CanonicalDataset
from backend.models.canonical import (
    AssetCriticality,
    EvidenceRef,
    EvidenceSufficiencyState,
)
from backend.models.ruleset import CoverageGapConfig


@dataclass
class CoverageGapSignal:
    cse_id: UUID
    asset_id: Optional[UUID]
    asset_criticality: AssetCriticality
    alert_category: Optional[str]
    observed_count: float
    expected_count: float
    coverage_ratio: float
    data_quality_score: float
    assessment_state: EvidenceSufficiencyState = EvidenceSufficiencyState.SUPPORTED
    evidence_refs: list[EvidenceRef] = field(default_factory=list)


class CoverageGapDetector:
    def __init__(
        self,
        coverage_ratio_threshold: float = 0.3,
        min_data_quality_to_flag: float = 0.7,
        applies_to_criticality: list[str] | None = None,
        config: CoverageGapConfig | None = None,
    ):
        if config is not None:
            self.coverage_ratio_threshold = config.coverage_ratio_threshold
            self.min_data_quality_to_flag = config.min_data_quality_to_flag
            self.applies_to_criticality = list(config.applies_to_criticality)
        else:
            self.coverage_ratio_threshold = coverage_ratio_threshold
            self.min_data_quality_to_flag = min_data_quality_to_flag
            self.applies_to_criticality = applies_to_criticality or ["CRITICAL", "HIGH"]

    def detect(
        self,
        dataset: CanonicalDataset,
        data_quality_score: float,
    ) -> list[CoverageGapSignal]:
        signals: list[CoverageGapSignal] = []

        # Data-quality gate: if data quality is degraded (< 0.7), do NOT raise operational coverage gaps.
        # This prevents converting data ingestion outages into false positive security blind spot findings.
        if data_quality_score < self.min_data_quality_to_flag:
            return signals

        assets_by_id = {a.asset_id: a for a in dataset.assets}

        for obs in dataset.coverage_observations:
            if obs.expected_count <= 0:
                continue

            ratio = obs.observed_count / obs.expected_count
            if ratio < self.coverage_ratio_threshold:
                asset = assets_by_id.get(obs.asset_id) if obs.asset_id else None
                asset_crit = asset.criticality if asset else AssetCriticality.HIGH

                if asset_crit.value in self.applies_to_criticality:
                    refs: list[EvidenceRef] = [
                        EvidenceRef(
                            entity_type="coverage_observation",
                            entity_id=obs.observation_id,
                        )
                    ]
                    if obs.asset_id:
                        refs.append(
                            EvidenceRef(entity_type="asset", entity_id=obs.asset_id)
                        )

                    # Determine sufficiency state based on data trust
                    state = (
                        EvidenceSufficiencyState.SUPPORTED
                        if data_quality_score >= self.min_data_quality_to_flag
                        else EvidenceSufficiencyState.NOT_ASSESSABLE
                    )

                    signals.append(
                        CoverageGapSignal(
                            cse_id=obs.cse_id,
                            asset_id=obs.asset_id,
                            asset_criticality=asset_crit,
                            alert_category=obs.alert_category,
                            observed_count=obs.observed_count,
                            expected_count=obs.expected_count,
                            coverage_ratio=ratio,
                            data_quality_score=data_quality_score,
                            assessment_state=state,
                            evidence_refs=refs,
                        )
                    )

        return signals


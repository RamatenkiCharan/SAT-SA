"""
Analytical Ruleset and Weight Configuration Models.
Defines versioned, immutable ruleset structures for:
  - Data Quality weights & minimum sample thresholds (SRS §7.2.1)
  - Evidence Fusion weights & priority caps (SRS §10.5)
  - Priority thresholds & gating criteria
  - Detector configuration parameters (Fast Closure, Escalation Gap, Repeated Unresolved, Coverage Gap)
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4


@dataclass(frozen=True)
class DataQualityWeights:
    """SRS v2.0 §7.2.1 Data Quality formula weights."""
    completeness_weight: float = 0.30
    consistency_weight: float = 0.25
    coverage_weight: float = 0.25
    sample_sufficiency_weight: float = 0.20
    minimum_sample_size_default: int = 30

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DataQualityWeights:
        return cls(
            completeness_weight=float(data.get("completeness_weight", 0.30)),
            consistency_weight=float(data.get("consistency_weight", 0.25)),
            coverage_weight=float(data.get("coverage_weight", 0.25)),
            sample_sufficiency_weight=float(data.get("sample_sufficiency_weight", 0.20)),
            minimum_sample_size_default=int(data.get("minimum_sample_size_default", 30)),
        )


@dataclass(frozen=True)
class FusionWeights:
    """SRS v2.0 §10.5 Evidence Fusion priority scoring weights."""
    signal_strength_weight: float = 0.30
    peer_deviation_weight: float = 0.25
    persistence_weight: float = 0.20
    asset_criticality_weight: float = 0.15
    data_uncertainty_weight: float = -0.10
    signal_strength_cap: int = 3
    peer_deviation_zscore_cap: float = 3.0
    high_priority_min_independent_signals: int = 2
    high_priority_min_data_quality: float = 0.6

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FusionWeights:
        return cls(
            signal_strength_weight=float(data.get("signal_strength_weight", 0.30)),
            peer_deviation_weight=float(data.get("peer_deviation_weight", 0.25)),
            persistence_weight=float(data.get("persistence_weight", 0.20)),
            asset_criticality_weight=float(data.get("asset_criticality_weight", 0.15)),
            data_uncertainty_weight=float(data.get("data_uncertainty_weight", -0.10)),
            signal_strength_cap=int(data.get("signal_strength_cap", 3)),
            peer_deviation_zscore_cap=float(data.get("peer_deviation_zscore_cap", 3.0)),
            high_priority_min_independent_signals=int(data.get("high_priority_min_independent_signals", 2)),
            high_priority_min_data_quality=float(data.get("high_priority_min_data_quality", 0.6)),
        )


@dataclass(frozen=True)
class PriorityThresholds:
    """Supervisory prioritization & explainability gating thresholds."""
    high_priority_score_threshold: float = 0.75
    medium_priority_score_threshold: float = 0.50
    high_priority_min_independent_signals: int = 2
    high_priority_min_data_quality: float = 0.6
    min_priority_score_to_surface: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PriorityThresholds:
        return cls(
            high_priority_score_threshold=float(data.get("high_priority_score_threshold", 0.75)),
            medium_priority_score_threshold=float(data.get("medium_priority_score_threshold", 0.50)),
            high_priority_min_independent_signals=int(data.get("high_priority_min_independent_signals", 2)),
            high_priority_min_data_quality=float(data.get("high_priority_min_data_quality", 0.6)),
            min_priority_score_to_surface=float(data.get("min_priority_score_to_surface", 0.0)),
        )


@dataclass(frozen=True)
class FastClosureConfig:
    mad_multiplier: float = 2.5
    investigation_evidence_percentile: int = 25
    min_peer_group_size: int = 5

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FastClosureConfig:
        return cls(
            mad_multiplier=float(data.get("mad_multiplier", 2.5)),
            investigation_evidence_percentile=int(data.get("investigation_evidence_percentile", 25)),
            min_peer_group_size=int(data.get("min_peer_group_size", 5)),
        )


@dataclass(frozen=True)
class EscalationGapConfig:
    applies_to_severity: list[str] = field(default_factory=lambda: ["CRITICAL"])
    high_impact_categories: list[str] = field(default_factory=lambda: [
        "ransomware",
        "scada intrusion",
        "data exfiltration",
        "privilege escalation",
        "unauthorized access",
        "malware execution",
        "command and control",
    ])

    def to_dict(self) -> dict[str, Any]:
        return {
            "applies_to_severity": list(self.applies_to_severity),
            "high_impact_categories": list(self.high_impact_categories),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EscalationGapConfig:
        return cls(
            applies_to_severity=list(data.get("applies_to_severity", ["CRITICAL"])),
            high_impact_categories=list(data.get("high_impact_categories", [
                "ransomware",
                "scada intrusion",
                "data exfiltration",
                "privilege escalation",
                "unauthorized access",
                "malware execution",
                "command and control",
            ])),
        )


@dataclass(frozen=True)
class RepeatedUnresolvedConfig:
    min_occurrences: int = 3
    window_days: int = 30

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RepeatedUnresolvedConfig:
        return cls(
            min_occurrences=int(data.get("min_occurrences", 3)),
            window_days=int(data.get("window_days", 30)),
        )


@dataclass(frozen=True)
class CoverageGapConfig:
    coverage_ratio_threshold: float = 0.3
    min_data_quality_to_flag: float = 0.7
    applies_to_criticality: list[str] = field(default_factory=lambda: ["CRITICAL", "HIGH"])

    def to_dict(self) -> dict[str, Any]:
        return {
            "coverage_ratio_threshold": self.coverage_ratio_threshold,
            "min_data_quality_to_flag": self.min_data_quality_to_flag,
            "applies_to_criticality": list(self.applies_to_criticality),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CoverageGapConfig:
        return cls(
            coverage_ratio_threshold=float(data.get("coverage_ratio_threshold", 0.3)),
            min_data_quality_to_flag=float(data.get("min_data_quality_to_flag", 0.7)),
            applies_to_criticality=list(data.get("applies_to_criticality", ["CRITICAL", "HIGH"])),
        )


@dataclass(frozen=True)
class DetectorConfig:
    fast_closure: FastClosureConfig = field(default_factory=FastClosureConfig)
    escalation_gap: EscalationGapConfig = field(default_factory=EscalationGapConfig)
    repeated_unresolved: RepeatedUnresolvedConfig = field(default_factory=RepeatedUnresolvedConfig)
    coverage_gap: CoverageGapConfig = field(default_factory=CoverageGapConfig)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fast_closure": self.fast_closure.to_dict(),
            "escalation_gap": self.escalation_gap.to_dict(),
            "repeated_unresolved": self.repeated_unresolved.to_dict(),
            "coverage_gap": self.coverage_gap.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> DetectorConfig:
        d = data or {}
        return cls(
            fast_closure=FastClosureConfig.from_dict(d.get("fast_closure") or {}),
            escalation_gap=EscalationGapConfig.from_dict(d.get("escalation_gap") or {}),
            repeated_unresolved=RepeatedUnresolvedConfig.from_dict(d.get("repeated_unresolved") or {}),
            coverage_gap=CoverageGapConfig.from_dict(d.get("coverage_gap") or {}),
        )


@dataclass
class AnalyticalRuleset:
    """
    Complete, versioned ruleset bundle governing:
      - Data Quality calculation
      - Evidence Fusion & priority ranking
      - Priority & Explainability thresholds
      - Execution-Gap & Coverage detector parameters
    """
    ruleset_id: UUID
    version: str
    name: str
    is_active: bool
    effective_timestamp: datetime
    author: str
    rationale: str
    dq_weights: DataQualityWeights = field(default_factory=DataQualityWeights)
    fusion_weights: FusionWeights = field(default_factory=FusionWeights)
    thresholds: PriorityThresholds = field(default_factory=PriorityThresholds)
    detector_config: DetectorConfig = field(default_factory=DetectorConfig)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ruleset_id": str(self.ruleset_id),
            "version": self.version,
            "name": self.name,
            "is_active": self.is_active,
            "effective_timestamp": self.effective_timestamp.isoformat(),
            "author": self.author,
            "rationale": self.rationale,
            "dq_weights": self.dq_weights.to_dict(),
            "fusion_weights": self.fusion_weights.to_dict(),
            "thresholds": self.thresholds.to_dict(),
            "detector_config": self.detector_config.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AnalyticalRuleset:
        d = data or {}
        rid = UUID(d["ruleset_id"]) if isinstance(d.get("ruleset_id"), str) else d.get("ruleset_id", uuid4())
        eff_raw = d.get("effective_timestamp")
        if isinstance(eff_raw, str):
            try:
                eff = datetime.fromisoformat(eff_raw.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("effective_timestamp must be an ISO-8601 timestamp.") from exc
        elif isinstance(eff_raw, datetime):
            eff = eff_raw
        else:
            eff = datetime.now(timezone.utc)

        return cls(
            ruleset_id=rid,
            version=str(d.get("version", "V1")),
            name=str(d.get("name", "Default Authoritative Ruleset")),
            is_active=bool(d.get("is_active", False)),
            effective_timestamp=eff,
            author=str(d.get("author", "SAT-SA Core")),
            rationale=str(d.get("rationale", "Standard Authoritative Configuration")),
            dq_weights=DataQualityWeights.from_dict(d.get("dq_weights") or {}),
            fusion_weights=FusionWeights.from_dict(d.get("fusion_weights") or {}),
            thresholds=PriorityThresholds.from_dict(d.get("thresholds") or {}),
            detector_config=DetectorConfig.from_dict(d.get("detector_config") or {}),
        )



# Authoritative baseline ruleset V1 (SRS v2.0 §7.2.1, §7.4.1, §7.5.1, §10.5)
DEFAULT_AUTHORITATIVE_RULESET_V1 = AnalyticalRuleset(
    ruleset_id=UUID("00000000-0000-0000-0000-000000000001"),
    version="V1",
    name="NCIIPC Authoritative Supervisory Baseline Ruleset (SRS v2.0)",
    is_active=True,
    effective_timestamp=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    author="SAT-SA Engineering Team / NCIIPC Technical Committee",
    rationale="Pinned authoritative formula weights (DQ 0.30/0.25/0.25/0.20, Fusion 0.30/0.25/0.20/0.15/-0.10, MAD 2.5).",
    dq_weights=DataQualityWeights(),
    fusion_weights=FusionWeights(),
    thresholds=PriorityThresholds(),
    detector_config=DetectorConfig(),
)

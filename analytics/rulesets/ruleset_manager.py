"""
Ruleset Manager & Versioned Configuration Engine (SRS §24 / §52).
Stores and versions data quality weights, fusion weights, and detector thresholds.
Ensures every analysis run and finding is traceable back to an immutable, versioned ruleset.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4


@dataclass
class RulesetRecord:
    ruleset_id: UUID
    ruleset_version: str  # e.g., "V1", "V2"
    name: str
    description: str
    created_at: datetime
    data_quality_weights: dict[str, float]
    fusion_weights: dict[str, Any]
    detector_thresholds: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["ruleset_id"] = str(self.ruleset_id)
        d["created_at"] = self.created_at.isoformat()
        return d


# Default NCIIPC Baseline Ruleset V1
RULESET_V1_DEFAULT = RulesetRecord(
    ruleset_id=UUID("00000000-0000-0000-0000-000000000001"),
    ruleset_version="V1",
    name="NCIIPC Standard Critical Infrastructure Ruleset V1",
    description="Baseline supervisory ruleset containing §7.2.1 Data Trust ratios and §10.5 5-component fusion formula.",
    created_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    data_quality_weights={
        "completeness_weight": 0.35,
        "consistency_weight": 0.25,
        "coverage_weight": 0.25,
        "sample_sufficiency_weight": 0.15,
        "minimum_sample_size": 30,
    },
    fusion_weights={
        "signal_strength_weight": 0.30,
        "peer_deviation_weight": 0.25,
        "persistence_weight": 0.20,
        "asset_criticality_weight": 0.15,
        "data_uncertainty_weight": -0.10,
        "signal_strength_cap": 3,
        "peer_deviation_zscore_cap": 3.0,
        "high_priority_min_independent_signals": 2,
        "high_priority_min_data_quality": 0.6,
    },
    detector_thresholds={
        "fast_closure_mad_multiplier": 2.5,
        "fast_closure_evidence_percentile": 25,
        "escalation_gap_severity": "CRITICAL",
        "repeated_unresolved_window_days": 30,
        "repeated_unresolved_min_alerts": 3,
        "coverage_gap_ratio_threshold": 0.30,
        "coverage_gap_min_dq_gate": 0.70,
        "investigation_min_evidence": 1,
        "investigation_min_duration_seconds": 60.0,
        "workflow_shortcut_max_duration_seconds": 10.0,
    },
)

_RULESETS_REGISTRY: dict[str, RulesetRecord] = {
    "V1": RULESET_V1_DEFAULT,
}


def get_ruleset(version: str = "V1") -> RulesetRecord:
    return _RULESETS_REGISTRY.get(version.upper(), RULESET_V1_DEFAULT)


def list_rulesets() -> list[RulesetRecord]:
    return list(_RULESETS_REGISTRY.values())


def register_ruleset(ruleset: RulesetRecord) -> None:
    _RULESETS_REGISTRY[ruleset.ruleset_version.upper()] = ruleset

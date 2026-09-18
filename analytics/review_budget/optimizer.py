"""
INNOVATION PHASE 4: SUPERVISORY REVIEW-BUDGET OPTIMIZER

Core question:
"If a human supervisor can inspect only a limited number of cases,
which cases should be selected to maximize useful supervisory information?"

This is NOT simply "select the highest-risk cases."
This is: "Select a diverse, informative, evidence-grounded sample that gives
the supervisor maximum useful coverage of the SOC's operational behavior."

Architecture:
- Consumes the EXISTING supervisory priority scores from Evidence Fusion.
- Does NOT replace or modify them.
- Adds a greedy marginal-gain selection layer on top.

Temporal contradictions: NOT SUPPORTED (documented scope boundary).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4
import random

from backend.models.canonical import Finding, FindingType


# ---------------------------------------------------------------------------
# Selection reason taxonomy
# ---------------------------------------------------------------------------
class SelectionReason:
    HIGH_PRIORITY = "High supervisory priority with strong evidentiary support."
    UNCERTAINTY = "Selected because human review can resolve important uncertainty."
    CONTRADICTION = "Selected because evidence contradiction is unresolved."
    COVERAGE_CSE = "Selected because it adds a new entity (CSE) not yet represented."
    COVERAGE_TYPE = "Selected because it represents a new finding type not yet covered."
    COVERAGE_PERIOD = "Selected because it adds a new reporting period to the sample."
    DIVERSITY = "Selected because it represents a different operational behavior pattern."
    CONTROL = "Selected as a deterministic control sample for bias detection."


@dataclass
class SelectedReviewItem:
    """A single item in the review-budget sample."""
    finding_id: UUID
    finding: Finding
    selection_rank: int
    selection_reasons: list[str]
    marginal_value: float
    priority_contribution: float
    uncertainty_contribution: float
    contradiction_contribution: float
    coverage_contribution: float
    diversity_contribution: float
    is_control_sample: bool


@dataclass
class ReviewBudgetReport:
    """Summary of a review-budget optimization run."""
    budget: int
    candidate_count: int
    selected_count: int
    selected_items: list[SelectedReviewItem]
    cse_coverage: dict[str, Any]
    period_coverage: dict[str, Any]
    finding_type_coverage: dict[str, Any]
    control_sample_count: int
    selection_seed: int
    dataset_version_id: Optional[UUID] = None
    analysis_run_id: Optional[UUID] = None
    ruleset_version: Optional[str] = None
    computed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "budget": self.budget,
            "candidate_count": self.candidate_count,
            "selected_count": self.selected_count,
            "selected_items": [
                {
                    "finding_id": str(item.finding_id),
                    "selection_rank": item.selection_rank,
                    "selection_reasons": item.selection_reasons,
                    "marginal_value": round(item.marginal_value, 4),
                    "priority_contribution": round(item.priority_contribution, 4),
                    "uncertainty_contribution": round(item.uncertainty_contribution, 4),
                    "contradiction_contribution": round(item.contradiction_contribution, 4),
                    "coverage_contribution": round(item.coverage_contribution, 4),
                    "diversity_contribution": round(item.diversity_contribution, 4),
                    "is_control_sample": item.is_control_sample,
                    "finding_type": item.finding.finding_type.value,
                    "cse_id": str(item.finding.cse_id),
                    "reporting_period_id": str(item.finding.reporting_period_id),
                    "priority_score": round(item.finding.priority_score, 4),
                    "evidentiary_confidence": round(item.finding.evidentiary_confidence, 2),
                    "evidence_state": item.finding.evidence_state.value,
                    "evidence_record_count": len(item.finding.evidence_refs),
                }
                for item in self.selected_items
            ],
            "coverage": {
                "cses_represented": self.cse_coverage.get("represented", 0),
                "cses_total": self.cse_coverage.get("total", 0),
                "periods_represented": self.period_coverage.get("represented", 0),
                "periods_total": self.period_coverage.get("total", 0),
                "finding_types_represented": self.finding_type_coverage.get("represented", 0),
                "finding_types_total": self.finding_type_coverage.get("total", 0),
                "control_samples": self.control_sample_count,
            },
            "selection_seed": self.selection_seed,
            "dataset_version_id": str(self.dataset_version_id) if self.dataset_version_id else None,
            "analysis_run_id": str(self.analysis_run_id) if self.analysis_run_id else None,
            "ruleset_version": self.ruleset_version,
            "computed_at": self.computed_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# Supervisor Review-Budget Optimizer
# ---------------------------------------------------------------------------
class ReviewBudgetOptimizer:
    """
    Greedy marginal-gain selection that balances:
    1. Supervisory priority (existing fusion scores)
    2. Uncertainty (human review can resolve)
    3. Contradiction (evidence sources disagree)
    4. Coverage (entities, periods, finding types)
    5. Diversity (avoid redundant patterns)
    6. Control (deterministic random control sample)
    """

    def __init__(
        self,
        control_fraction: float = 0.10,
        seed: int = 42,
    ):
        self.control_fraction = max(0.0, min(0.5, control_fraction))
        self.seed = seed

    def optimize(
        self,
        candidates: list[Finding],
        budget: int,
        dataset_version_id: UUID | None = None,
        analysis_run_id: UUID | None = None,
        ruleset_version: str | None = None,
    ) -> ReviewBudgetReport:
        """
        Select up to `budget` findings from `candidates` to maximize
        supervisory coverage and information value.
        """
        now = datetime.now(timezone.utc)

        # Edge cases
        if budget <= 0 or not candidates:
            return ReviewBudgetReport(
                budget=budget,
                candidate_count=len(candidates),
                selected_count=0,
                selected_items=[],
                cse_coverage={"represented": 0, "total": len(set(c.cse_id for c in candidates))},
                period_coverage={"represented": 0, "total": len(set(c.reporting_period_id for c in candidates))},
                finding_type_coverage={"represented": 0, "total": len(set(c.finding_type for c in candidates))},
                control_sample_count=0,
                selection_seed=self.seed,
                dataset_version_id=dataset_version_id,
                analysis_run_id=analysis_run_id,
                ruleset_version=ruleset_version,
                computed_at=now,
            )

        effective_budget = min(budget, len(candidates))

        # Deduplicate: group by (cse_id, finding_type, reporting_period_id)
        # Keep highest priority from each group
        dedup_map: dict[tuple, Finding] = {}
        for f in candidates:
            key = (f.cse_id, f.finding_type, f.reporting_period_id)
            if key not in dedup_map or f.priority_score > dedup_map[key].priority_score:
                dedup_map[key] = f
        unique_candidates = list(dedup_map.values())

        effective_budget = min(effective_budget, len(unique_candidates))

        # Compute universe sets
        all_cse_ids = set(f.cse_id for f in unique_candidates)
        all_period_ids = set(f.reporting_period_id for f in unique_candidates)
        all_types = set(f.finding_type for f in unique_candidates)

        # Reserve control sample slots
        n_control = max(1, int(effective_budget * self.control_fraction)) if effective_budget >= 3 else 0
        n_greedy = effective_budget - n_control

        # Greedy marginal-gain selection
        selected: list[SelectedReviewItem] = []
        remaining = list(unique_candidates)

        # Track what's already covered
        covered_cses: set[UUID] = set()
        covered_periods: set[UUID] = set()
        covered_types: set[FindingType] = set()
        covered_patterns: set[str] = set()  # (cse_id, finding_type) as diversity key

        rank = 0
        for _ in range(n_greedy):
            if not remaining:
                break

            best_item = None
            best_value = -1.0
            best_reasons: list[str] = []
            best_components: dict[str, float] = {}

            for f in remaining:
                priority_v = f.priority_score

                # Uncertainty value: low confidence or weakly supported = high uncertainty value
                uncertainty_v = 0.0
                if f.evidentiary_confidence < 0.6:
                    uncertainty_v = 0.4 * (1.0 - f.evidentiary_confidence)
                if f.evidence_state.value in ("WEAKLY_SUPPORTED", "INSUFFICIENT_EVIDENCE"):
                    uncertainty_v += 0.2

                # Contradiction value
                contradiction_v = 0.0
                if f.finding_type == FindingType.EVIDENCE_CONTRADICTION:
                    contradiction_v = 0.3

                # Coverage value: marginal gain from adding new dimensions
                coverage_v = 0.0
                if f.cse_id not in covered_cses:
                    coverage_v += 0.25
                if f.reporting_period_id not in covered_periods:
                    coverage_v += 0.15
                if f.finding_type not in covered_types:
                    coverage_v += 0.20

                # Diversity value: penalize patterns already covered
                pattern_key = f"{f.cse_id}:{f.finding_type.value}"
                diversity_v = 0.15 if pattern_key not in covered_patterns else 0.0

                # Composite marginal value
                marginal = (
                    0.35 * priority_v
                    + 1.0 * uncertainty_v
                    + 1.0 * contradiction_v
                    + 1.0 * coverage_v
                    + 1.0 * diversity_v
                )

                if marginal > best_value:
                    best_value = marginal
                    best_item = f
                    best_components = {
                        "priority": priority_v,
                        "uncertainty": uncertainty_v,
                        "contradiction": contradiction_v,
                        "coverage": coverage_v,
                        "diversity": diversity_v,
                    }

            if best_item is None:
                break

            rank += 1
            reasons = _build_reasons(best_item, best_components, covered_cses, covered_types, covered_periods)
            selected.append(SelectedReviewItem(
                finding_id=best_item.finding_id,
                finding=best_item,
                selection_rank=rank,
                selection_reasons=reasons,
                marginal_value=best_value,
                priority_contribution=best_components["priority"],
                uncertainty_contribution=best_components["uncertainty"],
                contradiction_contribution=best_components["contradiction"],
                coverage_contribution=best_components["coverage"],
                diversity_contribution=best_components["diversity"],
                is_control_sample=False,
            ))

            # Update covered sets
            covered_cses.add(best_item.cse_id)
            covered_periods.add(best_item.reporting_period_id)
            covered_types.add(best_item.finding_type)
            covered_patterns.add(f"{best_item.cse_id}:{best_item.finding_type.value}")
            remaining.remove(best_item)

        # Control sample: deterministic seeded selection from remaining
        selected_ids = set(s.finding_id for s in selected)
        control_pool = [f for f in unique_candidates if f.finding_id not in selected_ids]

        if n_control > 0 and control_pool:
            rng = random.Random(self.seed)
            n_actual_control = min(n_control, len(control_pool))
            control_picks = rng.sample(control_pool, n_actual_control)

            for cf in control_picks:
                rank += 1
                selected.append(SelectedReviewItem(
                    finding_id=cf.finding_id,
                    finding=cf,
                    selection_rank=rank,
                    selection_reasons=[SelectionReason.CONTROL],
                    marginal_value=0.0,
                    priority_contribution=cf.priority_score,
                    uncertainty_contribution=0.0,
                    contradiction_contribution=0.0,
                    coverage_contribution=0.0,
                    diversity_contribution=0.0,
                    is_control_sample=True,
                ))
                covered_cses.add(cf.cse_id)
                covered_periods.add(cf.reporting_period_id)
                covered_types.add(cf.finding_type)

        actual_control_count = sum(1 for s in selected if s.is_control_sample)

        return ReviewBudgetReport(
            budget=budget,
            candidate_count=len(candidates),
            selected_count=len(selected),
            selected_items=selected,
            cse_coverage={
                "represented": len(covered_cses),
                "total": len(all_cse_ids),
            },
            period_coverage={
                "represented": len(covered_periods),
                "total": len(all_period_ids),
            },
            finding_type_coverage={
                "represented": len(covered_types),
                "total": len(all_types),
            },
            control_sample_count=actual_control_count,
            selection_seed=self.seed,
            dataset_version_id=dataset_version_id,
            analysis_run_id=analysis_run_id,
            ruleset_version=ruleset_version,
            computed_at=now,
        )


def _build_reasons(
    f: Finding,
    components: dict[str, float],
    covered_cses: set[UUID],
    covered_types: set[FindingType],
    covered_periods: set[UUID],
) -> list[str]:
    """Build human-readable selection reasons."""
    reasons = []
    if f.priority_score >= 0.75:
        reasons.append(SelectionReason.HIGH_PRIORITY)
    if components["uncertainty"] > 0.1:
        reasons.append(SelectionReason.UNCERTAINTY)
    if components["contradiction"] > 0:
        reasons.append(SelectionReason.CONTRADICTION)
    if f.cse_id not in covered_cses:
        reasons.append(SelectionReason.COVERAGE_CSE)
    if f.finding_type not in covered_types:
        reasons.append(SelectionReason.COVERAGE_TYPE)
    if f.reporting_period_id not in covered_periods:
        reasons.append(SelectionReason.COVERAGE_PERIOD)
    if components["diversity"] > 0:
        reasons.append(SelectionReason.DIVERSITY)
    if not reasons:
        reasons.append(SelectionReason.HIGH_PRIORITY)
    return reasons

"""
INNOVATION PHASE 5: SUPERVISORY DECISION STABILITY ANALYSIS

Evaluates the sensitivity of the review sample selection to changes in
analytical ruleset weights (FusionWeights). Operates completely read-only
on existing findings by utilizing the cached 'priority_components' (T,D,B,C,A).
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from analytics.fusion.evidence_fusion import compute_priority_tier
from analytics.review_budget.optimizer import ReviewBudgetOptimizer, ReviewBudgetReport
from backend.models.canonical import Finding
from backend.models.ruleset import DEFAULT_AUTHORITATIVE_RULESET_V1, FusionWeights


@dataclass
class PerturbedConfiguration:
    name: str
    magnitude: float
    weights: dict[str, float]
    normalization_method: str = "L1_preserve_signs"


@dataclass
class RankStabilityMetrics:
    spearman_rho: float
    mean_displacement: float
    max_displacement: int
    inversions: int


@dataclass
class ReviewSetStabilityMetrics:
    budget_k: int
    intersection_size: int
    union_size: int
    jaccard_similarity: float
    overlap_percentage: float
    entrant_count: int
    exit_count: int
    explanations: list[str]


@dataclass
class StabilityResult:
    configuration: PerturbedConfiguration
    score_mae: float
    score_max_delta: float
    rank_metrics: RankStabilityMetrics
    review_set_metrics: dict[int, ReviewSetStabilityMetrics]
    high_tier_crossings_out: int
    high_tier_crossings_in: int


@dataclass
class StabilityReport:
    dataset_version_id: UUID
    analysis_run_id: Optional[UUID]
    baseline_ruleset_version: str
    baseline_weights: dict[str, float]
    population_size: int
    optimizer_seed: int
    results: list[StabilityResult]
    computed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_version_id": str(self.dataset_version_id),
            "analysis_run_id": str(self.analysis_run_id) if self.analysis_run_id else None,
            "baseline_ruleset_version": self.baseline_ruleset_version,
            "baseline_weights": self.baseline_weights,
            "population_size": self.population_size,
            "optimizer_seed": self.optimizer_seed,
            "computed_at": self.computed_at.isoformat(),
            "results": [
                {
                    "configuration": {
                        "name": r.configuration.name,
                        "magnitude": r.configuration.magnitude,
                        "weights": {k: round(v, 4) for k, v in r.configuration.weights.items()},
                    },
                    "score_mae": round(r.score_mae, 4),
                    "score_max_delta": round(r.score_max_delta, 4),
                    "rank_metrics": {
                        "spearman_rho": round(r.rank_metrics.spearman_rho, 4),
                        "mean_displacement": round(r.rank_metrics.mean_displacement, 2),
                        "max_displacement": r.rank_metrics.max_displacement,
                        "inversions": r.rank_metrics.inversions,
                    },
                    "review_set_metrics": {
                        str(k): {
                            "budget_k": v.budget_k,
                            "intersection_size": v.intersection_size,
                            "union_size": v.union_size,
                            "jaccard_similarity": round(v.jaccard_similarity, 4),
                            "overlap_percentage": round(v.overlap_percentage, 4),
                            "entrant_count": v.entrant_count,
                            "exit_count": v.exit_count,
                            "explanations": v.explanations,
                        }
                        for k, v in r.review_set_metrics.items()
                    },
                    "threshold_crossings": {
                        "high_tier_crossings_out": r.high_tier_crossings_out,
                        "high_tier_crossings_in": r.high_tier_crossings_in,
                    }
                }
                for r in self.results
            ]
        }


def compute_spearman(rank_base: list[UUID], rank_pert: list[UUID]) -> float:
    """Computes Spearman Rank Correlation Coefficient cleanly."""
    if len(rank_base) < 2:
        return 1.0
    n = len(rank_base)
    base_pos = {uid: i for i, uid in enumerate(rank_base)}
    pert_pos = {uid: i for i, uid in enumerate(rank_pert)}

    d_sq_sum = sum((base_pos[uid] - pert_pos[uid]) ** 2 for uid in rank_base)
    rho = 1 - (6 * d_sq_sum) / (n * (n**2 - 1))
    return max(-1.0, min(1.0, rho))


def generate_perturbations(
    base_weights: dict[str, float], magnitudes: list[float]
) -> list[PerturbedConfiguration]:
    """
    Generates deterministic valid perturbations.
    For each magnitude, shifts weight toward one of the 4 positive components (T, D, B, C)
    and uniformly subtracts from the others to maintain L1 sum.
    A negative component (A) is kept static to preserve penalty mechanics.
    """
    configs = []
    positive_keys = ["signal_strength_weight", "peer_deviation_weight", "persistence_weight", "asset_criticality_weight"]
    
    for mag in magnitudes:
        for target_key in positive_keys:
            new_w = dict(base_weights)
            
            # Add magnitude to target, subtract mag/3 from the other 3
            new_w[target_key] += mag
            others = [k for k in positive_keys if k != target_key]
            sub = mag / len(others)
            for ok in others:
                new_w[ok] -= sub
                
            # Floor at 0.0 for positive keys to remain mathematically valid
            correction = 0.0
            for pk in positive_keys:
                if new_w[pk] < 0.0:
                    correction += abs(new_w[pk])
                    new_w[pk] = 0.0
            
            # If we floored anything, we must add the correction back to maintain sum
            if correction > 0:
                new_w[target_key] -= correction # Take it from the boosted key
                if new_w[target_key] < 0:
                    new_w[target_key] = 0.0 # Extreme edge case fallback

            configs.append(PerturbedConfiguration(
                name=f"+{int(mag*100)}% {target_key.split('_')[0].upper()}",
                magnitude=mag,
                weights=new_w,
            ))
    return configs


class StabilityAnalyzer:
    """
    Executes a read-only decision stability analysis.
    Evaluates how rank and top-K review samples change under perturbed assumptions.
    """
    def __init__(self, optimizer_seed: int = 42):
        self.optimizer_seed = optimizer_seed

    def analyze(
        self,
        findings: list[Finding],
        dataset_version_id: UUID,
        analysis_run_id: Optional[UUID] = None,
        baseline_ruleset_version: str = "V1",
        budgets: list[int] = [1, 5, 10, 25],
        magnitudes: list[float] = [0.05, 0.10, 0.15, 0.20],
    ) -> StabilityReport:
        
        # 1. Capture baseline weights
        base_w = DEFAULT_AUTHORITATIVE_RULESET_V1.fusion_weights.to_dict()
        
        # 2. Sort baseline population accurately
        # Tie-breaker: finding_id to guarantee deterministic stable sort
        base_population = sorted(
            findings, 
            key=lambda f: (f.priority_score, str(f.finding_id)), 
            reverse=True
        )
        base_ranks = [f.finding_id for f in base_population]
        
        # 3. Run baseline optimizer for each budget
        base_reviews: dict[int, ReviewBudgetReport] = {}
        for k in budgets:
            opt = ReviewBudgetOptimizer(seed=self.optimizer_seed)
            base_reviews[k] = opt.optimize(
                candidates=base_population,
                budget=k,
                dataset_version_id=dataset_version_id
            )

        # 4. Generate perturbations
        configs = generate_perturbations(base_w, magnitudes)
        results = []

        for config in configs:
            # 5. Recompute scores statelessly
            cloned_findings = []
            score_deltas = []
            crossings_out = 0
            crossings_in = 0
            
            for base_f in base_population:
                f_clone = copy.copy(base_f)
                comp = f_clone.priority_components
                
                if not comp:
                    # Fallback if somehow missing
                    cloned_findings.append(f_clone)
                    score_deltas.append(0.0)
                    continue

                # Reapply dot product
                w = config.weights
                raw_score = (
                    w.get("signal_strength_weight", 0.3) * comp.get("T", 0.0) +
                    w.get("peer_deviation_weight", 0.25) * comp.get("D", 0.0) +
                    w.get("persistence_weight", 0.2) * comp.get("B", 0.0) +
                    w.get("asset_criticality_weight", 0.15) * comp.get("C", 0.0) +
                    w.get("data_uncertainty_weight", -0.1) * comp.get("A", 0.0)
                )
                new_score = max(0.0, min(1.0, raw_score))
                delta = abs(new_score - base_f.priority_score)
                score_deltas.append(delta)
                
                # Check threshold crossing (0.75 is HIGH)
                was_high = base_f.priority_score >= 0.75
                is_high = new_score >= 0.75
                if was_high and not is_high:
                    crossings_out += 1
                elif not was_high and is_high:
                    crossings_in += 1
                
                f_clone.priority_score = new_score
                cloned_findings.append(f_clone)

            score_mae = sum(score_deltas) / len(score_deltas) if score_deltas else 0.0
            score_max = max(score_deltas) if score_deltas else 0.0

            # 6. Re-rank
            pert_population = sorted(
                cloned_findings, 
                key=lambda f: (f.priority_score, str(f.finding_id)), 
                reverse=True
            )
            pert_ranks = [f.finding_id for f in pert_population]
            
            # Rank Metrics
            spearman = compute_spearman(base_ranks, pert_ranks)
            
            base_pos = {uid: i for i, uid in enumerate(base_ranks)}
            pert_pos = {uid: i for i, uid in enumerate(pert_ranks)}
            
            displacements = [abs(base_pos[uid] - pert_pos[uid]) for uid in base_ranks]
            mean_disp = sum(displacements) / len(displacements) if displacements else 0.0
            max_disp = max(displacements) if displacements else 0

            # Count inversions (O(N^2) naive, but N is small for our budget usually. We do it globally here)
            # To optimize, we just count pairs that flip relative order.
            inversions = 0
            for i in range(len(base_ranks)):
                for j in range(i + 1, len(base_ranks)):
                    u1, u2 = base_ranks[i], base_ranks[j]
                    if pert_pos[u1] > pert_pos[u2]:
                        inversions += 1

            rank_metrics = RankStabilityMetrics(
                spearman_rho=spearman,
                mean_displacement=mean_disp,
                max_displacement=max_disp,
                inversions=inversions
            )

            # 7. Re-optimize for budgets
            set_metrics = {}
            for k in budgets:
                opt = ReviewBudgetOptimizer(seed=self.optimizer_seed)
                pert_report = opt.optimize(
                    candidates=pert_population,
                    budget=k,
                    dataset_version_id=dataset_version_id
                )
                
                base_set = set(item.finding_id for item in base_reviews[k].selected_items)
                pert_set = set(item.finding_id for item in pert_report.selected_items)
                
                intersection = base_set.intersection(pert_set)
                union = base_set.union(pert_set)
                
                jaccard = len(intersection) / len(union) if union else 1.0
                overlap_pct = len(intersection) / len(base_set) if base_set else 1.0
                
                entrants = pert_set - base_set
                exits = base_set - pert_set
                
                explanations = []
                for entrant in entrants:
                    explanations.append(f"Finding {str(entrant)[:8]} entered Top-{k} under {config.name} perturbation due to relative priority increase.")
                
                set_metrics[k] = ReviewSetStabilityMetrics(
                    budget_k=k,
                    intersection_size=len(intersection),
                    union_size=len(union),
                    jaccard_similarity=jaccard,
                    overlap_percentage=overlap_pct,
                    entrant_count=len(entrants),
                    exit_count=len(exits),
                    explanations=explanations[:3]  # Limit to top 3 explanations
                )

            results.append(StabilityResult(
                configuration=config,
                score_mae=score_mae,
                score_max_delta=score_max,
                rank_metrics=rank_metrics,
                review_set_metrics=set_metrics,
                high_tier_crossings_out=crossings_out,
                high_tier_crossings_in=crossings_in
            ))

        return StabilityReport(
            dataset_version_id=dataset_version_id,
            analysis_run_id=analysis_run_id,
            baseline_ruleset_version=baseline_ruleset_version,
            baseline_weights=base_w,
            population_size=len(findings),
            optimizer_seed=self.optimizer_seed,
            results=results
        )

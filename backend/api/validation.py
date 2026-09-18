"""Validation API endpoints for the current robust synthetic protocol."""
from __future__ import annotations

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from analytics.evaluation.review_efficiency import run_review_efficiency_benchmark
from analytics.evaluation.robust_validation import RobustValidationEngine
from analytics.evaluation.stability import StabilityAnalyzer
from backend.models.ruleset import DEFAULT_AUTHORITATIVE_RULESET_V1
from backend.repositories.in_memory_repo import SATRepository, get_repository
from backend.security.auth import UserContext, require_supervisor

router = APIRouter(prefix="/api/validation", tags=["validation"])


class StabilityRequest(BaseModel):
    dataset_version_id: str | None = Field(None, description="Target dataset version to analyze.")
    magnitudes: list[float] = Field([0.05, 0.10, 0.15, 0.20], description="List of perturbation magnitudes to test.")
    budgets: list[int] = Field([1, 5, 10, 25], description="List of Review Budget sizes (K) to evaluate for overlap.")
    optimizer_seed: int = Field(42, description="Seed for deterministic control sampling in ReviewBudgetOptimizer.")


class ValidationMetricsResponse(BaseModel):
    tp: int
    fp: int
    tn: int
    fn: int
    precision: float
    recall: float
    f1_score: float
    fpr: float
    precision_ci: str | None = None
    recall_ci: str | None = None


class RankingMetricsResponse(BaseModel):
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float


class ThresholdSensitivityResponse(BaseModel):
    threshold: float
    precision: float
    recall: float
    f1: float
    fpr: float


class WeightSensitivityResponse(BaseModel):
    weight: str
    original: float
    perturbed: float
    f1: float
    delta_f1: float
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    delta_recall_at_5: float


class ValidationProtocolResponse(BaseModel):
    protocol_version: str
    limitation_notice: str
    total_scenarios: int
    tuning_scenarios: int
    held_out_scenarios: int
    held_out_ratio: float
    hard_negative_count: int
    hard_negative_fp_count: int
    hard_negative_tn_count: int
    tuning_metrics: ValidationMetricsResponse
    held_out_metrics: ValidationMetricsResponse
    tuning_ranking: RankingMetricsResponse
    held_out_ranking: RankingMetricsResponse
    threshold_sensitivity: list[ThresholdSensitivityResponse]
    weight_sensitivity: list[WeightSensitivityResponse]


def _run_current_validation_protocol() -> ValidationProtocolResponse:
    """Run the single authoritative validation protocol used by the UI."""
    result = RobustValidationEngine(
        n_scenarios=240,
        n_bootstrap=200,
        ruleset=DEFAULT_AUTHORITATIVE_RULESET_V1,
    ).run(seed=42)
    return ValidationProtocolResponse.model_validate(result.to_dict())


@router.post("/stability")
def run_stability_analysis(
    req: StabilityRequest,
    repo: SATRepository = Depends(get_repository),
    user: UserContext = Depends(require_supervisor),
):
    """
    Executes Innovation 5: Supervisory Decision Stability Analysis.
    Measures the sensitivity of the review sample selection to analytical configuration choices.
    """
    # 1. Resolve active version
    ver_id = req.dataset_version_id or (str(repo.active_dataset_version_id) if repo.active_dataset_version_id else None)
    if not ver_id:
        raise HTTPException(status_code=404, detail="No active dataset version.")
    
    version_uuid = UUID(ver_id)
    findings = repo.get_findings(dataset_version_id=version_uuid)
    if findings is None or len(findings) == 0:
        # We can still run stability on empty, just to return the empty schema
        findings = []

    # Resolve analysis_run
    analysis_run_id = None
    for ds_meta in repo.datasets.values():
        for v in ds_meta.get("versions", []):
            if str(v.get("version_id")) == ver_id:
                analysis_run_id = v.get("analysis_run_id")
                break

    # 2. Run Analysis
    analyzer = StabilityAnalyzer(optimizer_seed=req.optimizer_seed)
    report = analyzer.analyze(
        findings=findings,
        dataset_version_id=version_uuid,
        analysis_run_id=analysis_run_id,
        baseline_ruleset_version=DEFAULT_AUTHORITATIVE_RULESET_V1.version_id,
        budgets=req.budgets,
        magnitudes=req.magnitudes,
    )

    # 3. Audit
    repo.record_audit_event(
        user_id=user.user_id,
        username=user.username,
        action="DECISION_STABILITY_ANALYSIS",
        target_type="dataset_version",
        target_id=ver_id,
        details={
            "population_size": len(findings),
            "magnitudes_tested": req.magnitudes,
            "budgets_tested": req.budgets,
        },
    )

    return report.to_dict()


@router.get("", response_model=ValidationProtocolResponse)
def get_validation_results(
    current_user: UserContext = Depends(require_supervisor),
) -> ValidationProtocolResponse:
    return _run_current_validation_protocol()


@router.get(
    "/historical-review-efficiency",
    deprecated=True,
    summary="Historical synthetic review-efficiency diagnostic",
)
def get_review_efficiency_results(
    current_user: UserContext = Depends(require_supervisor),
):
    report = run_review_efficiency_benchmark(ruleset=DEFAULT_AUTHORITATIVE_RULESET_V1)
    return report.to_dict()

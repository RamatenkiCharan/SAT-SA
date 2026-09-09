"""
Canonical evidence model for SAT-SA.

Source of truth: SAT-SA_SRS_v2_revised.md §9 (Canonical Data Model),
§24 (Database / Persistence Design), §54/FR-020-024 (Finding Model,
Canonical Evidence Model).

Design rules enforced here (do not silently violate these):
  - Source evidence is never overwritten (see AGENTS.md §9). These models
    represent CANONICAL records derived from source data, not the source
    payload itself. Source payloads must be stored separately and referenced
    by `source_record_ref`.
  - Every record that can produce or feed a finding carries provenance
    fields (dataset_version_id) so an analysis run is reproducible
    (SRS §52 Versioning Requirements).
  - Confidence / data-quality / model-confidence are represented as DISTINCT
    fields wherever they appear (PROJECT_CONTEXT §23) - never collapsed into
    one blended number without also carrying the components.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations - explicit, not free strings (AGENTS.md §37 Type Safety)
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class AssetCriticality(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class AlertStatus(str, Enum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    ESCALATED = "ESCALATED"
    CLOSED = "CLOSED"
    REOPENED = "REOPENED"


class ReviewDecisionState(str, Enum):
    """SRS §7.9 / PROJECT_CONTEXT §79 human decision states."""
    CONFIRMED = "CONFIRMED"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    NEEDS_INVESTIGATION = "NEEDS_INVESTIGATION"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class FindingType(str, Enum):
    """SRS §7.4.1 / §7.5.1 pinned P0 and P1 detector families."""
    FAST_CLOSURE = "FAST_CLOSURE"                                # FR-030
    INVESTIGATION_INSUFFICIENCY = "INVESTIGATION_INSUFFICIENCY"  # FR-031
    ESCALATION_GAP = "ESCALATION_GAP"                            # FR-032
    REPEATED_UNRESOLVED_ALERTS = "REPEATED_UNRESOLVED_ALERTS"    # FR-033
    WORKFLOW_SHORTCUT = "WORKFLOW_SHORTCUT"                      # FR-034
    COVERAGE_GAP = "COVERAGE_GAP"                                # FR-041


class ExpectationBasis(str, Enum):
    """PROJECT_CONTEXT §18 - never collapse these into one 'expected' concept."""
    HARD_REQUIREMENT = "HARD_REQUIREMENT"
    CONFIGURED_EXPECTATION = "CONFIGURED_EXPECTATION"
    STATISTICAL_BASELINE = "STATISTICAL_BASELINE"
    INFERRED_PATTERN = "INFERRED_PATTERN"


# ---------------------------------------------------------------------------
# Provenance mixin - every canonical/derived record needs this (SRS §24)
# ---------------------------------------------------------------------------

class ProvenanceMixin(BaseModel):
    dataset_version_id: UUID = Field(
        ..., description="Immutable dataset version this record was derived from."
    )
    source_record_ref: Optional[str] = Field(
        None, description="Pointer back to the untouched source record/file+row."
    )
    ingest_time: datetime = Field(..., description="When SAT-SA ingested this record.")


# ---------------------------------------------------------------------------
# Core entities (SRS §9 table)
# ---------------------------------------------------------------------------

class CSE(ProvenanceMixin):
    cse_id: UUID
    name: str
    sector: str
    scale: str = Field(..., description="Peer-grouping dimension, e.g. small/medium/large.")
    reporting_period_id: UUID


class ReportingPeriod(BaseModel):
    reporting_period_id: UUID
    cse_id: UUID
    period_start: datetime
    period_end: datetime


class Asset(ProvenanceMixin):
    asset_id: UUID
    cse_id: UUID
    criticality: AssetCriticality
    asset_type: str
    environment: str
    expected_monitoring_context: Optional[str] = Field(
        None, description="Free-text/coded expectation used by negative-space engine (FR-040)."
    )


class Alert(ProvenanceMixin):
    alert_id: UUID
    cse_id: UUID
    asset_id: UUID
    reporting_period_id: UUID
    event_time: datetime = Field(..., description="When the underlying activity occurred.")
    severity: Severity
    alert_category: str
    source: str
    status: AlertStatus


class Investigation(ProvenanceMixin):
    investigation_id: UUID
    alert_id: UUID
    started_at: datetime
    ended_at: Optional[datetime] = None
    analyst_id: Optional[str] = None
    evidence_count: int = Field(0, ge=0)
    disposition: Optional[str] = None


class Case(ProvenanceMixin):
    case_id: UUID
    alert_id: UUID
    opened_at: datetime
    closed_at: Optional[datetime] = None
    severity: Severity
    outcome: Optional[str] = None


class Escalation(ProvenanceMixin):
    escalation_id: UUID
    case_id: UUID
    escalated_at: datetime
    level: str
    target: str


class Action(ProvenanceMixin):
    action_id: UUID
    case_id: UUID
    action_type: str
    performed_at: datetime
    outcome: Optional[str] = None


class Closure(ProvenanceMixin):
    closure_id: UUID
    case_id: UUID
    closed_at: datetime
    reason: str
    reviewer: Optional[str] = None

    @property
    def closure_duration_seconds(self) -> Optional[float]:
        # Filled in by the workflow-reconstruction service once the linked
        # Case.opened_at is resolved; kept as a computed hook, never stored
        # redundantly on the source record (avoids silent divergence).
        return None


class CoverageObservation(ProvenanceMixin):
    """Feeds FR-012 coverage analysis and FR-041 negative-space coverage gap."""
    observation_id: UUID
    cse_id: UUID
    asset_id: Optional[UUID] = None
    alert_category: Optional[str] = None
    period_id: UUID
    expected_count: float = Field(..., ge=0)
    observed_count: float = Field(..., ge=0)


class PeerGroup(BaseModel):
    peer_group_id: UUID
    definition: str = Field(..., description="Human-readable peer-grouping criteria, FR-060.")
    member_cse_ids: list[UUID] = Field(default_factory=list)

    @property
    def size(self) -> int:
        return len(self.member_cse_ids)

    @property
    def below_minimum_size(self) -> bool:
        # SRS §7.7 FR-062: minimum peer-group size of 5.
        return self.size < 5


# ---------------------------------------------------------------------------
# Data quality (SRS §7.2.1) - components ALWAYS carried alongside the score
# ---------------------------------------------------------------------------

class DataQualityComponents(BaseModel):
    completeness_ratio: float = Field(..., ge=0, le=1)
    consistency_ratio: float = Field(..., ge=0, le=1)
    coverage_ratio: float = Field(..., ge=0, le=1)
    sample_sufficiency_ratio: float = Field(..., ge=0, le=1)


class DataQualityScore(BaseModel):
    dataset_version_id: UUID
    score: float = Field(..., ge=0, le=1)
    components: DataQualityComponents
    ruleset_version: str = Field(..., description="Version of the weights used (§24 rulesets table).")
    computed_at: datetime


# ---------------------------------------------------------------------------
# Finding model (SRS §54 / AGENTS.md §24 finding contract)
# ---------------------------------------------------------------------------

class EvidenceRef(BaseModel):
    entity_type: str = Field(..., description="e.g. 'alert', 'investigation', 'case'.")
    entity_id: UUID


class Finding(BaseModel):
    finding_id: UUID
    cse_id: UUID
    reporting_period_id: UUID
    finding_type: FindingType

    priority_score: float = Field(..., ge=0, le=1)
    priority_components: dict[str, float] = Field(
        ..., description="§10.5 five components (SignalStrength, PeerDeviation, "
                          "Persistence, AssetCriticality, DataUncertainty) - "
                          "must always accompany priority_score, never shown alone."
    )

    evidentiary_confidence: float = Field(..., ge=0, le=1)
    data_quality_status: DataQualityScore

    expectation_basis: ExpectationBasis
    expected_behavior: str
    observed_behavior: str

    supporting_signals: list[str] = Field(default_factory=list)
    contradicting_signals: list[str] = Field(default_factory=list)

    peer_context: Optional[str] = None
    temporal_context: Optional[str] = None

    evidence_refs: list[EvidenceRef] = Field(default_factory=list)

    analytical_method: str
    ruleset_version: str
    model_version: Optional[str] = None
    dataset_version_id: UUID
    analysis_run_id: UUID

    review_status: Optional[ReviewDecisionState] = None
    review_notes: Optional[str] = None

    created_at: datetime

    def validate_finding_generation_contract(self) -> list[str]:
        """
        PROJECT_CONTEXT §78 finding generation contract, enforced as data,
        not just documentation. Returns a list of violations (empty = OK).
        Call this before persisting a HIGH-priority finding.
        """
        violations: list[str] = []
        if len(self.evidence_refs) == 0:
            violations.append("No evidence_refs: a finding may not exist without linked records.")
        if self.data_quality_status.score <= 0.6:
            violations.append(
                "DataQualityScore <= 0.6: FR-073 forbids surfacing as high priority."
            )
        independent_signals = len(self.supporting_signals)
        if independent_signals < 2:
            violations.append(
                "Fewer than 2 independent supporting signals: FR-073 threshold not met."
            )
        return violations

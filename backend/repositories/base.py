"""
Base SAT-SA Repository Interface and Domain Metadata Definitions.
Defines the contract implemented by both InMemoryRepository and PostgresRepository.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from analytics.canonicalization.canonicalization import CanonicalDataset
from analytics.data_quality.quality_score import DataQualityResult
from analytics.peer_benchmark.benchmarks import PeerBenchmarkEngine
from analytics.workflow.workflow_reconstruction import ReconstructedDataset
from backend.models.canonical import (
    Finding,
    ReviewDecisionState,
)
from backend.models.provenance import AnalysisRun, FindingProvenanceTrace
from backend.models.ruleset import AnalyticalRuleset



@dataclass
class DatasetMetadata:
    dataset_id: UUID
    name: str
    description: str
    created_at: datetime
    versions: list[DatasetVersionMetadata] = field(default_factory=list)


@dataclass
class DatasetVersionMetadata:
    dataset_version_id: UUID
    dataset_id: UUID
    version_number: int
    source_file_ref: str
    import_time: datetime
    transformation_version: str
    schema_version: str
    row_count: int
    data_quality_score: Optional[float] = None
    data_quality_components: Optional[dict[str, float]] = None
    data_quality_warnings: list[str] = field(default_factory=list)
    file_format: Optional[str] = None
    sha256_hash: Optional[str] = None
    accepted_rows: int = 0
    rejected_rows: int = 0
    rejection_reasons: list[str] = field(default_factory=list)


@dataclass
class AuditEvent:
    audit_event_id: UUID
    user_id: str
    username: str
    action: str
    target_type: str
    target_id: Optional[str]
    occurred_at: datetime
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReviewDecisionRecord:
    review_decision_id: UUID
    finding_id: UUID
    decision: ReviewDecisionState
    reviewer_id: str
    reviewer_name: str
    decided_at: datetime
    notes: Optional[str] = None


@dataclass
class EvidenceMessageRecord:
    message_id: UUID
    finding_id: UUID
    evidence_id: Optional[str]
    sender_id: str
    sender_name: str
    sender_role: str
    recipient: str
    message: str
    sent_at: datetime


class BaseSATRepository(ABC):
    """Abstract Base Class for all SAT-SA repository implementations."""

    @abstractmethod
    def record_audit_event(
        self,
        user_id: str,
        username: str,
        action: str,
        target_type: str,
        target_id: Optional[str] = None,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Records an immutable security/operational audit log entry."""
        ...

    @abstractmethod
    def get_audit_events(self, limit: int = 100) -> list[AuditEvent]:
        """Retrieves recent audit events in reverse chronological order."""
        ...

    def get_user_by_username(self, username: str) -> Any | None:
        """Returns an active user record, or None when it does not exist."""
        raise NotImplementedError

    def get_user_by_id(self, user_id: str) -> Any | None:
        """Returns an active user record, or None when it does not exist."""
        raise NotImplementedError

    def list_users(self) -> list[Any]:
        """Returns active user records."""
        raise NotImplementedError

    @abstractmethod
    def set_active_dataset_version(
        self, dataset_version_id: UUID, user_id: str, username: str
    ) -> DatasetVersionMetadata:
        """Changes the active evidence version and records the accountable action."""
        ...

    @abstractmethod
    def register_dataset_version(
        self,
        dataset_id: UUID,
        dataset_name: str,
        source_file_ref: str,
        canonical_dataset: CanonicalDataset,
        reconstructed_dataset: ReconstructedDataset,
        benchmark_engine: PeerBenchmarkEngine,
        findings: list[Finding],
        dq_score: Optional[float] = None,
        dq_result: Optional[DataQualityResult] = None,
        description: str = "",
        file_format: Optional[str] = None,
        sha256_hash: Optional[str] = None,
        accepted_rows: Optional[int] = None,
        rejected_rows: int = 0,
        rejection_reasons: Optional[list[str]] = None,
        analysis_run: Optional[AnalysisRun] = None,
    ) -> DatasetVersionMetadata:
        """Persists a new immutable dataset version with full canonical models, findings, and metrics."""
        ...

    @abstractmethod
    def record_analysis_run(self, run: AnalysisRun) -> AnalysisRun:
        """Records an analytical execution run."""
        ...

    @abstractmethod
    def get_analysis_run(self, analysis_run_id: UUID) -> Optional[AnalysisRun]:
        """Retrieves an analysis run by ID."""
        ...

    @abstractmethod
    def get_finding_provenance(self, finding_id: UUID) -> Optional[FindingProvenanceTrace]:
        """Retrieves complete 6-tier provenance lineage trace for a finding."""
        ...

    @abstractmethod
    def list_datasets(self) -> list[dict[str, Any]]:
        """Returns all datasets and their versions with provenance and DQ summaries."""
        ...

    @abstractmethod
    def get_findings(
        self,
        dataset_version_id: Optional[UUID] = None,
        sector: Optional[str] = None,
        finding_type: Optional[str] = None,
        cse_id: Optional[UUID] = None,
        min_priority: Optional[float] = None,
    ) -> list[Finding]:
        """Filters and returns prioritized findings."""
        ...

    @abstractmethod
    def get_finding_by_id(self, finding_id: UUID) -> Optional[Finding]:
        """Retrieves a single finding by ID."""
        ...

    @abstractmethod
    def get_finding_evidence_records(self, finding_id: UUID) -> dict[str, Any]:
        """Fetches decomposed evidence records (alerts, cases, investigations, escalations, actions, closures, assets) for a finding."""
        ...

    @abstractmethod
    def record_review_decision(
        self,
        finding_id: UUID,
        decision: ReviewDecisionState,
        reviewer_id: str,
        reviewer_name: str,
        notes: Optional[str] = None,
    ) -> ReviewDecisionRecord:
        """Records a human examiner review decision and updates finding review state."""
        ...

    @abstractmethod
    def get_active_ruleset(self) -> AnalyticalRuleset:
        """Retrieves the currently active analytical ruleset."""
        ...

    @abstractmethod
    def get_ruleset_by_version(self, version: str) -> Optional[AnalyticalRuleset]:
        """Retrieves an analytical ruleset by version string."""
        ...

    @abstractmethod
    def list_rulesets(self) -> list[AnalyticalRuleset]:
        """Lists all registered versioned rulesets."""
        ...

    @abstractmethod
    def register_ruleset(
        self,
        ruleset: AnalyticalRuleset,
        set_active: bool = False,
    ) -> AnalyticalRuleset:
        """Registers a new versioned ruleset."""
        ...

    @abstractmethod
    def set_active_ruleset(self, version: str) -> AnalyticalRuleset:
        """Activates a specific versioned ruleset."""
        ...

    def get_peer_groups(self, version_id: UUID) -> list[PeerGroup]:
        """Retrieves persisted versioned peer groups for a dataset version."""
        return []

    def persist_peer_groups(self, version_id: UUID, groups: list[PeerGroup]) -> None:
        """Persists versioned peer groups for a dataset version."""
        pass

    @abstractmethod
    def save_evidence_message(
        self,
        finding_id: UUID,
        message: str,
        sender_id: str,
        sender_name: str,
        sender_role: str,
        evidence_id: Optional[str] = None,
        recipient: Optional[str] = None,
    ) -> EvidenceMessageRecord:
        """Records an evidence inquiry / supervisory directive message and logs audit event."""
        ...

    @abstractmethod
    def get_evidence_messages(self, finding_id: Optional[UUID] = None) -> list[EvidenceMessageRecord]:
        """Retrieves stored evidence messages."""
        ...




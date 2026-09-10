"""
Domain Models for Analysis-Run Provenance and End-to-End Traceability (SRS §24, §52, §54).
Enforces reproducible analytical execution and verifiable lineage from upload to evidence.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AnalysisRun(BaseModel):
    """
    Immutable record of an analytical execution run against a specific dataset version.
    Records the exact ruleset, detector configuration, code version, and execution metrics.
    """
    analysis_run_id: UUID = Field(default_factory=uuid4)
    dataset_id: UUID
    dataset_version_id: UUID
    schema_version: str = Field("2.0.0", description="Canonical schema specification version.")
    ruleset_version: str = Field("V1", description="Analytical ruleset version used for weights & thresholds.")
    ruleset_id: Optional[UUID] = None
    detector_config: dict[str, Any] = Field(default_factory=dict, description="Snapshot of detector parameters.")
    app_version: str = Field("1.0.0", description="Application release version.")
    git_commit: Optional[str] = Field("git-rev-satsa-v2", description="Source code commit SHA/tag where available.")
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: Optional[datetime] = None
    status: str = Field("COMPLETED", description="Execution status: RUNNING | COMPLETED | FAILED")
    error_message: Optional[str] = None
    findings_count: int = Field(0, ge=0)


class EvidenceProvenanceRef(BaseModel):
    """Reference linking an evidence record to its source canonical record."""
    entity_type: str
    entity_id: UUID
    source_record_ref: Optional[str] = None


class FindingProvenanceTrace(BaseModel):
    """
    Complete 6-tier lineage trace for a finding:
    Upload -> Dataset -> Dataset Version -> Analysis Run -> Finding -> Evidence References.
    """
    # 1. Upload Source File Provenance
    source_file_ref: str
    sha256_hash: Optional[str] = None
    file_format: Optional[str] = None
    import_time: datetime

    # 2. Dataset Entity
    dataset_id: UUID
    dataset_name: str

    # 3. Immutable Dataset Version
    dataset_version_id: UUID
    version_number: int
    row_count: int
    data_quality_score: float

    # 4. Analysis Run Metadata
    analysis_run_id: UUID
    schema_version: str
    ruleset_version: str
    detector_config: dict[str, Any]
    app_version: str
    git_commit: Optional[str]
    started_at: datetime
    finished_at: Optional[datetime]
    status: str
    error_message: Optional[str] = None

    # 5. Finding Details & Traceability Contract
    finding_id: UUID
    finding_type: str
    detector: str = ""
    detector_version: str = "1.0.0"
    reason: str = ""
    source_entity: dict[str, Any] = Field(default_factory=dict)
    source_record_ids: list[str] = Field(default_factory=list)
    priority_score: float
    priority_label: str
    evidentiary_confidence: float
    calculation_inputs: dict[str, Any] = Field(default_factory=dict)
    calculation_result: dict[str, Any] = Field(default_factory=dict)

    # 6. Linked Canonical Evidence
    evidence_records_count: int
    evidence_refs: list[EvidenceProvenanceRef] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_file_ref": self.source_file_ref,
            "sha256_hash": self.sha256_hash,
            "file_format": self.file_format,
            "import_time": self.import_time.isoformat(),
            "dataset_id": str(self.dataset_id),
            "dataset_name": self.dataset_name,
            "dataset_version_id": str(self.dataset_version_id),
            "dataset_version": {
                "dataset_version_id": str(self.dataset_version_id),
                "version_number": self.version_number,
                "dataset_id": str(self.dataset_id),
                "dataset_name": self.dataset_name,
            },
            "version_number": self.version_number,
            "row_count": self.row_count,
            "data_quality_score": round(self.data_quality_score, 4),
            "analysis_run_id": str(self.analysis_run_id),
            "analysis_run": {
                "analysis_run_id": str(self.analysis_run_id),
                "ruleset_version": self.ruleset_version,
                "schema_version": self.schema_version,
                "started_at": self.started_at.isoformat(),
                "finished_at": self.finished_at.isoformat() if self.finished_at else None,
                "status": self.status,
            },
            "schema_version": self.schema_version,
            "ruleset_version": self.ruleset_version,
            "detector_config": self.detector_config,
            "app_version": self.app_version,
            "git_commit": self.git_commit,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "status": self.status,
            "error_message": self.error_message,
            "finding_id": str(self.finding_id),
            "finding_type": self.finding_type,
            "detector": self.detector or self.finding_type,
            "detector_version": self.detector_version,
            "reason": self.reason,
            "source_entity": self.source_entity,
            "source_record_ids": self.source_record_ids,
            "priority_score": round(self.priority_score, 4),
            "priority_label": self.priority_label,
            "evidentiary_confidence": round(self.evidentiary_confidence, 4),
            "calculation_inputs": self.calculation_inputs,
            "calculation_result": self.calculation_result,
            "evidence_records_count": self.evidence_records_count,
            "evidence_references": [
                {
                    "entity_type": ref.entity_type,
                    "entity_id": str(ref.entity_id),
                    "source_record_ref": ref.source_record_ref,
                }
                for ref in self.evidence_refs
            ],
            "evidence_refs": [
                {
                    "entity_type": ref.entity_type,
                    "entity_id": str(ref.entity_id),
                    "source_record_ref": ref.source_record_ref,
                }
                for ref in self.evidence_refs
            ],
        }

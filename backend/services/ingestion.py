"""
Unified Ingestion Service for SAT-SA (SRS §7.1).
Handles:
  File Upload -> Format Detector -> CSV/JSON Parser -> Schema Mapper ->
  Validator (rejection tracking) -> Canonicalizer -> Provenance ->
  Data Trust -> Analysis -> Persistence.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from uuid import UUID, uuid4

from analytics.canonicalization.canonicalization import (
    CanonicalDataset,
    _parse_dt,
    _parse_uuid,
)
from analytics.data_quality.quality_processor import evaluate_dataset_quality
from analytics.data_quality.quality_score import DataQualityResult
from analytics.execution_gap.escalation_gap import EscalationGapDetector
from analytics.execution_gap.fast_closure import FastClosureDetector
from analytics.execution_gap.repeated_unresolved import RepeatedUnresolvedDetector
from analytics.fusion.evidence_fusion import EvidenceFusionEngine
from analytics.negative_space.coverage_gap import CoverageGapDetector
from analytics.peer_benchmark.benchmarks import PeerBenchmarkEngine
from analytics.workflow.workflow_reconstruction import ReconstructedDataset
from backend.models.canonical import (
    Action,
    Alert,
    AlertStatus,
    Asset,
    AssetCriticality,
    Case,
    Closure,
    CoverageObservation,
    CSE,
    Escalation,
    Finding,
    Investigation,
    ReportingPeriod,
    Severity,
)
from backend.models.provenance import AnalysisRun
from backend.models.ruleset import AnalyticalRuleset
from backend.repositories.in_memory_repo import SATRepository
from backend.services.ruleset_service import RulesetService



_ALLOWED_EXTENSIONS = {".csv", ".json"}
_MAX_FILE_SIZE_BYTES = 200 * 1024 * 1024  # 200MB ceiling


class IngestionValidationError(ValueError):
    """Raised on malformed or unparseable uploads."""


class FileFormat(str, Enum):
    CSV = "csv"
    JSON = "json"


# Canonical Schema Field Aliases
_ALERT_FIELD_ALIASES = {
    "alert_id": ["alert_id", "id", "alertid", "alert_identifier", "incident_id", "ticket_id", "event_id", "alert_key"],
    "cse_id": ["cse_id", "cse", "cseid", "entity_id", "entityid", "organization_id", "org_id", "tenant_id", "company_id"],
    "asset_id": ["asset_id", "assetid", "host_id", "target_asset", "target_id", "hostname", "device_id", "ip_address", "ip", "asset", "host"],
    "reporting_period_id": ["reporting_period_id", "reportingperiodid", "period_id", "periodid", "quarter", "period"],
    "event_time": ["event_time", "eventtime", "timestamp", "event_timestamp", "time", "created_at", "occurred_at", "date", "datetime", "start_time", "log_time", "alert_time", "created_time"],
    "severity": ["severity", "sev", "priority", "criticality", "urgency", "impact", "level", "alert_severity", "severity_level"],
    "alert_category": ["alert_category", "alertcategory", "category", "type", "alert_type", "attack_type", "rule_name", "signature", "threat_type", "description", "title", "name", "event_type", "alert_name", "threat_name"],
    "source": ["source", "src", "log_source", "sensor", "tool", "product", "detector", "vendor", "origin", "datasource", "data_source", "source_type"],
    "status": ["status", "state", "alert_status", "alert_state", "disposition", "resolution", "ticket_status", "incident_status", "stage", "lifecycle_status", "closure_status", "outcome", "action_status", "current_status", "alertstatus", "alertstate"],
}

_CSE_FIELD_ALIASES = {
    "cse_id": ["cse_id", "id", "cseid"],
    "name": ["name", "cse_name", "entity_name"],
    "sector": ["sector", "industry"],
    "scale": ["scale", "size"],
    "reporting_period_id": ["reporting_period_id", "period_id"],
}

_ASSET_FIELD_ALIASES = {
    "asset_id": ["asset_id", "id", "assetid"],
    "cse_id": ["cse_id", "cseid"],
    "criticality": ["criticality", "crit", "asset_criticality"],
    "asset_type": ["asset_type", "type", "assettype"],
    "environment": ["environment", "env"],
    "expected_monitoring_context": ["expected_monitoring_context", "context"],
}


@dataclass(frozen=True)
class IngestionProvenance:
    filename: str
    file_format: str
    sha256_hash: str
    file_size_bytes: int
    upload_time: datetime
    transformation_version: str = "T1.0"
    schema_version: str = "S1.0"


@dataclass
class RejectedRecord:
    row_index: int
    entity_type: str
    reasons: list[str]
    raw_record: dict[str, Any]


@dataclass
class ValidationSummary:
    total_input_rows: int
    accepted_rows: int
    rejected_rows: int
    rejection_reasons: list[str] = field(default_factory=list)
    rejected_details: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class IngestionResult:
    dataset_id: UUID
    dataset_version_id: UUID
    provenance: IngestionProvenance
    validation_summary: ValidationSummary
    canonical_dataset: CanonicalDataset
    reconstructed_dataset: ReconstructedDataset
    benchmark_engine: PeerBenchmarkEngine
    findings: list[Finding]
    data_quality_result: DataQualityResult
    analysis_run: Optional[AnalysisRun] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "success",
            "dataset_id": str(self.dataset_id),
            "dataset_version_id": str(self.dataset_version_id),
            "analysis_run_id": str(self.analysis_run.analysis_run_id) if self.analysis_run else None,
            "provenance": {
                "filename": self.provenance.filename,
                "file_format": self.provenance.file_format,
                "sha256_hash": self.provenance.sha256_hash,
                "file_size_bytes": self.provenance.file_size_bytes,
                "upload_time": self.provenance.upload_time.isoformat(),
                "transformation_version": self.provenance.transformation_version,
                "schema_version": self.provenance.schema_version,
                "analysis_run_id": str(self.analysis_run.analysis_run_id) if self.analysis_run else None,
            },
            "validation_summary": {
                "total_input_rows": self.validation_summary.total_input_rows,
                "accepted_rows": self.validation_summary.accepted_rows,
                "rejected_rows": self.validation_summary.rejected_rows,
                "rejection_reasons": self.validation_summary.rejection_reasons,
                "warnings": self.validation_summary.warnings,
            },
            "row_count": len(self.canonical_dataset.alerts),
            "findings_generated": len(self.findings),
            "data_quality_score": round(self.data_quality_result.score, 4),
            "data_quality_breakdown": {
                "overall_score": round(self.data_quality_result.score * 100, 1),
                "completeness": round(self.data_quality_result.components.completeness_ratio * 100, 1),
                "consistency": round(self.data_quality_result.components.consistency_ratio * 100, 1),
                "coverage": round(self.data_quality_result.components.coverage_ratio * 100, 1),
                "sample_sufficiency": round(self.data_quality_result.components.sample_sufficiency_ratio * 100, 1),
                "warnings": self.data_quality_result.warnings,
            },
        }



def detect_format(filename: str, contents: bytes) -> FileFormat:
    """Detects and verifies file format against supported types."""
    if len(contents) > _MAX_FILE_SIZE_BYTES:
        raise IngestionValidationError(
            f"File size exceeds maximum allowed limit ({len(contents)} > {_MAX_FILE_SIZE_BYTES} bytes)."
        )

    fn_lower = filename.lower()
    if fn_lower.endswith(".csv"):
        return FileFormat.CSV
    if fn_lower.endswith(".json"):
        return FileFormat.JSON

    # Fallback content sniffing
    snippet = contents[:1024].decode("utf-8", errors="ignore").strip()
    if snippet.startswith("{") or snippet.startswith("["):
        return FileFormat.JSON
    if "," in snippet or "\t" in snippet:
        return FileFormat.CSV

    raise IngestionValidationError(
        f"Unsupported file format for '{filename}'. SAT-SA accepts .csv and .json files only."
    )


def parse_raw_payload(contents: bytes, file_format: FileFormat) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    """Parses raw binary contents into structured raw entity dictionaries."""
    parse_warnings: list[str] = []

    if file_format == FileFormat.JSON:
        try:
            text = contents.decode("utf-8")
            data = json.loads(text)
        except UnicodeDecodeError as exc:
            raise IngestionValidationError(f"Invalid UTF-8 encoding in JSON: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise IngestionValidationError(f"Malformed JSON: {exc}") from exc

        if isinstance(data, list):
            # Array of objects
            for idx, item in enumerate(data):
                if not isinstance(item, dict):
                    raise IngestionValidationError(f"Item {idx} in JSON array is not an object.")
            return {"alerts": data}, parse_warnings

        elif isinstance(data, dict):
            known_entity_keys = {
                "cse",
                "reporting_periods",
                "assets",
                "alerts",
                "investigations",
                "cases",
                "escalations",
                "actions",
                "closures",
                "coverage_observations",
            }
            if any(k in data for k in known_entity_keys):
                bundle: dict[str, list[dict[str, Any]]] = {}
                for k, v in data.items():
                    if isinstance(v, list):
                        bundle[k] = [item for item in v if isinstance(item, dict)]
                    else:
                        parse_warnings.append(f"Entity key '{k}' expected list of objects, got {type(v).__name__}.")
                return bundle, parse_warnings
            else:
                # Single record dictionary
                return {"alerts": [data]}, parse_warnings
        else:
            raise IngestionValidationError("Top-level JSON must be an object or array of objects.")

    elif file_format == FileFormat.CSV:
        try:
            text = contents.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise IngestionValidationError(f"Invalid UTF-8 encoding in CSV: {exc}") from exc

        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None:
            raise IngestionValidationError("CSV has no header row.")

        rows: list[dict[str, Any]] = []
        for idx, row in enumerate(reader):
            if None in row:
                parse_warnings.append(f"CSV Row {idx + 1}: contains extra columns beyond header definition.")
            # Remove DictReader None key if present
            clean_row = {k: v for k, v in row.items() if k is not None}
            rows.append(clean_row)

        return {"alerts": rows}, parse_warnings

    raise IngestionValidationError(f"Unhandled file format: {file_format}")


def _map_fields(row: dict[str, Any], alias_map: dict[str, list[str]]) -> tuple[dict[str, Any], list[str]]:
    """Normalizes row fields using canonical aliases and detects unknown columns."""
    normalized: dict[str, Any] = {}
    row_keys_lower = {str(k).strip().lower(): k for k in row.keys()}
    mapped_source_keys = set()

    for canonical_field, aliases in alias_map.items():
        for alias in aliases:
            alias_clean = alias.lower().replace("-", "_").replace(" ", "_")
            for rk_clean, original_key in row_keys_lower.items():
                if rk_clean.replace("-", "_").replace(" ", "_") == alias_clean:
                    val = row[original_key]
                    if val is not None and str(val).strip() != "":
                        normalized[canonical_field] = str(val).strip() if isinstance(val, str) else val
                    mapped_source_keys.add(original_key)
                    break
            if canonical_field in normalized:
                break

    unknown_columns = [k for k in row.keys() if k not in mapped_source_keys]
    return normalized, unknown_columns


def _validate_datetime(val: Any) -> tuple[Optional[datetime], Optional[str]]:
    """Validates datetime strings without silent coercion."""
    if val is None or (isinstance(val, str) and not val.strip()):
        return None, "Missing timestamp value"
    if isinstance(val, datetime):
        return val, None
    if isinstance(val, str):
        val_str = val.strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(val_str), None
        except ValueError:
            for fmt in (
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M:%S%z",
                "%Y-%m-%d",
                "%Y/%m/%d %H:%M:%S",
                "%Y/%m/%d",
            ):
                try:
                    return datetime.strptime(val.strip(), fmt).replace(tzinfo=timezone.utc), None
                except ValueError:
                    pass
            return None, f"Invalid date/time format: '{val}'"
    return None, f"Invalid date type: {type(val).__name__}"


def validate_and_canonicalize_bundle(
    raw_bundle: dict[str, list[dict[str, Any]]],
    dataset_version_id: UUID,
    now: datetime,
) -> tuple[CanonicalDataset, ValidationSummary]:
    """
    Validates all entity records, rejects invalid rows with reasons, and constructs CanonicalDataset.
    """
    accepted_alerts: list[Alert] = []
    accepted_cse: list[CSE] = []
    accepted_assets: list[Asset] = []
    accepted_investigations: list[Investigation] = []
    accepted_cases: list[Case] = []
    accepted_escalations: list[Escalation] = []
    accepted_actions: list[Action] = []
    accepted_closures: list[Closure] = []
    accepted_coverage_observations: list[CoverageObservation] = []

    rejection_reasons: list[str] = []
    rejected_details: list[dict[str, Any]] = []
    warnings: list[str] = []

    seen_alert_ids: set[UUID] = set()
    seen_cse_ids: set[UUID] = set()
    seen_asset_ids: set[UUID] = set()

    total_input_rows = 0

    # 1. Validate & Canonicalize CSEs
    cse_rows = raw_bundle.get("cse", [])
    total_input_rows += len(cse_rows)
    for idx, raw_row in enumerate(cse_rows):
        mapped, unknown = _map_fields(raw_row, _CSE_FIELD_ALIASES)
        row_reasons = []
        if unknown:
            warnings.append(f"CSE Row {idx + 1}: unmapped columns {unknown}")

        if "name" not in mapped:
            row_reasons.append("Missing required field 'name'")
        if "sector" not in mapped:
            row_reasons.append("Missing required field 'sector'")

        cse_id = _parse_uuid(mapped.get("cse_id")) if "cse_id" in mapped else uuid4()
        if cse_id in seen_cse_ids:
            row_reasons.append(f"Duplicate CSE identifier: '{cse_id}'")
        seen_cse_ids.add(cse_id)

        rep_id = _parse_uuid(mapped.get("reporting_period_id")) if "reporting_period_id" in mapped else uuid4()

        if row_reasons:
            rejection_reasons.append(f"CSE Row {idx + 1}: {'; '.join(row_reasons)}")
            rejected_details.append({"row_index": idx, "entity_type": "cse", "reasons": row_reasons, "raw_record": raw_row})
        else:
            accepted_cse.append(
                CSE(
                    cse_id=cse_id,
                    name=str(mapped["name"]),
                    sector=str(mapped["sector"]),
                    scale=str(mapped.get("scale", "medium")),
                    reporting_period_id=rep_id,
                    dataset_version_id=dataset_version_id,
                    source_record_ref=str(mapped.get("source_record_ref", f"cse_{cse_id}")),
                    ingest_time=now,
                )
            )

    # 2. Validate & Canonicalize Assets
    asset_rows = raw_bundle.get("assets", [])
    total_input_rows += len(asset_rows)
    for idx, raw_row in enumerate(asset_rows):
        mapped, unknown = _map_fields(raw_row, _ASSET_FIELD_ALIASES)
        row_reasons = []
        if unknown:
            warnings.append(f"Asset Row {idx + 1}: unmapped columns {unknown}")

        if "asset_type" not in mapped:
            row_reasons.append("Missing required field 'asset_type'")

        crit_raw = str(mapped.get("criticality", "MEDIUM")).upper()
        if crit_raw not in AssetCriticality.__members__:
            row_reasons.append(f"Invalid criticality '{crit_raw}'. Expected {list(AssetCriticality.__members__.keys())}")

        asset_id = _parse_uuid(mapped.get("asset_id")) if "asset_id" in mapped else uuid4()
        if asset_id in seen_asset_ids:
            row_reasons.append(f"Duplicate Asset identifier: '{asset_id}'")
        seen_asset_ids.add(asset_id)

        cse_id = _parse_uuid(mapped.get("cse_id")) if "cse_id" in mapped else (accepted_cse[0].cse_id if accepted_cse else uuid4())

        if row_reasons:
            rejection_reasons.append(f"Asset Row {idx + 1}: {'; '.join(row_reasons)}")
            rejected_details.append({"row_index": idx, "entity_type": "asset", "reasons": row_reasons, "raw_record": raw_row})
        else:
            accepted_assets.append(
                Asset(
                    asset_id=asset_id,
                    cse_id=cse_id,
                    criticality=AssetCriticality[crit_raw],
                    asset_type=str(mapped["asset_type"]),
                    environment=str(mapped.get("environment", "Production")),
                    expected_monitoring_context=mapped.get("expected_monitoring_context"),
                    dataset_version_id=dataset_version_id,
                    source_record_ref=str(mapped.get("source_record_ref", f"asset_{asset_id}")),
                    ingest_time=now,
                )
            )

    # 3. Validate & Canonicalize Alerts
    alert_rows = raw_bundle.get("alerts", [])
    total_input_rows += len(alert_rows)
    for idx, raw_row in enumerate(alert_rows):
        mapped, unknown = _map_fields(raw_row, _ALERT_FIELD_ALIASES)
        row_reasons = []
        if unknown:
            warnings.append(f"Alert Row {idx + 1}: unmapped columns {unknown}")

        # 1. Severity Validation & Normalization
        sev_raw: Optional[str] = None
        sev_val = str(mapped.get("severity", "")).strip() if "severity" in mapped and mapped["severity"] is not None else ""
        if sev_val:
            sev_clean = sev_val.upper().replace("-", "_").replace(" ", "_")
            if sev_clean in Severity.__members__:
                sev_raw = sev_clean
            elif sev_clean in {"1", "CRIT", "CRITICAL", "FATAL", "EMERGENCY"}:
                sev_raw = "CRITICAL"
            elif sev_clean in {"2", "HIGH", "MAJOR", "SEVERE"}:
                sev_raw = "HIGH"
            elif sev_clean in {"3", "MED", "MEDIUM", "MODERATE", "WARN", "WARNING"}:
                sev_raw = "MEDIUM"
            elif sev_clean in {"4", "LOW", "MINOR"}:
                sev_raw = "LOW"
            elif sev_clean in {"5", "INFO", "INFORMATIONAL", "DEBUG"}:
                sev_raw = "INFO"
            else:
                row_reasons.append(f"Invalid severity '{sev_val}'. Expected {list(Severity.__members__.keys())}")
        else:
            sev_raw = "MEDIUM"
            warnings.append(f"Alert Row {idx + 1}: field 'severity' not provided; defaulted to 'MEDIUM'.")

        # 2. Status Validation & Normalization
        stat_raw: Optional[str] = None
        stat_val = str(mapped.get("status", "")).strip() if "status" in mapped and mapped["status"] is not None else ""
        if stat_val:
            stat_clean = stat_val.upper().replace("-", "_").replace(" ", "_")
            if stat_clean in AlertStatus.__members__:
                stat_raw = stat_clean
            elif stat_clean in {"CLOSED", "RESOLVED", "DISMISSED", "AUTO_CLOSED", "DONE", "COMPLETED", "TRUE_POSITIVE", "FALSE_POSITIVE"}:
                stat_raw = "CLOSED"
            elif stat_clean in {"INVESTIGATING", "IN_PROGRESS", "TRIAGED", "ANALYZING", "UNDER_REVIEW", "ASSIGNED"}:
                stat_raw = "INVESTIGATING"
            elif stat_clean in {"ESCALATED", "ESCALATE", "TIER2", "L2", "TIER3", "L3"}:
                stat_raw = "ESCALATED"
            elif stat_clean in {"OPEN", "NEW", "ACTIVE", "PENDING", "UNASSIGNED", "TRIGGERED"}:
                stat_raw = "OPEN"
            elif stat_clean in {"REOPENED", "RE_OPENED"}:
                stat_raw = "REOPENED"
            else:
                row_reasons.append(f"Invalid status '{stat_val}'. Expected {list(AlertStatus.__members__.keys())}")
        else:
            # Missing status column: infer CLOSED if closure indicators exist, otherwise OPEN
            if any(k in raw_row for k in ("closed_at", "closure_time", "ended_at", "resolution", "disposition")):
                stat_raw = "CLOSED"
            else:
                stat_raw = "OPEN"
            warnings.append(f"Alert Row {idx + 1}: field 'status' not provided; defaulted to '{stat_raw}'.")

        # 3. Alert Category & Source Fallbacks
        cat_val = str(mapped.get("alert_category", "")).strip() if "alert_category" in mapped and mapped["alert_category"] is not None else ""
        if not cat_val:
            cat_val = "SECURITY_EVENT"
            warnings.append(f"Alert Row {idx + 1}: field 'alert_category' not provided; defaulted to 'SECURITY_EVENT'.")

        src_val = str(mapped.get("source", "")).strip() if "source" in mapped and mapped["source"] is not None else ""
        if not src_val:
            src_val = "SIEM_INGEST"
            warnings.append(f"Alert Row {idx + 1}: field 'source' not provided; defaulted to 'SIEM_INGEST'.")

        # 4. Event Time & Date validation
        parsed_dt: Optional[datetime] = None
        if "event_time" in mapped and mapped["event_time"]:
            parsed_dt, dt_err = _validate_datetime(mapped.get("event_time"))
            if dt_err:
                row_reasons.append(dt_err)
        else:
            parsed_dt = now
            warnings.append(f"Alert Row {idx + 1}: field 'event_time' not provided; defaulted to ingestion timestamp.")

        # Duplicate identifier check
        alert_id = _parse_uuid(mapped.get("alert_id")) if "alert_id" in mapped and mapped["alert_id"] else uuid4()
        if "alert_id" in mapped and alert_id in seen_alert_ids:
            row_reasons.append(f"Duplicate alert identifier: '{alert_id}'")
        seen_alert_ids.add(alert_id)

        if row_reasons or not sev_raw or not stat_raw:
            rejection_reasons.append(f"Alert Row {idx + 1}: {'; '.join(row_reasons)}")
            rejected_details.append({"row_index": idx, "entity_type": "alert", "reasons": row_reasons, "raw_record": raw_row})
        else:
            cse_id = _parse_uuid(mapped.get("cse_id")) if "cse_id" in mapped and mapped["cse_id"] else (accepted_cse[0].cse_id if accepted_cse else uuid4())
            asset_id = _parse_uuid(mapped.get("asset_id")) if "asset_id" in mapped and mapped["asset_id"] else uuid4()
            rep_id = _parse_uuid(mapped.get("reporting_period_id")) if "reporting_period_id" in mapped and mapped["reporting_period_id"] else uuid4()

            accepted_alerts.append(
                Alert(
                    alert_id=alert_id,
                    cse_id=cse_id,
                    asset_id=asset_id,
                    reporting_period_id=rep_id,
                    event_time=parsed_dt or now,
                    severity=Severity[sev_raw],
                    alert_category=cat_val,
                    source=src_val,
                    status=AlertStatus[stat_raw],
                    dataset_version_id=dataset_version_id,
                    source_record_ref=str(mapped.get("source_record_ref", f"alert_{alert_id}")),
                    ingest_time=now,
                )
            )

    # 4. Other Entities (Investigations, Cases, Escalations, Actions, Closures, Coverage Observations)
    for inv in raw_bundle.get("investigations", []):
        inv_id = _parse_uuid(inv.get("investigation_id"))
        alt_id = _parse_uuid(inv.get("alert_id"))
        dt_start, _ = _validate_datetime(inv.get("started_at"))
        dt_end, _ = _validate_datetime(inv.get("ended_at")) if inv.get("ended_at") else (None, None)
        accepted_investigations.append(
            Investigation(
                investigation_id=inv_id,
                alert_id=alt_id,
                started_at=dt_start or now,
                ended_at=dt_end,
                analyst_id=str(inv.get("analyst_id")) if inv.get("analyst_id") else None,
                evidence_count=int(inv.get("evidence_count", 0)),
                disposition=str(inv.get("disposition")) if inv.get("disposition") else None,
                dataset_version_id=dataset_version_id,
                source_record_ref=str(inv.get("source_record_ref", f"inv_{inv_id}")),
                ingest_time=now,
            )
        )

    for case in raw_bundle.get("cases", []):
        c_id = _parse_uuid(case.get("case_id"))
        alt_id = _parse_uuid(case.get("alert_id"))
        dt_open, _ = _validate_datetime(case.get("opened_at"))
        dt_close, _ = _validate_datetime(case.get("closed_at")) if case.get("closed_at") else (None, None)
        sev_raw = str(case.get("severity", "MEDIUM")).upper()
        sev = Severity[sev_raw] if sev_raw in Severity.__members__ else Severity.MEDIUM
        accepted_cases.append(
            Case(
                case_id=c_id,
                alert_id=alt_id,
                opened_at=dt_open or now,
                closed_at=dt_close,
                severity=sev,
                outcome=str(case.get("outcome")) if case.get("outcome") else None,
                dataset_version_id=dataset_version_id,
                source_record_ref=str(case.get("source_record_ref", f"case_{c_id}")),
                ingest_time=now,
            )
        )

    for esc in raw_bundle.get("escalations", []):
        esc_id = _parse_uuid(esc.get("escalation_id"))
        c_id = _parse_uuid(esc.get("case_id"))
        dt_esc, _ = _validate_datetime(esc.get("escalated_at"))
        accepted_escalations.append(
            Escalation(
                escalation_id=esc_id,
                case_id=c_id,
                escalated_at=dt_esc or now,
                level=str(esc.get("level", "Tier-2")),
                target=str(esc.get("target", "Senior Responder")),
                dataset_version_id=dataset_version_id,
                source_record_ref=str(esc.get("source_record_ref", f"esc_{esc_id}")),
                ingest_time=now,
            )
        )

    for act in raw_bundle.get("actions", []):
        act_id = _parse_uuid(act.get("action_id"))
        c_id = _parse_uuid(act.get("case_id"))
        dt_act, _ = _validate_datetime(act.get("performed_at"))
        accepted_actions.append(
            Action(
                action_id=act_id,
                case_id=c_id,
                action_type=str(act.get("action_type", "Remediate")),
                performed_at=dt_act or now,
                outcome=str(act.get("outcome")) if act.get("outcome") else None,
                dataset_version_id=dataset_version_id,
                source_record_ref=str(act.get("source_record_ref", f"act_{act_id}")),
                ingest_time=now,
            )
        )

    for clo in raw_bundle.get("closures", []):
        clo_id = _parse_uuid(clo.get("closure_id"))
        c_id = _parse_uuid(clo.get("case_id"))
        dt_clo, _ = _validate_datetime(clo.get("closed_at"))
        accepted_closures.append(
            Closure(
                closure_id=clo_id,
                case_id=c_id,
                closed_at=dt_clo or now,
                reason=str(clo.get("reason", "Resolved")),
                reviewer=str(clo.get("reviewer")) if clo.get("reviewer") else None,
                dataset_version_id=dataset_version_id,
                source_record_ref=str(clo.get("source_record_ref", f"clo_{clo_id}")),
                ingest_time=now,
            )
        )

    for obs in raw_bundle.get("coverage_observations", []):
        obs_id = _parse_uuid(obs.get("observation_id"))
        cse_id = _parse_uuid(obs.get("cse_id"))
        asset_id = _parse_uuid(obs.get("asset_id")) if obs.get("asset_id") else None
        p_id = _parse_uuid(obs.get("period_id"))
        accepted_coverage_observations.append(
            CoverageObservation(
                observation_id=obs_id,
                cse_id=cse_id,
                asset_id=asset_id,
                alert_category=str(obs.get("alert_category")) if obs.get("alert_category") else None,
                period_id=p_id,
                expected_count=float(obs.get("expected_count", 10.0)),
                observed_count=float(obs.get("observed_count", 0.0)),
                dataset_version_id=dataset_version_id,
                source_record_ref=str(obs.get("source_record_ref", f"obs_{obs_id}")),
                ingest_time=now,
            )
        )

    # Standalone alert synthesis for baseline CSE & Assets if missing
    if accepted_alerts and not accepted_cse:
        default_cse_id = accepted_alerts[0].cse_id
        default_rep_id = accepted_alerts[0].reporting_period_id
        accepted_cse.append(
            CSE(
                cse_id=default_cse_id,
                name="Primary Monitored Entity",
                sector="Critical Infrastructure",
                scale="medium",
                reporting_period_id=default_rep_id,
                dataset_version_id=dataset_version_id,
                source_record_ref="auto_generated_cse",
                ingest_time=now,
            )
        )

    if accepted_alerts and not accepted_assets:
        known_asset_ids = {a.asset_id for a in accepted_alerts}
        default_cse_id = accepted_cse[0].cse_id if accepted_cse else uuid4()
        for a_id in known_asset_ids:
            accepted_assets.append(
                Asset(
                    asset_id=a_id,
                    cse_id=default_cse_id,
                    criticality=AssetCriticality.HIGH,
                    asset_type="Monitored Server",
                    environment="Production",
                    expected_monitoring_context="Active monitoring",
                    dataset_version_id=dataset_version_id,
                    source_record_ref="auto_generated_asset",
                    ingest_time=now,
                )
            )

    accepted_reporting_periods: list[ReportingPeriod] = []
    for rp in raw_bundle.get("reporting_periods", []):
        r_id = _parse_uuid(rp.get("reporting_period_id"))
        c_id = _parse_uuid(rp.get("cse_id")) if rp.get("cse_id") else (accepted_cse[0].cse_id if accepted_cse else uuid4())
        p_start, _ = _validate_datetime(rp.get("period_start"))
        p_end, _ = _validate_datetime(rp.get("period_end"))
        accepted_reporting_periods.append(
            ReportingPeriod(
                reporting_period_id=r_id,
                cse_id=c_id,
                period_start=p_start or now,
                period_end=p_end or now,
            )
        )

    if not accepted_reporting_periods and accepted_cse:
        for c in accepted_cse:
            accepted_reporting_periods.append(
                ReportingPeriod(
                    reporting_period_id=c.reporting_period_id,
                    cse_id=c.cse_id,
                    period_start=now,
                    period_end=now,
                )
            )

    canonical_ds = CanonicalDataset(
        dataset_version_id=dataset_version_id,
        cse_list=accepted_cse,
        reporting_periods=accepted_reporting_periods,
        assets=accepted_assets,
        alerts=accepted_alerts,
        investigations=accepted_investigations,
        cases=accepted_cases,
        escalations=accepted_escalations,
        actions=accepted_actions,
        closures=accepted_closures,
        coverage_observations=accepted_coverage_observations,
    )

    accepted_count = len(accepted_alerts) + len(accepted_cse) + len(accepted_assets)
    rejected_count = len(rejected_details)

    summary = ValidationSummary(
        total_input_rows=total_input_rows,
        accepted_rows=len(accepted_alerts),
        rejected_rows=rejected_count,
        rejection_reasons=rejection_reasons,
        rejected_details=rejected_details,
        warnings=warnings,
    )

    return canonical_ds, summary


def ingest_file_stream(
    contents: bytes,
    filename: str,
    dataset_id: Optional[UUID] = None,
    dataset_version_id: Optional[UUID] = None,
    repo: Optional[SATRepository] = None,
    dataset_name: Optional[str] = None,
    description: Optional[str] = None,
    ruleset: Optional[AnalyticalRuleset] = None,
) -> IngestionResult:
    """
    Unified Ingestion Entrypoint for CSV and JSON.
    Executes:
      Detection -> Parsing -> Schema Mapping -> Validation ->
      Canonicalization -> Provenance -> Data Trust -> Analysis -> Persistence.
    All weights and detector thresholds are governed by versioned ruleset.
    """
    now = datetime.now(timezone.utc)
    ds_id = dataset_id or uuid4()
    ver_id = dataset_version_id or uuid4()
    ds_name = dataset_name or f"Upload: {filename}"
    desc = description or f"Operational evidence package ({filename})"
    active_ruleset = ruleset or RulesetService.get_active_ruleset(repo)

    # 1. Format Detection
    file_format = detect_format(filename, contents)

    # 2. SHA-256 Provenance
    sha256_hash = hashlib.sha256(contents).hexdigest()
    provenance = IngestionProvenance(
        filename=filename,
        file_format=file_format.value,
        sha256_hash=sha256_hash,
        file_size_bytes=len(contents),
        upload_time=now,
    )

    # 3. Parsing
    raw_bundle, parse_warnings = parse_raw_payload(contents, file_format)

    # 4. Schema Mapping, Validation & Canonicalization
    canonical_ds, val_summary = validate_and_canonicalize_bundle(raw_bundle, ver_id, now)
    val_summary.warnings.extend(parse_warnings)

    if len(canonical_ds.alerts) == 0 and val_summary.rejected_rows > 0:
        raise IngestionValidationError(
            f"All {val_summary.rejected_rows} rows were rejected due to schema validation failures:\n"
            + "\n".join(val_summary.rejection_reasons[:10])
        )

    # 5. Data Trust Engine (Genuine DQ Calculation via versioned ruleset)
    dq_result = evaluate_dataset_quality(canonical_ds, ver_id, ruleset=active_ruleset)

    # 6. Workflow Reconstruction & Benchmarking Engine
    reconstructed_ds = ReconstructedDataset(canonical_ds)
    benchmark_engine = PeerBenchmarkEngine(reconstructed_ds)

    # 7. Execution Gap & Negative-Space Detectors (Configured via versioned ruleset)
    fast_closure_detector = FastClosureDetector(config=active_ruleset.detector_config.fast_closure)
    escalation_gap_detector = EscalationGapDetector(config=active_ruleset.detector_config.escalation_gap)
    repeated_unresolved_detector = RepeatedUnresolvedDetector(config=active_ruleset.detector_config.repeated_unresolved)
    coverage_gap_detector = CoverageGapDetector(config=active_ruleset.detector_config.coverage_gap)

    fast_closures = fast_closure_detector.detect(reconstructed_ds, benchmark_engine)
    escalation_gaps = escalation_gap_detector.detect(reconstructed_ds)
    repeated_unresolved = repeated_unresolved_detector.detect(reconstructed_ds)
    coverage_gaps = coverage_gap_detector.detect(canonical_ds, dq_result.score)

    # 8. Evidence Fusion (Configured via versioned ruleset)
    fusion_engine = EvidenceFusionEngine(ruleset=active_ruleset)
    analysis_run_id = uuid4()
    findings: list[Finding] = []

    for cse in canonical_ds.cse_list:
        cse_findings = fusion_engine.fuse_signals(
            cse_id=cse.cse_id,
            reporting_period_id=cse.reporting_period_id,
            dataset_version_id=ver_id,
            analysis_run_id=analysis_run_id,
            data_quality_result=dq_result,
            fast_closures=fast_closures,
            escalation_gaps=escalation_gaps,
            repeated_unresolved=repeated_unresolved,
            coverage_gaps=coverage_gaps,
        )
        findings.extend(cse_findings)

    # 8. Attach source record refs to evidence references

    source_ref_map: dict[UUID, str] = {}
    for c in canonical_ds.cse_list:
        if c.source_record_ref:
            source_ref_map[c.cse_id] = c.source_record_ref
    for a in canonical_ds.assets:
        if a.source_record_ref:
            source_ref_map[a.asset_id] = a.source_record_ref
    for alt in canonical_ds.alerts:
        if alt.source_record_ref:
            source_ref_map[alt.alert_id] = alt.source_record_ref
    for inv in canonical_ds.investigations:
        if inv.source_record_ref:
            source_ref_map[inv.investigation_id] = inv.source_record_ref
    for cs in canonical_ds.cases:
        if cs.source_record_ref:
            source_ref_map[cs.case_id] = cs.source_record_ref
    for esc in canonical_ds.escalations:
        if esc.source_record_ref:
            source_ref_map[esc.escalation_id] = esc.source_record_ref
    for act in canonical_ds.actions:
        if act.source_record_ref:
            source_ref_map[act.action_id] = act.source_record_ref
    for clo in canonical_ds.closures:
        if clo.source_record_ref:
            source_ref_map[clo.closure_id] = clo.source_record_ref
    for cov in canonical_ds.coverage_observations:
        if cov.source_record_ref:
            source_ref_map[cov.observation_id] = cov.source_record_ref

    for f in findings:
        for ref in f.evidence_refs:
            if not ref.source_record_ref:
                if ref.entity_id in source_ref_map:
                    ref.source_record_ref = source_ref_map[ref.entity_id]
                else:
                    ref.source_record_ref = f"canonical:{ref.entity_type}:{ref.entity_id}"

    finished_at = datetime.now(timezone.utc)

    # 9. Record Analysis Run Provenance
    det_cfg = active_ruleset.detector_config.to_dict() if hasattr(active_ruleset.detector_config, "to_dict") else (active_ruleset.detector_config.model_dump() if hasattr(active_ruleset.detector_config, "model_dump") else dict(active_ruleset.detector_config))
    analysis_run = AnalysisRun(
        analysis_run_id=analysis_run_id,
        dataset_id=ds_id,
        dataset_version_id=ver_id,
        schema_version="2.0.0",
        ruleset_version=active_ruleset.version,
        ruleset_id=active_ruleset.ruleset_id,
        detector_config=det_cfg,
        app_version="1.0.0",
        git_commit="git-rev-satsa-v2",
        started_at=now,
        finished_at=finished_at,
        status="COMPLETED",
        findings_count=len(findings),
    )

    # 10. Persistence
    if repo is not None:
        repo.register_dataset_version(
            dataset_id=ds_id,
            dataset_name=ds_name,
            source_file_ref=filename,
            canonical_dataset=canonical_ds,
            reconstructed_dataset=reconstructed_ds,
            benchmark_engine=benchmark_engine,
            findings=findings,
            dq_result=dq_result,
            description=desc,
            file_format=file_format.value,
            sha256_hash=sha256_hash,
            accepted_rows=val_summary.accepted_rows,
            rejected_rows=val_summary.rejected_rows,
            rejection_reasons=val_summary.rejection_reasons,
            analysis_run=analysis_run,
        )

    return IngestionResult(
        dataset_id=ds_id,
        dataset_version_id=ver_id,
        provenance=provenance,
        validation_summary=val_summary,
        canonical_dataset=canonical_ds,
        reconstructed_dataset=reconstructed_ds,
        benchmark_engine=benchmark_engine,
        findings=findings,
        data_quality_result=dq_result,
        analysis_run=analysis_run,
    )



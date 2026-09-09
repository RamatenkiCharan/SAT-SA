"""
Canonicalization Service.
Maps parsed raw CSV / JSON dictionaries to typed Canonical Pydantic Models.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from backend.models.canonical import (
    Alert,
    AlertStatus,
    Asset,
    AssetCriticality,
    Action,
    Case,
    Closure,
    CoverageObservation,
    CSE,
    Escalation,
    Investigation,
    ReportingPeriod,
    Severity,
)


def _parse_dt(val: Any) -> datetime:
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        # Handle ISO and common formats
        val = val.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(val)
        except ValueError:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d"):
                try:
                    return datetime.strptime(val, fmt)
                except ValueError:
                    pass
    return datetime.now(timezone.utc)


def _parse_uuid(val: Any) -> UUID:
    if isinstance(val, UUID):
        return val
    if isinstance(val, str):
        try:
            return UUID(val)
        except ValueError:
            pass
    return uuid4()


class CanonicalDataset:
    def __init__(
        self,
        dataset_version_id: UUID,
        cse_list: Optional[list[CSE]] = None,
        reporting_periods: Optional[list[ReportingPeriod]] = None,
        assets: Optional[list[Asset]] = None,
        alerts: Optional[list[Alert]] = None,
        investigations: Optional[list[Investigation]] = None,
        cases: Optional[list[Case]] = None,
        escalations: Optional[list[Escalation]] = None,
        actions: Optional[list[Action]] = None,
        closures: Optional[list[Closure]] = None,
        coverage_observations: Optional[list[CoverageObservation]] = None,
    ):
        self.dataset_version_id = dataset_version_id
        self.cse_list: list[CSE] = cse_list or []
        self.reporting_periods: list[ReportingPeriod] = reporting_periods or []
        self.assets: list[Asset] = assets or []
        self.alerts: list[Alert] = alerts or []
        self.investigations: list[Investigation] = investigations or []
        self.cases: list[Case] = cases or []
        self.escalations: list[Escalation] = escalations or []
        self.actions: list[Action] = actions or []
        self.closures: list[Closure] = closures or []
        self.coverage_observations: list[CoverageObservation] = coverage_observations or []


def canonicalize_records(
    raw_bundle: dict[str, list[dict[str, Any]]],
    dataset_version_id: UUID,
) -> CanonicalDataset:
    """
    Canonicalizes bundles of raw dictionary records (e.g. from JSON or multi-file CSV imports)
    into a structured CanonicalDataset.
    """
    now = datetime.now(timezone.utc)
    dataset = CanonicalDataset(dataset_version_id=dataset_version_id)

    # 1. CSE
    for row in raw_bundle.get("cse", []):
        cse_id = _parse_uuid(row.get("cse_id"))
        rep_id = _parse_uuid(row.get("reporting_period_id"))
        dataset.cse_list.append(
            CSE(
                cse_id=cse_id,
                name=str(row.get("name", "Unknown CSE")),
                sector=str(row.get("sector", "Critical Infrastructure")),
                scale=str(row.get("scale", "medium")),
                reporting_period_id=rep_id,
                dataset_version_id=dataset_version_id,
                source_record_ref=row.get("source_record_ref", f"cse_{cse_id}"),
                ingest_time=now,
            )
        )

    # 2. Reporting Periods
    for row in raw_bundle.get("reporting_periods", []):
        rep_id = _parse_uuid(row.get("reporting_period_id"))
        cse_id = _parse_uuid(row.get("cse_id"))
        dataset.reporting_periods.append(
            ReportingPeriod(
                reporting_period_id=rep_id,
                cse_id=cse_id,
                period_start=_parse_dt(row.get("period_start")),
                period_end=_parse_dt(row.get("period_end")),
            )
        )

    # 3. Assets
    for row in raw_bundle.get("assets", []):
        asset_id = _parse_uuid(row.get("asset_id"))
        cse_id = _parse_uuid(row.get("cse_id"))
        crit_raw = str(row.get("criticality", "MEDIUM")).upper()
        crit = AssetCriticality[crit_raw] if crit_raw in AssetCriticality.__members__ else AssetCriticality.MEDIUM
        dataset.assets.append(
            Asset(
                asset_id=asset_id,
                cse_id=cse_id,
                criticality=crit,
                asset_type=str(row.get("asset_type", "Server")),
                environment=str(row.get("environment", "Production")),
                expected_monitoring_context=row.get("expected_monitoring_context"),
                dataset_version_id=dataset_version_id,
                source_record_ref=row.get("source_record_ref", f"asset_{asset_id}"),
                ingest_time=now,
            )
        )

    # 4. Alerts
    for row in raw_bundle.get("alerts", []):
        alert_id = _parse_uuid(row.get("alert_id"))
        cse_id = _parse_uuid(row.get("cse_id"))
        asset_id = _parse_uuid(row.get("asset_id"))
        rep_id = _parse_uuid(row.get("reporting_period_id"))
        sev_raw = str(row.get("severity", "MEDIUM")).upper()
        sev = Severity[sev_raw] if sev_raw in Severity.__members__ else Severity.MEDIUM
        status_raw = str(row.get("status", "OPEN")).upper()
        status = AlertStatus[status_raw] if status_raw in AlertStatus.__members__ else AlertStatus.OPEN

        dataset.alerts.append(
            Alert(
                alert_id=alert_id,
                cse_id=cse_id,
                asset_id=asset_id,
                reporting_period_id=rep_id,
                event_time=_parse_dt(row.get("event_time")),
                severity=sev,
                alert_category=str(row.get("alert_category", "Authentication")),
                source=str(row.get("source", "SIEM")),
                status=status,
                dataset_version_id=dataset_version_id,
                source_record_ref=row.get("source_record_ref", f"alert_{alert_id}"),
                ingest_time=now,
            )
        )

    # 5. Investigations
    for row in raw_bundle.get("investigations", []):
        inv_id = _parse_uuid(row.get("investigation_id"))
        alert_id = _parse_uuid(row.get("alert_id"))
        dataset.investigations.append(
            Investigation(
                investigation_id=inv_id,
                alert_id=alert_id,
                started_at=_parse_dt(row.get("started_at")),
                ended_at=_parse_dt(row.get("ended_at")) if row.get("ended_at") else None,
                analyst_id=str(row.get("analyst_id")) if row.get("analyst_id") else None,
                evidence_count=int(row.get("evidence_count", 0)),
                disposition=str(row.get("disposition")) if row.get("disposition") else None,
                dataset_version_id=dataset_version_id,
                source_record_ref=row.get("source_record_ref", f"inv_{inv_id}"),
                ingest_time=now,
            )
        )

    # 6. Cases
    for row in raw_bundle.get("cases", []):
        case_id = _parse_uuid(row.get("case_id"))
        alert_id = _parse_uuid(row.get("alert_id"))
        sev_raw = str(row.get("severity", "MEDIUM")).upper()
        sev = Severity[sev_raw] if sev_raw in Severity.__members__ else Severity.MEDIUM
        dataset.cases.append(
            Case(
                case_id=case_id,
                alert_id=alert_id,
                opened_at=_parse_dt(row.get("opened_at")),
                closed_at=_parse_dt(row.get("closed_at")) if row.get("closed_at") else None,
                severity=sev,
                outcome=str(row.get("outcome")) if row.get("outcome") else None,
                dataset_version_id=dataset_version_id,
                source_record_ref=row.get("source_record_ref", f"case_{case_id}"),
                ingest_time=now,
            )
        )

    # 7. Escalations
    for row in raw_bundle.get("escalations", []):
        esc_id = _parse_uuid(row.get("escalation_id"))
        case_id = _parse_uuid(row.get("case_id"))
        dataset.escalations.append(
            Escalation(
                escalation_id=esc_id,
                case_id=case_id,
                escalated_at=_parse_dt(row.get("escalated_at")),
                level=str(row.get("level", "L2")),
                target=str(row.get("target", "SOC Lead")),
                dataset_version_id=dataset_version_id,
                source_record_ref=row.get("source_record_ref", f"esc_{esc_id}"),
                ingest_time=now,
            )
        )

    # 8. Actions
    for row in raw_bundle.get("actions", []):
        act_id = _parse_uuid(row.get("action_id"))
        case_id = _parse_uuid(row.get("case_id"))
        dataset.actions.append(
            Action(
                action_id=act_id,
                case_id=case_id,
                action_type=str(row.get("action_type", "Block IP")),
                performed_at=_parse_dt(row.get("performed_at")),
                outcome=str(row.get("outcome")) if row.get("outcome") else None,
                dataset_version_id=dataset_version_id,
                source_record_ref=row.get("source_record_ref", f"act_{act_id}"),
                ingest_time=now,
            )
        )

    # 9. Closures
    for row in raw_bundle.get("closures", []):
        clo_id = _parse_uuid(row.get("closure_id"))
        case_id = _parse_uuid(row.get("case_id"))
        dataset.closures.append(
            Closure(
                closure_id=clo_id,
                case_id=case_id,
                closed_at=_parse_dt(row.get("closed_at")),
                reason=str(row.get("reason", "Resolved")),
                reviewer=str(row.get("reviewer")) if row.get("reviewer") else None,
                dataset_version_id=dataset_version_id,
                source_record_ref=row.get("source_record_ref", f"clo_{clo_id}"),
                ingest_time=now,
            )
        )

    # 10. Coverage Observations
    for row in raw_bundle.get("coverage_observations", []):
        obs_id = _parse_uuid(row.get("observation_id"))
        cse_id = _parse_uuid(row.get("cse_id"))
        asset_id = _parse_uuid(row.get("asset_id")) if row.get("asset_id") else None
        period_id = _parse_uuid(row.get("period_id"))
        dataset.coverage_observations.append(
            CoverageObservation(
                observation_id=obs_id,
                cse_id=cse_id,
                asset_id=asset_id,
                alert_category=str(row.get("alert_category")) if row.get("alert_category") else None,
                period_id=period_id,
                expected_count=float(row.get("expected_count", 10.0)),
                observed_count=float(row.get("observed_count", 0.0)),
                dataset_version_id=dataset_version_id,
                source_record_ref=row.get("source_record_ref", f"obs_{obs_id}"),
                ingest_time=now,
            )
        )

    return dataset

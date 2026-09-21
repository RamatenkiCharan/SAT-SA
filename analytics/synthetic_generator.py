"""
Synthetic SOC Operational Evidence Dataset Generator & Validation Engine.
Adheres to the Generator/Detector Independence Protocol to construct realistic multi-sector CSE scenarios
and evaluate Precision, Recall, F1, and Supervisory Review Yield without circular validation.
Provides parameterized scenario generation across:
  - Timing (closure duration distributions, investigation duration, rolling windows, jitter)
  - Severity (severity mixes, critical/high defect severities)
  - Asset Class & Criticality (multi-sector asset archetypes)
  - Peer Composition (cohort sizes, multi-sector scales)
  - Missingness (telemetry outage rates, missing audit fields, silent coverage assets)
  - Noise (spurious alerts, scheduled maintenance bursts, non-target anomalies)
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, NamedTuple, Optional
from uuid import UUID, uuid4

from analytics.canonicalization.canonicalization import CanonicalDataset, canonicalize_records
from analytics.data_quality.quality_processor import evaluate_dataset_quality
from analytics.data_quality.quality_score import DataQualityResult
from analytics.execution_gap.escalation_gap import EscalationGapDetector
from analytics.execution_gap.fast_closure import FastClosureDetector
from analytics.execution_gap.repeated_unresolved import RepeatedUnresolvedDetector
from analytics.fusion.evidence_fusion import EvidenceFusionEngine
from analytics.negative_space.coverage_gap import CoverageGapDetector
from analytics.peer_benchmark.benchmarks import PeerBenchmarkEngine
from analytics.workflow.workflow_reconstruction import ReconstructedDataset
from backend.models.canonical import Finding
from backend.models.provenance import AnalysisRun
from backend.models.ruleset import (
    DEFAULT_AUTHORITATIVE_RULESET_V1,
    AnalyticalRuleset,
)


class PipelineResult(NamedTuple):
    canonical_dataset: CanonicalDataset
    reconstructed_dataset: ReconstructedDataset
    benchmark_engine: PeerBenchmarkEngine
    findings: list[Finding]
    data_quality_result: DataQualityResult
    analysis_run: Optional[AnalysisRun] = None


@dataclass
class TimingParameters:
    """Parametric configuration for workflow timing and durations."""
    fast_closure_range: tuple[float, float] = (180.0, 360.0)  # seconds
    normal_closure_range: tuple[float, float] = (2100.0, 4200.0)  # seconds
    maintenance_closure_range: tuple[float, float] = (1800.0, 3600.0)
    investigation_evidence_range_defect: tuple[int, int] = (0, 1)
    investigation_evidence_range_normal: tuple[int, int] = (3, 8)
    repetition_window_days: int = 30
    timestamp_jitter_seconds: tuple[float, float] = (0.0, 300.0)


@dataclass
class SeverityParameters:
    """Parametric configuration for alert severity distributions."""
    severity_weights: dict[str, float] = field(
        default_factory=lambda: {
            "CRITICAL": 0.25,
            "HIGH": 0.25,
            "MEDIUM": 0.25,
            "LOW": 0.15,
            "INFO": 0.10,
        }
    )
    defect_severities: list[str] = field(default_factory=lambda: ["CRITICAL", "HIGH"])
    high_impact_categories: list[str] = field(
        default_factory=lambda: [
            "SCADA Intrusion",
            "Ransomware",
            "Privilege Escalation",
            "Unauthorized Access",
            "Brute Force",
            "Malware Execution",
            "Data Exfiltration",
        ]
    )


@dataclass
class AssetArchetype:
    """Parametric specification of an operational asset archetype."""
    name: str
    asset_type: str
    criticality: str
    environment: str
    monitoring_context: str = ""


@dataclass
class PeerCompositionParameters:
    """Parametric configuration for cohort and peer group composition."""
    cohort_size: int = 5
    scale: str = "large"  # small, medium, large
    sector: str = "Power & Energy"


@dataclass
class MissingnessParameters:
    """Parametric configuration for data missingness and telemetry loss."""
    is_data_outage: bool = False
    data_outage_alert_count: int = 5
    omit_optional_fields: bool = False
    silent_coverage_asset: bool = False
    expected_coverage_count: float = 40.0
    observed_coverage_count_normal_range: tuple[float, float] = (32.0, 48.0)


@dataclass
class NoiseParameters:
    """Parametric configuration for operational noise and non-target spikes."""
    is_noisy: bool = False
    noisy_alert_count_range: tuple[int, int] = (55, 75)
    is_maintenance_anomaly: bool = False
    maintenance_alert_count_range: tuple[int, int] = (40, 55)
    maintenance_category: str = "Scheduled Maintenance / Firmware Patching"


@dataclass
class ScenarioParameters:
    """Complete multi-dimensional parameterized scenario specification."""
    name: str
    sector: str
    scale: str
    primary_category: str
    categories: list[str] = field(default_factory=list)
    has_fast_closure: bool = False
    has_escalation_gap: bool = False
    has_repeated_unresolved: bool = False
    has_coverage_gap: bool = False
    self_reported_sla: float = 0.95
    description: str = ""
    timing: TimingParameters = field(default_factory=TimingParameters)
    severity: SeverityParameters = field(default_factory=SeverityParameters)
    assets: list[AssetArchetype] = field(default_factory=list)
    missingness: MissingnessParameters = field(default_factory=MissingnessParameters)
    noise: NoiseParameters = field(default_factory=NoiseParameters)


@dataclass
class GroundTruthScenario:
    cse_id: UUID
    cse_name: str
    sector: str
    scale: str
    primary_category: str
    categories: list[str]
    has_fast_closure: bool
    has_escalation_gap: bool
    has_repeated_unresolved: bool
    has_coverage_gap: bool
    is_data_outage: bool
    is_noisy_data: bool
    is_non_target_anomaly: bool
    self_reported_sla: float
    description: str
    parameters: Optional[ScenarioParameters] = None


# 8 Mandatory Scenario Categories (SRS §19.4)
SCENARIO_CATEGORIES = [
    "normal behavior",
    "fast closure defect",
    "escalation gap",
    "repeated unresolved behavior",
    "coverage gap",
    "noisy data",
    "missing data",
    "non-target anomalies",
]


def build_default_assets(sector: str, scale: str) -> list[AssetArchetype]:
    """Generates standard realistic assets for a given sector and scale."""
    if "Power" in sector or "Energy" in sector:
        return [
            AssetArchetype("SCADA Substation Master Node", "SCADA Controller", "CRITICAL", "High Voltage Grid", "Active 24/7 SIEM & EDR telemetry for Substation Node"),
            AssetArchetype("Primary Domain Controller", "Identity Server", "CRITICAL", "Internal Corp", "Active 24/7 AD Audit Logs"),
            AssetArchetype("Database Cluster Alpha", "SQL Cluster", "HIGH", "Data Center", "Database Query & Ingestion Logs"),
            AssetArchetype("Edge Log Forwarder", "Telemetry Node", "MEDIUM", "DMZ", "Syslog Forwarding"),
        ]
    elif "Financial" in sector or "Banking" in sector:
        return [
            AssetArchetype("Core Banking Ledger Node", "Transaction Engine", "CRITICAL", "Core Network", "Core Ledger Transaction Auditing"),
            AssetArchetype("SWIFT Wire Terminal Gateway", "Financial Gateway", "CRITICAL", "DMZ Secure", "SWIFT ISO20022 Messaging Auditing"),
            AssetArchetype("Customer Account Database", "SQL Cluster", "HIGH", "Data Center", "Customer Transaction Logging"),
            AssetArchetype("Branch API Gateway", "API Gateway", "MEDIUM", "Edge", "API Ingress Audit"),
        ]
    elif "Transport" in sector:
        return [
            AssetArchetype("Signalling Control Master Node", "Train Control", "CRITICAL", "Rail Network", "Signalling Telemetry Stream"),
            AssetArchetype("Automated Train Operation Server", "ATO Controller", "CRITICAL", "Rail Ops Center", "ATO Dispatch Stream"),
            AssetArchetype("Passenger Routing Server", "Transit Core", "HIGH", "Data Center", "Routing Logs"),
            AssetArchetype("Station Access Gate Hub", "IoT Gateway", "MEDIUM", "Station LAN", "Gate Access Logs"),
        ]
    elif "Telecom" in sector:
        return [
            AssetArchetype("Core BGP Backbone Router Alpha", "Core Router", "CRITICAL", "WAN Backbone", "BGP NetFlow Telemetry"),
            AssetArchetype("Subscriber AAA Authentication Node", "Identity Core", "CRITICAL", "Core DC", "RADIUS/TACACS Audit"),
            AssetArchetype("Cellular Tower Telemetry Aggregator", "Telemetry Hub", "HIGH", "Field Node", "Base Station NetFlow"),
            AssetArchetype("Billing Mediation Engine", "SQL Cluster", "MEDIUM", "Corp Network", "Mediation Data Stream"),
        ]
    else:  # Healthcare / Defense
        return [
            AssetArchetype("EHR Primary Database Cluster", "Database Cluster", "CRITICAL", "Core DC", "EHR Clinical Access Logs"),
            AssetArchetype("PACS Medical Imaging Core", "DICOM Server", "CRITICAL", "Hospital Core", "DICOM Image Flow Logs"),
            AssetArchetype("Secure Authentication Gateway", "Identity Proxy", "CRITICAL", "DMZ", "Auth Gateway Stream"),
            AssetArchetype("Clinical Workstation Forwarder", "Endpoint Hub", "MEDIUM", "Hospital LAN", "Endpoint EDR Stream"),
        ]


# ---------------------------------------------------------------------------
# 10 TUNING SCENARIOS (66.7% of catalog)
# ---------------------------------------------------------------------------
TUNING_SCENARIO_CONFIGS: list[dict[str, Any]] = [
    {
        "name": "Northern Power Grid Co.",
        "sector": "Power & Energy",
        "scale": "large",
        "primary_category": "normal behavior",
        "categories": ["normal behavior"],
        "fast_closure": False,
        "escalation_gap": False,
        "repeated_unresolved": False,
        "coverage_gap": False,
        "data_outage": False,
        "noisy_data": False,
        "non_target_anomaly": False,
        "self_reported_sla": 0.965,
        "desc": "Baseline healthy critical infrastructure entity with standard investigation depth.",
        "timing": TimingParameters(normal_closure_range=(2100.0, 4200.0), investigation_evidence_range_normal=(3, 8)),
    },
    {
        "name": "National Power Dispatch Center (NPDC)",
        "sector": "Power & Energy",
        "scale": "large",
        "primary_category": "fast closure defect",
        "categories": ["fast closure defect", "escalation gap", "repeated unresolved behavior"],
        "fast_closure": True,
        "escalation_gap": True,
        "repeated_unresolved": True,
        "coverage_gap": False,
        "data_outage": False,
        "noisy_data": False,
        "non_target_anomaly": False,
        "self_reported_sla": 0.992,
        "desc": "THE WOW MOMENT: 99.2% self-reported SLA compliance, but operational evidence shows rapid closures (avg 4m), 0 escalations on SCADA alerts, and repeated ransomware triggers.",
        "timing": TimingParameters(fast_closure_range=(180.0, 360.0), investigation_evidence_range_defect=(0, 1)),
    },
    {
        "name": "Federal Reserve Core Banking",
        "sector": "Financial Services",
        "scale": "large",
        "primary_category": "normal behavior",
        "categories": ["normal behavior"],
        "fast_closure": False,
        "escalation_gap": False,
        "repeated_unresolved": False,
        "coverage_gap": False,
        "data_outage": False,
        "noisy_data": False,
        "non_target_anomaly": False,
        "self_reported_sla": 0.978,
        "desc": "High compliance financial sector entity with robust multi-tiered escalation.",
        "timing": TimingParameters(normal_closure_range=(2400.0, 4500.0)),
    },
    {
        "name": "Metro Rail Transit Command",
        "sector": "Transportation",
        "scale": "medium",
        "primary_category": "fast closure defect",
        "categories": ["fast closure defect"],
        "fast_closure": True,
        "escalation_gap": False,
        "repeated_unresolved": False,
        "coverage_gap": False,
        "data_outage": False,
        "noisy_data": False,
        "non_target_anomaly": False,
        "self_reported_sla": 0.985,
        "desc": "Overworked L1 analysts closing signalling alerts below peer duration.",
        "timing": TimingParameters(fast_closure_range=(150.0, 320.0), investigation_evidence_range_defect=(0, 1)),
    },
    {
        "name": "National Telecom Core Backbone",
        "sector": "Telecommunications",
        "scale": "large",
        "primary_category": "escalation gap",
        "categories": ["escalation gap"],
        "fast_closure": False,
        "escalation_gap": True,
        "repeated_unresolved": False,
        "coverage_gap": False,
        "data_outage": False,
        "noisy_data": False,
        "non_target_anomaly": False,
        "self_reported_sla": 0.940,
        "desc": "Core router alerts resolving without Tier-2 escalation records.",
    },
    {
        "name": "State Healthcare Exchange",
        "sector": "Healthcare & Defense",
        "scale": "medium",
        "primary_category": "coverage gap",
        "categories": ["coverage gap"],
        "fast_closure": False,
        "escalation_gap": False,
        "repeated_unresolved": False,
        "coverage_gap": True,
        "data_outage": False,
        "noisy_data": False,
        "non_target_anomaly": False,
        "self_reported_sla": 0.950,
        "desc": "Negative space: EHR Database is completely silent (0 observed vs 50 expected) despite healthy pipeline.",
    },
    {
        "name": "Coastal Water Authority",
        "sector": "Power & Energy",
        "scale": "large",
        "primary_category": "missing data",
        "categories": ["missing data"],
        "fast_closure": False,
        "escalation_gap": False,
        "repeated_unresolved": False,
        "coverage_gap": False,
        "data_outage": True,
        "noisy_data": False,
        "non_target_anomaly": False,
        "self_reported_sla": 0.820,
        "desc": "Known data ingestion disruption: low activity correctly classified as data uncertainty, NOT an operational breach.",
        "missingness": MissingnessParameters(is_data_outage=True, data_outage_alert_count=5),
    },
    {
        "name": "Interstate Oil Pipeline Corp.",
        "sector": "Power & Energy",
        "scale": "large",
        "primary_category": "repeated unresolved behavior",
        "categories": ["repeated unresolved behavior"],
        "fast_closure": False,
        "escalation_gap": False,
        "repeated_unresolved": True,
        "coverage_gap": False,
        "data_outage": False,
        "noisy_data": False,
        "non_target_anomaly": False,
        "self_reported_sla": 0.935,
        "desc": "Recurrent SCADA intrusion alerts on pumping station with zero remediation actions recorded.",
        "timing": TimingParameters(repetition_window_days=30),
    },
    {
        "name": "Global Maritime Logistics",
        "sector": "Transportation",
        "scale": "large",
        "primary_category": "noisy data",
        "categories": ["noisy data"],
        "fast_closure": False,
        "escalation_gap": False,
        "repeated_unresolved": False,
        "coverage_gap": False,
        "data_outage": False,
        "noisy_data": True,
        "non_target_anomaly": False,
        "self_reported_sla": 0.910,
        "desc": "High alert volume with timestamp jitter and spurious benign noise; investigations are thorough and benign.",
        "noise": NoiseParameters(is_noisy=True, noisy_alert_count_range=(55, 75)),
    },
    {
        "name": "AeroSpace Avionics Defense",
        "sector": "Healthcare & Defense",
        "scale": "large",
        "primary_category": "non-target anomalies",
        "categories": ["non-target anomalies"],
        "fast_closure": False,
        "escalation_gap": False,
        "repeated_unresolved": False,
        "coverage_gap": False,
        "data_outage": False,
        "noisy_data": False,
        "non_target_anomaly": True,
        "self_reported_sla": 0.960,
        "desc": "Operational surge during scheduled maintenance window with complete evidence; non-target statistical variance.",
        "noise": NoiseParameters(is_maintenance_anomaly=True, maintenance_alert_count_range=(40, 55)),
    },
]


# ---------------------------------------------------------------------------
# 5 HELD-OUT SCENARIOS (33.3% of catalog - Held-Out combinations across all 6 dimensions)
# ---------------------------------------------------------------------------
HELD_OUT_SCENARIO_CONFIGS: list[dict[str, Any]] = [
    {
        "name": "Pacific Clean Energy Grid",
        "sector": "Power & Energy",
        "scale": "medium",
        "primary_category": "normal behavior",
        "categories": ["normal behavior"],
        "fast_closure": False,
        "escalation_gap": False,
        "repeated_unresolved": False,
        "coverage_gap": False,
        "data_outage": False,
        "noisy_data": False,
        "non_target_anomaly": False,
        "self_reported_sla": 0.970,
        "desc": "Independent clean energy utility with novel renewable solar/BESS asset archetypes and distinct closure timing.",
        "timing": TimingParameters(normal_closure_range=(2400.0, 4800.0), investigation_evidence_range_normal=(4, 9)),
        "assets": [
            AssetArchetype("Solar Inverter Master Controller", "SCADA Controller", "CRITICAL", "Solar Field", "Active Solar Farm Telemetry"),
            AssetArchetype("BESS Energy Storage Gateway", "Identity Server", "CRITICAL", "Substation", "Active BESS Telemetry"),
            AssetArchetype("Grid Historian Database", "SQL Cluster", "HIGH", "DMZ", "Grid Metering Stream"),
            AssetArchetype("Field Telemetry Node", "Telemetry Node", "MEDIUM", "Data Center", "Historian Query Logs"),
        ],
    },
    {
        "name": "Apex Commercial Bank",
        "sector": "Financial Services",
        "scale": "large",
        "primary_category": "fast closure defect",
        "categories": ["fast closure defect", "escalation gap"],
        "fast_closure": True,
        "escalation_gap": True,
        "repeated_unresolved": False,
        "coverage_gap": False,
        "data_outage": False,
        "noisy_data": False,
        "non_target_anomaly": False,
        "self_reported_sla": 0.990,
        "desc": "Held-out banking entity: novel SWIFT ISO20022 wire assets, faster rapid closures (120-240s), and omitted escalations.",
        "timing": TimingParameters(fast_closure_range=(120.0, 240.0), investigation_evidence_range_defect=(0, 1)),
        "assets": [
            AssetArchetype("SWIFT ISO20022 Wire Terminal", "SCADA Controller", "CRITICAL", "Secured DMZ", "High-Value Wire Transaction Telemetry"),
            AssetArchetype("Real-Time Settlement Gateway", "Identity Server", "CRITICAL", "Core VPC", "Settlement Ledger Feed"),
            AssetArchetype("Core Ledger Database", "SQL Cluster", "HIGH", "Data Center", "Fraud Risk Scoring Logs"),
            AssetArchetype("ATM Network Forwarder", "Telemetry Node", "MEDIUM", "Field Branch", "ATM Transaction Logs"),
        ],
    },
    {
        "name": "Satellite Telecom Uplink Corp",
        "sector": "Telecommunications",
        "scale": "medium",
        "primary_category": "coverage gap",
        "categories": ["coverage gap"],
        "fast_closure": False,
        "escalation_gap": False,
        "repeated_unresolved": False,
        "coverage_gap": True,
        "data_outage": False,
        "noisy_data": False,
        "non_target_anomaly": False,
        "self_reported_sla": 0.955,
        "desc": "Held-out negative space scenario: novel Ka-band Satellite Transponder telemetry is completely silent.",
        "assets": [
            AssetArchetype("Ka-Band Satellite Transponder", "SCADA Controller", "CRITICAL", "Ground Station", "Ka-Band Satellite Telemetry"),
            AssetArchetype("Ground Station Auth Gateway", "Identity Server", "CRITICAL", "Antenna Array", "Antenna Positioning Stream"),
            AssetArchetype("Satellite Telemetry Database", "SQL Cluster", "HIGH", "Ground Hub", "Modulation Telemetry"),
            AssetArchetype("Ground Node Forwarder", "Telemetry Node", "MEDIUM", "DMZ", "Collector Health Logs"),
        ],
    },
    {
        "name": "Regional Trauma Center Alliance",
        "sector": "Healthcare & Defense",
        "scale": "medium",
        "primary_category": "repeated unresolved behavior",
        "categories": ["repeated unresolved behavior", "noisy data"],
        "fast_closure": False,
        "escalation_gap": False,
        "repeated_unresolved": True,
        "coverage_gap": False,
        "data_outage": False,
        "noisy_data": True,
        "non_target_anomaly": False,
        "self_reported_sla": 0.925,
        "desc": "Held-out healthcare scenario: novel DICOM/PACS medical assets, high background telemetry noise (60-80 alerts) + recurrent ransomware triggers with zero remediation.",
        "noise": NoiseParameters(is_noisy=True, noisy_alert_count_range=(60, 80)),
        "assets": [
            AssetArchetype("PACS Medical Imaging Core", "SCADA Controller", "CRITICAL", "Hospital Core", "DICOM Image Flow Logs"),
            AssetArchetype("ICU Vital Monitor Gateway", "Identity Server", "CRITICAL", "Intensive Care VLAN", "Vital Monitor Telemetry"),
            AssetArchetype("EHR Database Cluster", "SQL Cluster", "HIGH", "Data Center", "Prescription Access Audit"),
            AssetArchetype("Clinical Log Forwarder", "Telemetry Node", "MEDIUM", "Hospital LAN", "LIS Data Stream"),
        ],
    },
    {
        "name": "Urban Metrorail System",
        "sector": "Transportation",
        "scale": "large",
        "primary_category": "missing data",
        "categories": ["missing data", "non-target anomalies"],
        "fast_closure": False,
        "escalation_gap": False,
        "repeated_unresolved": False,
        "coverage_gap": False,
        "data_outage": True,
        "noisy_data": False,
        "non_target_anomaly": True,
        "self_reported_sla": 0.810,
        "desc": "Held-out telemetry disruption (very low alert count, low DQ) and track calibration maintenance; correctly handled without false positives.",
        "missingness": MissingnessParameters(is_data_outage=True, data_outage_alert_count=6),
        "noise": NoiseParameters(is_maintenance_anomaly=True, maintenance_category="Track Calibration & Signal Diagnostics"),
        "assets": [
            AssetArchetype("Track Calibration Signal Controller", "Signalling RTU", "CRITICAL", "Rail Substation", "Track Signal Diagnostics"),
            AssetArchetype("Automated Train Operation Engine", "ATO Server", "CRITICAL", "Rail Ops Center", "ATO Dispatch Stream"),
            AssetArchetype("Substation Power Monitor", "Telemetry Node", "HIGH", "Field Enclosure", "Power Feed Telemetry"),
            AssetArchetype("Maintenance Telemetry Forwarder", "IoT Gateway", "MEDIUM", "Rail Yard", "Yard Maintenance Feed"),
        ],
    },
]


def generate_parameterized_scenario(
    cfg: dict[str, Any] | ScenarioParameters,
    rng: random.Random,
    base_time: datetime,
    now: datetime,
) -> tuple[dict[str, list[dict[str, Any]]], GroundTruthScenario]:
    """
    Generates a single CSE scenario's operational telemetry adhering to strict
    Generator/Detector Independence rules across all 6 parametric dimensions.
    """
    if isinstance(cfg, ScenarioParameters):
        p = cfg
    else:
        timing = cfg.get("timing") or TimingParameters()
        severity = cfg.get("severity") or SeverityParameters()
        missingness = cfg.get("missingness") or MissingnessParameters(
            is_data_outage=cfg.get("data_outage", False)
        )
        noise = cfg.get("noise") or NoiseParameters(
            is_noisy=cfg.get("noisy_data", False),
            is_maintenance_anomaly=cfg.get("non_target_anomaly", False),
        )
        assets = cfg.get("assets") or build_default_assets(cfg["sector"], cfg["scale"])
        p = ScenarioParameters(
            name=cfg["name"],
            sector=cfg["sector"],
            scale=cfg["scale"],
            primary_category=cfg["primary_category"],
            categories=list(cfg.get("categories", [cfg["primary_category"]])),
            has_fast_closure=cfg.get("fast_closure", False),
            has_escalation_gap=cfg.get("escalation_gap", False),
            has_repeated_unresolved=cfg.get("repeated_unresolved", False),
            has_coverage_gap=cfg.get("coverage_gap", False),
            self_reported_sla=cfg.get("self_reported_sla", 0.95),
            description=cfg.get("desc", ""),
            timing=timing,
            severity=severity,
            assets=assets,
            missingness=missingness,
            noise=noise,
        )

    cse_id = uuid4()
    rep_id = uuid4()

    scenario_bundle: dict[str, list[dict[str, Any]]] = {
        "cse": [
            {
                "cse_id": str(cse_id),
                "name": p.name,
                "sector": p.sector,
                "scale": p.scale,
                "reporting_period_id": str(rep_id),
            }
        ],
        "reporting_periods": [
            {
                "reporting_period_id": str(rep_id),
                "cse_id": str(cse_id),
                "period_start": base_time.isoformat(),
                "period_end": now.isoformat(),
            }
        ],
        "assets": [],
        "alerts": [],
        "investigations": [],
        "cases": [],
        "escalations": [],
        "actions": [],
        "closures": [],
        "coverage_observations": [],
        "kpi_claims": [
            {
                "claim_id": str(uuid4()),
                "cse_id": str(cse_id),
                "reporting_period_id": str(rep_id),
                "metric_name": "SLA Compliance",
                "reported_value": p.self_reported_sla,
                "target_value": 60.0,
                "population": "All Alerts",
                "context": p.description,
            }
        ],
    }

    gt_scenario = GroundTruthScenario(
        cse_id=cse_id,
        cse_name=p.name,
        sector=p.sector,
        scale=p.scale,
        primary_category=p.primary_category,
        categories=list(p.categories),
        has_fast_closure=p.has_fast_closure,
        has_escalation_gap=p.has_escalation_gap,
        has_repeated_unresolved=p.has_repeated_unresolved,
        has_coverage_gap=p.has_coverage_gap,
        is_data_outage=p.missingness.is_data_outage,
        is_noisy_data=p.noise.is_noisy,
        is_non_target_anomaly=p.noise.is_maintenance_anomaly,
        self_reported_sla=p.self_reported_sla,
        description=p.description,
        parameters=p,
    )

    # 1. Assets
    asset_defs = p.assets if p.assets else build_default_assets(p.sector, p.scale)
    asset_tuples: list[tuple[UUID, str, str, str]] = []
    for a in asset_defs:
        a_id = uuid4()
        asset_tuples.append((a_id, a.name, a.asset_type, a.criticality))
        scenario_bundle["assets"].append(
            {
                "asset_id": str(a_id),
                "cse_id": str(cse_id),
                "criticality": a.criticality,
                "asset_type": a.asset_type,
                "environment": a.environment,
                "expected_monitoring_context": a.monitoring_context or f"Active monitoring for {a.name}",
            }
        )

    # 2. Alert Count Determination
    if p.missingness.is_data_outage:
        alert_count = p.missingness.data_outage_alert_count
    elif p.noise.is_noisy:
        alert_count = rng.randint(p.noise.noisy_alert_count_range[0], p.noise.noisy_alert_count_range[1])
    elif p.noise.is_maintenance_anomaly:
        alert_count = rng.randint(p.noise.maintenance_alert_count_range[0], p.noise.maintenance_alert_count_range[1])
    else:
        alert_count = rng.randint(28, 42)

    # 3. Alerts & Workflows
    for i in range(alert_count):
        alt_id = uuid4()
        case_id = uuid4()
        inv_id = uuid4()
        clo_id = uuid4()

        target_asset = asset_tuples[i % len(asset_tuples)]
        event_dt = base_time + timedelta(
            days=rng.uniform(1, 28), hours=rng.uniform(0, 23)
        )

        # Assign Severity
        if p.has_fast_closure or p.has_escalation_gap:
            sev = "CRITICAL" if i < 10 else ("HIGH" if i < 18 else "MEDIUM")
        elif p.noise.is_noisy:
            sev = rng.choice(["LOW", "MEDIUM", "INFO", "LOW", "MEDIUM", "HIGH"])
        else:
            sev = rng.choice(["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"])

        # Category
        if p.noise.is_maintenance_anomaly and i < 15:
            category = p.noise.maintenance_category
        else:
            category = rng.choice(
                [
                    "SCADA Intrusion",
                    "Ransomware",
                    "Privilege Escalation",
                    "Unauthorized Access",
                    "Brute Force",
                    "Malware Execution",
                ]
            )

        if p.has_repeated_unresolved and i < 6:
            target_asset = asset_tuples[0]
            category = "SCADA Intrusion" if "Power" in p.sector else ("Ransomware" if "Health" in p.sector else "Unauthorized Access")

        scenario_bundle["alerts"].append(
            {
                "alert_id": str(alt_id),
                "cse_id": str(cse_id),
                "asset_id": str(target_asset[0]),
                "reporting_period_id": str(rep_id),
                "event_time": event_dt.isoformat(),
                "severity": sev,
                "alert_category": category,
                "source": "Splunk/EDR",
                "status": "CLOSED",
            }
        )

        # Investigation
        inv_start = event_dt + timedelta(minutes=rng.uniform(1, 10))
        if p.has_fast_closure and sev in p.severity.defect_severities:
            duration_sec = rng.uniform(p.timing.fast_closure_range[0], p.timing.fast_closure_range[1])
            evidence_cnt = rng.choice([0, 1])
        elif p.noise.is_maintenance_anomaly:
            duration_sec = rng.uniform(p.timing.maintenance_closure_range[0], p.timing.maintenance_closure_range[1])
            evidence_cnt = rng.randint(4, 8)
        else:
            duration_sec = rng.uniform(p.timing.normal_closure_range[0], p.timing.normal_closure_range[1])
            evidence_cnt = rng.randint(p.timing.investigation_evidence_range_normal[0], p.timing.investigation_evidence_range_normal[1])

        inv_end = inv_start + timedelta(seconds=duration_sec)

        scenario_bundle["investigations"].append(
            {
                "investigation_id": str(inv_id),
                "alert_id": str(alt_id),
                "started_at": inv_start.isoformat(),
                "ended_at": inv_end.isoformat(),
                "analyst_id": f"analyst_{rng.randint(101, 115)}",
                "evidence_count": evidence_cnt,
                "disposition": "Maintenance Completed" if "Maintenance" in category or "Calibration" in category else "False Positive / Auto-Remediated",
            }
        )

        scenario_bundle["cases"].append(
            {
                "case_id": str(case_id),
                "alert_id": str(alt_id),
                "opened_at": inv_start.isoformat(),
                "closed_at": inv_end.isoformat(),
                "severity": sev,
                "outcome": "Closed per SOP",
            }
        )

        # Escalation
        if sev == "CRITICAL" and not p.has_escalation_gap:
            scenario_bundle["escalations"].append(
                {
                    "escalation_id": str(uuid4()),
                    "case_id": str(case_id),
                    "escalated_at": (inv_start + timedelta(minutes=5)).isoformat(),
                    "level": "Tier-2",
                    "target": "Senior Incident Responder",
                }
            )

        # Actions
        if not p.has_repeated_unresolved:
            scenario_bundle["actions"].append(
                {
                    "action_id": str(uuid4()),
                    "case_id": str(case_id),
                    "action_type": "Isolate Endpoint & Deploy Rule",
                    "performed_at": (inv_start + timedelta(minutes=15)).isoformat(),
                    "outcome": "Success",
                }
            )

        # Closure
        scenario_bundle["closures"].append(
            {
                "closure_id": str(clo_id),
                "case_id": str(case_id),
                "closed_at": inv_end.isoformat(),
                "reason": "Resolved",
                "reviewer": f"lead_{rng.randint(1, 5)}",
            }
        )

    # 4. Coverage Observations
    for a_id, a_name, a_type, a_crit in asset_tuples:
        expected_cnt = p.missingness.expected_coverage_count
        if p.has_coverage_gap and a_crit == "CRITICAL":
            # Silent critical asset
            obs_cnt = 0.0
        elif p.missingness.is_data_outage:
            expected_cnt = 0.0
            obs_cnt = 0.0
        else:
            obs_cnt = rng.uniform(
                p.missingness.observed_coverage_count_normal_range[0],
                p.missingness.observed_coverage_count_normal_range[1],
            )

        scenario_bundle["coverage_observations"].append(
            {
                "observation_id": str(uuid4()),
                "cse_id": str(cse_id),
                "asset_id": str(a_id),
                "alert_category": "SCADA Intrusion" if "Power" in p.sector else ("Ransomware" if "Health" in p.sector else "Core Security Telemetry"),
                "period_id": str(rep_id),
                "expected_count": expected_cnt,
                "observed_count": obs_cnt,
            }
        )

    return scenario_bundle, gt_scenario


def generate_synthetic_soc_benchmark(
    seed: int = 42,
    dataset_version_id: UUID | None = None,
    is_held_out: bool = False,
    custom_scenarios: list[dict[str, Any] | ScenarioParameters] | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], list[GroundTruthScenario]]:
    """
    Constructs multi-CSE synthetic datasets representing Power, Banking, Telecom, Transport, and Healthcare sectors.
    Adheres to the Generator/Detector Independence Protocol (SRS §19.4).
    Supports separate Tuning (10 scenarios) and Held-Out (5 scenarios, 33.3% ratio) suites covering all 8 categories
    with parameterized generation across timing, severity, asset class, peer composition, missingness, and noise.
    """
    rng = random.Random(seed + (1000 if is_held_out else 0))
    now = datetime.now(timezone.utc)
    base_time = now - timedelta(days=30)

    raw_bundle: dict[str, list[dict[str, Any]]] = {
        "cse": [],
        "reporting_periods": [],
        "assets": [],
        "alerts": [],
        "investigations": [],
        "cases": [],
        "escalations": [],
        "actions": [],
        "closures": [],
        "coverage_observations": [],
        "kpi_claims": [],
    }

    scenarios: list[GroundTruthScenario] = []
    configs = custom_scenarios or (HELD_OUT_SCENARIO_CONFIGS if is_held_out else TUNING_SCENARIO_CONFIGS)

    for cfg in configs:
        sc_bundle, sc_gt = generate_parameterized_scenario(cfg, rng, base_time, now)
        for tbl, rows in sc_bundle.items():
            raw_bundle[tbl].extend(rows)
        scenarios.append(sc_gt)

    return raw_bundle, scenarios


def run_full_analytical_pipeline(
    raw_bundle: dict[str, list[dict[str, Any]]],
    dataset_version_id: UUID | None = None,
    ruleset: AnalyticalRuleset | None = None,
) -> PipelineResult:
    """
    Executes the complete end-to-end analytical pipeline:
    Canonicalization -> Workflow Reconstruction -> Peer Benchmarking -> Data Trust ->
    Detectors (Fast Closure, Escalation Gap, Repeated Unresolved, Coverage Gap) -> Evidence Fusion.
    Parameters and weights are configured dynamically via versioned ruleset.
    """
    started_at = datetime.now(timezone.utc)
    ver_id = dataset_version_id or uuid4()
    analysis_run_id = uuid4()
    active_ruleset = ruleset or DEFAULT_AUTHORITATIVE_RULESET_V1

    # 1. Canonicalization
    canonical_ds = canonicalize_records(raw_bundle, ver_id)

    # 2. Workflow Reconstruction
    reconstructed_ds = ReconstructedDataset(canonical_ds)

    # 3. Peer Benchmarking Engine
    benchmark_engine = PeerBenchmarkEngine(reconstructed_ds)

    # 4. Data Quality Engine
    dq_result = evaluate_dataset_quality(canonical_ds, ver_id, ruleset=active_ruleset)

    # 5. Detectors (configured via versioned ruleset)
    fast_closure_detector = FastClosureDetector(config=active_ruleset.detector_config.fast_closure)
    escalation_gap_detector = EscalationGapDetector(config=active_ruleset.detector_config.escalation_gap)
    repeated_unresolved_detector = RepeatedUnresolvedDetector(config=active_ruleset.detector_config.repeated_unresolved)
    coverage_gap_detector = CoverageGapDetector(config=active_ruleset.detector_config.coverage_gap)
    from analytics.kpi_integrity.divergence_detector import ClaimEvidenceDivergenceDetector
    from analytics.kpi_integrity.outcome_divergence import MetricOutcomeDivergenceDetector
    from analytics.contradiction.evidence_contradiction import EvidenceContradictionEngine
    kpi_detector = ClaimEvidenceDivergenceDetector(ruleset=active_ruleset)
    outcome_detector = MetricOutcomeDivergenceDetector(ruleset=active_ruleset)
    contradiction_engine = EvidenceContradictionEngine(ruleset=active_ruleset)

    fast_closures = fast_closure_detector.detect(reconstructed_ds, benchmark_engine)
    escalation_gaps = escalation_gap_detector.detect(reconstructed_ds)
    repeated_unresolved = repeated_unresolved_detector.detect(reconstructed_ds)
    coverage_gaps = coverage_gap_detector.detect(canonical_ds, dq_result.score)
    kpi_findings = kpi_detector.detect(canonical_ds, reconstructed_ds, dq_result, analysis_run_id)
    outcome_findings = outcome_detector.detect(canonical_ds, reconstructed_ds, dq_result, benchmark_engine, analysis_run_id)
    contradictions = contradiction_engine.detect(canonical_ds, reconstructed_ds, dq_result, analysis_run_id)

    # 6. Evidence Fusion
    fusion_engine = EvidenceFusionEngine(ruleset=active_ruleset)
    all_findings: list[Finding] = []
    
    # Pre-add KPI findings to all_findings since fusion engine might not fuse them
    # if they are standalone supervisory findings. Actually, let's just append them.
    all_findings.extend(kpi_findings)
    all_findings.extend(outcome_findings)
    all_findings.extend(contradictions)

    for cse in canonical_ds.cse_list:
        rep_id = cse.reporting_period_id
        cse_findings = fusion_engine.fuse_signals(
            cse_id=cse.cse_id,
            reporting_period_id=rep_id,
            dataset_version_id=ver_id,
            analysis_run_id=analysis_run_id,
            data_quality_result=dq_result,
            fast_closures=fast_closures,
            escalation_gaps=escalation_gaps,
            repeated_unresolved=repeated_unresolved,
            coverage_gaps=coverage_gaps,
        )
        all_findings.extend(cse_findings)

    # 7. Attach source record refs to evidence references
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

    for f in all_findings:
        for ref in f.evidence_refs:
            if not ref.source_record_ref:
                if ref.entity_id in source_ref_map:
                    ref.source_record_ref = source_ref_map[ref.entity_id]
                else:
                    ref.source_record_ref = f"canonical:{ref.entity_type}:{ref.entity_id}"

    finished_at = datetime.now(timezone.utc)

    # 8. Record Analysis Run Provenance
    det_cfg = active_ruleset.detector_config.to_dict() if hasattr(active_ruleset.detector_config, "to_dict") else (active_ruleset.detector_config.model_dump() if hasattr(active_ruleset.detector_config, "model_dump") else dict(active_ruleset.detector_config))
    analysis_run = AnalysisRun(
        analysis_run_id=analysis_run_id,
        dataset_id=ver_id,
        dataset_version_id=ver_id,
        schema_version="2.0.0",
        ruleset_version=active_ruleset.version,
        ruleset_id=active_ruleset.ruleset_id,
        detector_config=det_cfg,
        app_version="1.0.0",
        started_at=started_at,
        finished_at=finished_at,
        status="COMPLETED",
        findings_count=len(all_findings),
    )

    return PipelineResult(
        canonical_dataset=canonical_ds,
        reconstructed_dataset=reconstructed_ds,
        benchmark_engine=benchmark_engine,
        findings=all_findings,
        data_quality_result=dq_result,
        analysis_run=analysis_run,
    )


def evaluate_ground_truth_validation(
    is_held_out: bool = False,
) -> dict[str, Any]:
    """
    Computes complete validation metrics against known ground truth scenarios (SRS §19.4):
    TP, FP, TN, FN, Precision, Recall, F1, False-Positive Rate (FPR), Top-K Recall, and Review Yield.
    """
    raw_bundle, scenarios = generate_synthetic_soc_benchmark(
        seed=101 if is_held_out else 42,
        is_held_out=is_held_out,
    )
    pipeline_res = run_full_analytical_pipeline(raw_bundle)
    findings = pipeline_res.findings

    detector_types = [
        "FAST_CLOSURE",
        "ESCALATION_GAP",
        "REPEATED_UNRESOLVED_ALERTS",
        "COVERAGE_GAP",
        "METRIC_OUTCOME_DIVERGENCE"
    ]

    # Build ground truth weakness map
    gt_map: dict[UUID, set[str]] = {}
    for s in scenarios:
        gt_set = set()
        if s.has_fast_closure:
            gt_set.add("FAST_CLOSURE")
        if s.has_escalation_gap:
            gt_set.add("ESCALATION_GAP")
        if s.has_repeated_unresolved:
            gt_set.add("REPEATED_UNRESOLVED_ALERTS")
        if s.has_coverage_gap and not s.is_data_outage:
            gt_set.add("COVERAGE_GAP")
            
        # Metric Outcome Divergence: high KPI but poor operational behavior
        if (s.has_fast_closure or s.has_escalation_gap or s.has_repeated_unresolved) and s.self_reported_sla >= 0.90:
            if not s.is_data_outage:
                gt_set.add("METRIC_OUTCOME_DIVERGENCE")
                
        gt_map[s.cse_id] = gt_set

    # Tally detections
    detected_pairs = set()
    for f in findings:
        pair = (f.cse_id, f.finding_type.value)
        detected_pairs.add(pair)

    tp = 0
    fp = 0
    tn = 0
    fn = 0

    for s in scenarios:
        expected_gts = gt_map.get(s.cse_id, set())
        for det in detector_types:
            is_gt_positive = det in expected_gts
            is_detected = (s.cse_id, det) in detected_pairs

            if is_gt_positive and is_detected:
                tp += 1
            elif not is_gt_positive and is_detected:
                fp += 1
            elif not is_gt_positive and not is_detected:
                tn += 1
            elif is_gt_positive and not is_detected:
                fn += 1

    total_gt = tp + fn
    total_neg = fp + tn

    precision = tp / max(tp + fp, 1)
    recall = tp / max(total_gt, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-6)
    fpr = fp / max(total_neg, 1)

    # Compute Supervisory Review Yield
    sorted_findings = sorted(findings, key=lambda f: f.priority_score, reverse=True)
    yield_curve = []
    accumulated_tp = 0
    seen_gt = set()

    for idx, f in enumerate(sorted_findings, start=1):
        pair = (f.cse_id, f.finding_type.value)
        if pair not in seen_gt:
            seen_gt.add(pair)
            if f.cse_id in gt_map and f.finding_type.value in gt_map[f.cse_id]:
                accumulated_tp += 1
        yield_curve.append(
            {
                "cases_reviewed": idx,
                "true_weaknesses_captured": accumulated_tp,
                "total_true_weaknesses": total_gt,
                "yield_percentage": round((accumulated_tp / max(total_gt, 1)) * 100, 1),
            }
        )

    # Compute category-level summary
    category_summary = {}
    for cat in SCENARIO_CATEGORIES:
        matching_scenarios = [s for s in scenarios if cat in s.categories or s.primary_category == cat]
        cat_tp = 0
        cat_fp = 0
        cat_tn = 0
        cat_fn = 0
        for s in matching_scenarios:
            expected_gts = gt_map.get(s.cse_id, set())
            for det in detector_types:
                is_gt_pos = det in expected_gts
                is_det = (s.cse_id, det) in detected_pairs
                if is_gt_pos and is_det:
                    cat_tp += 1
                elif not is_gt_pos and is_det:
                    cat_fp += 1
                elif not is_gt_pos and not is_det:
                    cat_tn += 1
                elif is_gt_pos and not is_det:
                    cat_fn += 1
        category_summary[cat] = {
            "scenario_count": len(matching_scenarios),
            "tp": cat_tp,
            "fp": cat_fp,
            "tn": cat_tn,
            "fn": cat_fn,
        }

    return {
        "dataset_split": "Held-Out Set" if is_held_out else "Tuning Set",
        "scenarios_evaluated": len(scenarios),
        "total_true_weaknesses": total_gt,
        "total_negative_hypotheses": total_neg,
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "false_positive_rate": round(fpr, 4),
        "top_k_recall": round(min(1.0, tp / max(total_gt, 1)), 4),
        "yield_summary": f"{accumulated_tp} of {total_gt} true supervisory weaknesses captured in top {len(sorted_findings)} prioritized cases.",
        "yield_curve": yield_curve,
        "category_summary": category_summary,
    }

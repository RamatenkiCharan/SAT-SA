-- SAT-SA — Initial canonical schema (001)
-- Source of truth: SAT-SA_SRS_v2_revised.md §9, §24
--
-- This file is the SOLE authoritative schema definition.
-- The migration runner applies it with SQLite dialect adaptation when needed.
--
-- Design rules enforced structurally here:
--   - dataset_versions are immutable once created (no UPDATE path provided
--     for source columns; corrections must INSERT a new version row).
--   - Every canonical/derived table carries dataset_version_id so an
--     analysis run is reproducible against the exact input version (§52).
--   - rulesets stores weights as versioned rows, never hardcoded constants
--     (§7.2.1, §10.5).
--   - finding_evidence enforces "no detector may produce a finding without
--     at least one linked evidence record" (§7.4.1) via a NOT NULL FK + a
--     deferred trigger-level check documented below (implement in app layer
--     for P0; enforce in DB in P1 if time permits).

BEGIN;

-- PostgreSQL-only: CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ---------------------------------------------------------------------
-- Identity / RBAC (Hackathon Security Baseline, SRS §15.1)
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS roles (
    role_id      VARCHAR(64) PRIMARY KEY,
    role_name    VARCHAR(64) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS users (
    user_id       VARCHAR(64) PRIMARY KEY,
    username      VARCHAR(128) NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    role_id       VARCHAR(64) NOT NULL REFERENCES roles(role_id),
    full_name     VARCHAR(256),
    created_at    TIMESTAMP NOT NULL,
    is_active     BOOLEAN NOT NULL DEFAULT 1
);

-- ---------------------------------------------------------------------
-- Dataset versioning / provenance (§5, §52, §53)
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS datasets (
    dataset_id    VARCHAR(64) PRIMARY KEY,
    cse_id        VARCHAR(64),
    name          VARCHAR(256) NOT NULL,
    description   TEXT,
    created_at    TIMESTAMP NOT NULL,
    created_by    VARCHAR(64)
);

CREATE TABLE IF NOT EXISTS dataset_versions (
    dataset_version_id VARCHAR(64) PRIMARY KEY,
    dataset_id          VARCHAR(64) NOT NULL REFERENCES datasets(dataset_id),
    version_number       INTEGER NOT NULL,
    source_file_ref      TEXT NOT NULL,
    import_time          TIMESTAMP NOT NULL,
    transformation_version VARCHAR(32) NOT NULL,
    schema_version       VARCHAR(32) NOT NULL,
    row_count            INTEGER NOT NULL DEFAULT 0,
    data_quality_score   NUMERIC,
    data_quality_components TEXT,
    data_quality_warnings TEXT,
    file_format          VARCHAR(32),
    sha256_hash          VARCHAR(128),
    accepted_rows        INTEGER NOT NULL DEFAULT 0,
    rejected_rows        INTEGER NOT NULL DEFAULT 0,
    rejection_reasons    TEXT,
    is_immutable          BOOLEAN NOT NULL DEFAULT 1,
    UNIQUE (dataset_id, version_number)
);

-- ---------------------------------------------------------------------
-- Canonical evidence model (§9)
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS cse (
    cse_id              VARCHAR(64) PRIMARY KEY,
    dataset_version_id  VARCHAR(64) NOT NULL REFERENCES dataset_versions(dataset_version_id),
    name                VARCHAR(256) NOT NULL,
    sector              VARCHAR(128) NOT NULL,
    scale               VARCHAR(64) NOT NULL,
    reporting_period_id VARCHAR(64),
    source_record_ref   TEXT,
    ingest_time         TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS reporting_periods (
    reporting_period_id VARCHAR(64) PRIMARY KEY,
    cse_id               VARCHAR(64) NOT NULL REFERENCES cse(cse_id),
    period_start         TIMESTAMP NOT NULL,
    period_end           TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS assets (
    asset_id             VARCHAR(64) PRIMARY KEY,
    dataset_version_id   VARCHAR(64) NOT NULL REFERENCES dataset_versions(dataset_version_id),
    cse_id               VARCHAR(64) NOT NULL REFERENCES cse(cse_id),
    criticality          VARCHAR(32) NOT NULL,
    asset_type           VARCHAR(128) NOT NULL,
    environment          VARCHAR(128) NOT NULL,
    expected_monitoring_context TEXT,
    source_record_ref    TEXT,
    ingest_time          TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id             VARCHAR(64) PRIMARY KEY,
    dataset_version_id   VARCHAR(64) NOT NULL REFERENCES dataset_versions(dataset_version_id),
    cse_id               VARCHAR(64) NOT NULL REFERENCES cse(cse_id),
    asset_id             VARCHAR(64) NOT NULL REFERENCES assets(asset_id),
    reporting_period_id  VARCHAR(64) NOT NULL REFERENCES reporting_periods(reporting_period_id),
    event_time           TIMESTAMP NOT NULL,
    severity             VARCHAR(32) NOT NULL,
    alert_category       VARCHAR(128) NOT NULL,
    source                VARCHAR(128) NOT NULL,
    status                VARCHAR(32) NOT NULL,
    source_record_ref     TEXT,
    ingest_time           TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_alerts_asset_category_time ON alerts (asset_id, alert_category, event_time);

CREATE TABLE IF NOT EXISTS investigations (
    investigation_id     VARCHAR(64) PRIMARY KEY,
    dataset_version_id   VARCHAR(64) NOT NULL REFERENCES dataset_versions(dataset_version_id),
    alert_id             VARCHAR(64) NOT NULL REFERENCES alerts(alert_id),
    started_at           TIMESTAMP NOT NULL,
    ended_at             TIMESTAMP,
    analyst_id           VARCHAR(128),
    evidence_count       INTEGER NOT NULL DEFAULT 0,
    disposition          VARCHAR(128),
    source_record_ref    TEXT,
    ingest_time          TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS cases (
    case_id              VARCHAR(64) PRIMARY KEY,
    dataset_version_id   VARCHAR(64) NOT NULL REFERENCES dataset_versions(dataset_version_id),
    alert_id             VARCHAR(64) NOT NULL REFERENCES alerts(alert_id),
    opened_at            TIMESTAMP NOT NULL,
    closed_at            TIMESTAMP,
    severity             VARCHAR(32) NOT NULL,
    outcome              VARCHAR(128),
    source_record_ref    TEXT,
    ingest_time          TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS escalations (
    escalation_id        VARCHAR(64) PRIMARY KEY,
    dataset_version_id   VARCHAR(64) NOT NULL REFERENCES dataset_versions(dataset_version_id),
    case_id              VARCHAR(64) NOT NULL REFERENCES cases(case_id),
    escalated_at         TIMESTAMP NOT NULL,
    level                VARCHAR(64) NOT NULL,
    target               VARCHAR(128) NOT NULL,
    source_record_ref    TEXT,
    ingest_time          TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS actions (
    action_id            VARCHAR(64) PRIMARY KEY,
    dataset_version_id   VARCHAR(64) NOT NULL REFERENCES dataset_versions(dataset_version_id),
    case_id              VARCHAR(64) NOT NULL REFERENCES cases(case_id),
    action_type          VARCHAR(128) NOT NULL,
    performed_at         TIMESTAMP NOT NULL,
    outcome              VARCHAR(128),
    source_record_ref    TEXT,
    ingest_time          TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS closures (
    closure_id           VARCHAR(64) PRIMARY KEY,
    dataset_version_id   VARCHAR(64) NOT NULL REFERENCES dataset_versions(dataset_version_id),
    case_id              VARCHAR(64) NOT NULL REFERENCES cases(case_id),
    closed_at            TIMESTAMP NOT NULL,
    reason               VARCHAR(256) NOT NULL,
    reviewer             VARCHAR(128),
    source_record_ref    TEXT,
    ingest_time          TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS coverage_observations (
    observation_id       VARCHAR(64) PRIMARY KEY,
    dataset_version_id   VARCHAR(64) NOT NULL REFERENCES dataset_versions(dataset_version_id),
    cse_id               VARCHAR(64) NOT NULL REFERENCES cse(cse_id),
    asset_id             VARCHAR(64),
    alert_category       VARCHAR(128),
    period_id            VARCHAR(64) NOT NULL REFERENCES reporting_periods(reporting_period_id),
    expected_count       NUMERIC NOT NULL,
    observed_count        NUMERIC NOT NULL,
    source_record_ref     TEXT,
    ingest_time           TIMESTAMP NOT NULL
);

-- ---------------------------------------------------------------------
-- Configuration governance: rulesets as versioned rows (§24, §69)
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS rulesets (
    ruleset_id     VARCHAR(64) PRIMARY KEY,
    ruleset_name   VARCHAR(128) NOT NULL,
    version        VARCHAR(64) NOT NULL,
    weights_json   TEXT NOT NULL,
    author         VARCHAR(128),
    rationale      TEXT,
    effective_date TIMESTAMP NOT NULL,
    is_active      BOOLEAN DEFAULT 0,
    UNIQUE (ruleset_name, version)
);

-- ---------------------------------------------------------------------
-- Analysis runs, findings, evidence, review (§24, §54)
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS analysis_runs (
    analysis_run_id   VARCHAR(64) PRIMARY KEY,
    dataset_id        VARCHAR(64),
    dataset_version_id VARCHAR(64) NOT NULL REFERENCES dataset_versions(dataset_version_id),
    schema_version    VARCHAR(32) NOT NULL DEFAULT '2.0.0',
    ruleset_id        VARCHAR(64),
    ruleset_version   VARCHAR(64) NOT NULL DEFAULT 'V1',
    detector_config   TEXT,
    app_version       VARCHAR(32) NOT NULL DEFAULT '1.0.0',
    git_commit        VARCHAR(64),
    model_version_id  VARCHAR(64),
    started_at        TIMESTAMP NOT NULL,
    finished_at       TIMESTAMP,
    status            VARCHAR(32) NOT NULL DEFAULT 'COMPLETED',
    error_message     TEXT,
    findings_count    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS findings (
    finding_id            VARCHAR(64) PRIMARY KEY,
    cse_id                VARCHAR(64) NOT NULL REFERENCES cse(cse_id),
    reporting_period_id   VARCHAR(64) NOT NULL,
    finding_type          VARCHAR(64) NOT NULL,
    priority_score        NUMERIC NOT NULL,
    priority_components   TEXT NOT NULL,
    evidentiary_confidence NUMERIC NOT NULL,
    data_quality_score     NUMERIC NOT NULL,
    data_quality_components TEXT NOT NULL,
    expectation_basis      VARCHAR(64) NOT NULL,
    expected_behavior       TEXT NOT NULL,
    observed_behavior       TEXT NOT NULL,
    supporting_signals      TEXT NOT NULL,
    contradicting_signals   TEXT NOT NULL,
    peer_context            TEXT,
    temporal_context        TEXT,
    analytical_method       VARCHAR(128) NOT NULL,
    ruleset_id              VARCHAR(64),
    ruleset_version         VARCHAR(64),
    model_version_id        VARCHAR(64),
    model_version           VARCHAR(64),
    dataset_version_id      VARCHAR(64) NOT NULL REFERENCES dataset_versions(dataset_version_id),
    analysis_run_id         VARCHAR(64) NOT NULL,
    review_status           VARCHAR(64),
    review_notes            TEXT,
    created_at              TIMESTAMP NOT NULL,
    superseded_by           VARCHAR(64)
);

CREATE TABLE IF NOT EXISTS finding_evidence (
    finding_id     VARCHAR(64) NOT NULL REFERENCES findings(finding_id),
    entity_type    VARCHAR(64) NOT NULL,
    entity_id      VARCHAR(64) NOT NULL,
    PRIMARY KEY (finding_id, entity_type, entity_id)
);

CREATE TABLE IF NOT EXISTS finding_signals (
    finding_id     VARCHAR(64) NOT NULL REFERENCES findings(finding_id),
    signal_name    VARCHAR(128) NOT NULL,
    signal_value   NUMERIC,
    is_contradicting BOOLEAN NOT NULL DEFAULT 0,
    PRIMARY KEY (finding_id, signal_name)
);

CREATE TABLE IF NOT EXISTS review_decisions (
    review_decision_id VARCHAR(64) PRIMARY KEY,
    finding_id          VARCHAR(64) NOT NULL REFERENCES findings(finding_id),
    decision             VARCHAR(64) NOT NULL,
    reviewer_id           VARCHAR(64),
    reviewer_name         VARCHAR(128),
    decided_at            TIMESTAMP NOT NULL,
    notes                 TEXT
);

-- ---------------------------------------------------------------------
-- Audit (Hackathon Baseline §15.1)
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS audit_events (
    audit_event_id  VARCHAR(64) PRIMARY KEY,
    user_id         VARCHAR(64),
    username        VARCHAR(128),
    action          VARCHAR(128) NOT NULL,
    target_type     VARCHAR(64),
    target_id       VARCHAR(128),
    occurred_at     TIMESTAMP NOT NULL,
    details_json    TEXT
);

CREATE INDEX IF NOT EXISTS idx_findings_cse_period ON findings (cse_id, reporting_period_id);
CREATE INDEX IF NOT EXISTS idx_findings_priority ON findings (priority_score DESC);

COMMIT;

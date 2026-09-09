-- SAT-SA — Initial canonical schema
-- Source of truth: SAT-SA_SRS_v2_revised.md §9, §24
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

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ---------------------------------------------------------------------
-- Identity / RBAC (Hackathon Security Baseline, SRS §15.1)
-- ---------------------------------------------------------------------

CREATE TABLE roles (
    role_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_name    TEXT NOT NULL UNIQUE  -- supervisor | analyst | admin
);

CREATE TABLE users (
    user_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role_id       UUID NOT NULL REFERENCES roles(role_id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_active     BOOLEAN NOT NULL DEFAULT true
);

-- ---------------------------------------------------------------------
-- Dataset versioning / provenance (§5, §52, §53)
-- ---------------------------------------------------------------------

CREATE TABLE datasets (
    dataset_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cse_id        UUID,  -- FK added after cse table exists (below)
    name          TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by    UUID REFERENCES users(user_id)
);

CREATE TABLE dataset_versions (
    dataset_version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id          UUID NOT NULL REFERENCES datasets(dataset_id),
    version_number       INTEGER NOT NULL,
    source_file_ref      TEXT NOT NULL,
    import_time          TIMESTAMPTZ NOT NULL DEFAULT now(),
    transformation_version TEXT NOT NULL,
    schema_version       TEXT NOT NULL,
    is_immutable          BOOLEAN NOT NULL DEFAULT true,
    UNIQUE (dataset_id, version_number)
);
-- Immutability is enforced at the application layer (services/ingestion.py):
-- no UPDATE statement is ever issued against a row in this table after insert.

-- ---------------------------------------------------------------------
-- Canonical evidence model (§9)
-- ---------------------------------------------------------------------

CREATE TABLE cse (
    cse_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_version_id  UUID NOT NULL REFERENCES dataset_versions(dataset_version_id),
    name                TEXT NOT NULL,
    sector              TEXT NOT NULL,
    scale               TEXT NOT NULL,
    source_record_ref   TEXT,
    ingest_time         TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE datasets ADD CONSTRAINT fk_datasets_cse FOREIGN KEY (cse_id) REFERENCES cse(cse_id);

CREATE TABLE reporting_periods (
    reporting_period_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cse_id               UUID NOT NULL REFERENCES cse(cse_id),
    period_start         TIMESTAMPTZ NOT NULL,
    period_end           TIMESTAMPTZ NOT NULL
);

CREATE TABLE assets (
    asset_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_version_id   UUID NOT NULL REFERENCES dataset_versions(dataset_version_id),
    cse_id               UUID NOT NULL REFERENCES cse(cse_id),
    criticality          TEXT NOT NULL CHECK (criticality IN ('CRITICAL','HIGH','MEDIUM','LOW')),
    asset_type           TEXT NOT NULL,
    environment          TEXT NOT NULL,
    expected_monitoring_context TEXT,
    source_record_ref    TEXT,
    ingest_time          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE alerts (
    alert_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_version_id   UUID NOT NULL REFERENCES dataset_versions(dataset_version_id),
    cse_id               UUID NOT NULL REFERENCES cse(cse_id),
    asset_id             UUID NOT NULL REFERENCES assets(asset_id),
    reporting_period_id  UUID NOT NULL REFERENCES reporting_periods(reporting_period_id),
    event_time           TIMESTAMPTZ NOT NULL,
    severity             TEXT NOT NULL CHECK (severity IN ('CRITICAL','HIGH','MEDIUM','LOW','INFO')),
    alert_category       TEXT NOT NULL,
    source                TEXT NOT NULL,
    status                TEXT NOT NULL CHECK (status IN ('OPEN','INVESTIGATING','ESCALATED','CLOSED','REOPENED')),
    source_record_ref     TEXT,
    ingest_time           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_alerts_asset_category_time ON alerts (asset_id, alert_category, event_time);

CREATE TABLE investigations (
    investigation_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_version_id   UUID NOT NULL REFERENCES dataset_versions(dataset_version_id),
    alert_id             UUID NOT NULL REFERENCES alerts(alert_id),
    started_at           TIMESTAMPTZ NOT NULL,
    ended_at             TIMESTAMPTZ,
    analyst_id           TEXT,
    evidence_count       INTEGER NOT NULL DEFAULT 0 CHECK (evidence_count >= 0),
    disposition          TEXT,
    source_record_ref    TEXT,
    ingest_time          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE cases (
    case_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_version_id   UUID NOT NULL REFERENCES dataset_versions(dataset_version_id),
    alert_id             UUID NOT NULL REFERENCES alerts(alert_id),
    opened_at            TIMESTAMPTZ NOT NULL,
    closed_at            TIMESTAMPTZ,
    severity             TEXT NOT NULL CHECK (severity IN ('CRITICAL','HIGH','MEDIUM','LOW','INFO')),
    outcome              TEXT,
    source_record_ref    TEXT,
    ingest_time          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE escalations (
    escalation_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_version_id   UUID NOT NULL REFERENCES dataset_versions(dataset_version_id),
    case_id              UUID NOT NULL REFERENCES cases(case_id),
    escalated_at         TIMESTAMPTZ NOT NULL,
    level                TEXT NOT NULL,
    target               TEXT NOT NULL,
    source_record_ref    TEXT,
    ingest_time          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE actions (
    action_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_version_id   UUID NOT NULL REFERENCES dataset_versions(dataset_version_id),
    case_id              UUID NOT NULL REFERENCES cases(case_id),
    action_type          TEXT NOT NULL,
    performed_at         TIMESTAMPTZ NOT NULL,
    outcome              TEXT,
    source_record_ref    TEXT,
    ingest_time          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE closures (
    closure_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_version_id   UUID NOT NULL REFERENCES dataset_versions(dataset_version_id),
    case_id              UUID NOT NULL REFERENCES cases(case_id),
    closed_at            TIMESTAMPTZ NOT NULL,
    reason               TEXT NOT NULL,
    reviewer             TEXT,
    source_record_ref    TEXT,
    ingest_time          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE coverage_observations (
    observation_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_version_id   UUID NOT NULL REFERENCES dataset_versions(dataset_version_id),
    cse_id               UUID NOT NULL REFERENCES cse(cse_id),
    asset_id             UUID REFERENCES assets(asset_id),
    alert_category       TEXT,
    period_id            UUID NOT NULL REFERENCES reporting_periods(reporting_period_id),
    expected_count       NUMERIC NOT NULL CHECK (expected_count >= 0),
    observed_count        NUMERIC NOT NULL CHECK (observed_count >= 0),
    source_record_ref     TEXT,
    ingest_time           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- Peer grouping (§7.7)
-- ---------------------------------------------------------------------

CREATE TABLE peer_groups (
    peer_group_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    definition     TEXT NOT NULL
);

CREATE TABLE peer_memberships (
    peer_group_id  UUID NOT NULL REFERENCES peer_groups(peer_group_id),
    cse_id         UUID NOT NULL REFERENCES cse(cse_id),
    PRIMARY KEY (peer_group_id, cse_id)
);

-- ---------------------------------------------------------------------
-- Configuration governance: rulesets as versioned rows (§24, §69)
-- ---------------------------------------------------------------------

CREATE TABLE rulesets (
    ruleset_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ruleset_name   TEXT NOT NULL,        -- e.g. 'data_quality_score', 'evidence_fusion'
    version        TEXT NOT NULL,        -- e.g. 'V1'
    weights_json   JSONB NOT NULL,
    author         TEXT,
    rationale      TEXT,
    effective_date TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (ruleset_name, version)
);

CREATE TABLE model_versions (
    model_version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name        TEXT NOT NULL,
    version           TEXT NOT NULL,
    feature_schema    JSONB,
    training_data_description TEXT,
    evaluation_record JSONB,
    activation_status TEXT NOT NULL DEFAULT 'INACTIVE',
    UNIQUE (model_name, version)
);

-- ---------------------------------------------------------------------
-- Analysis runs, findings, evidence, review (§24, §54)
-- ---------------------------------------------------------------------

CREATE TABLE analysis_runs (
    analysis_run_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_version_id UUID NOT NULL REFERENCES dataset_versions(dataset_version_id),
    ruleset_id         UUID REFERENCES rulesets(ruleset_id),
    model_version_id   UUID REFERENCES model_versions(model_version_id),
    started_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at        TIMESTAMPTZ,
    status             TEXT NOT NULL DEFAULT 'RUNNING'  -- RUNNING | COMPLETED | FAILED
);

CREATE TABLE analytical_features (
    feature_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_run_id   UUID NOT NULL REFERENCES analysis_runs(analysis_run_id),
    scope_type        TEXT NOT NULL,   -- 'cse' | 'asset' | 'case' | ...
    scope_id          UUID NOT NULL,
    feature_name      TEXT NOT NULL,
    feature_value     NUMERIC,
    computed_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE findings (
    finding_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cse_id                UUID NOT NULL REFERENCES cse(cse_id),
    reporting_period_id   UUID NOT NULL REFERENCES reporting_periods(reporting_period_id),
    finding_type          TEXT NOT NULL CHECK (finding_type IN
                             ('FAST_CLOSURE','ESCALATION_GAP','REPEATED_UNRESOLVED_ALERTS','COVERAGE_GAP')),
    priority_score        NUMERIC NOT NULL CHECK (priority_score >= 0 AND priority_score <= 1),
    priority_components   JSONB NOT NULL,
    evidentiary_confidence NUMERIC NOT NULL CHECK (evidentiary_confidence >= 0 AND evidentiary_confidence <= 1),
    data_quality_score     NUMERIC NOT NULL,
    data_quality_components JSONB NOT NULL,
    expectation_basis      TEXT NOT NULL,
    expected_behavior       TEXT NOT NULL,
    observed_behavior       TEXT NOT NULL,
    supporting_signals      JSONB NOT NULL DEFAULT '[]',
    contradicting_signals   JSONB NOT NULL DEFAULT '[]',
    peer_context            TEXT,
    temporal_context        TEXT,
    analytical_method       TEXT NOT NULL,
    ruleset_id              UUID REFERENCES rulesets(ruleset_id),
    model_version_id        UUID REFERENCES model_versions(model_version_id),
    dataset_version_id      UUID NOT NULL REFERENCES dataset_versions(dataset_version_id),
    analysis_run_id         UUID NOT NULL REFERENCES analysis_runs(analysis_run_id),
    review_status           TEXT,   -- CONFIRMED | FALSE_POSITIVE | NEEDS_INVESTIGATION | INSUFFICIENT_EVIDENCE
    review_notes            TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    superseded_by           UUID REFERENCES findings(finding_id)  -- append-only history (skill 06)
);

CREATE TABLE finding_evidence (
    finding_id     UUID NOT NULL REFERENCES findings(finding_id),
    entity_type    TEXT NOT NULL,
    entity_id      UUID NOT NULL,
    PRIMARY KEY (finding_id, entity_type, entity_id)
);
-- Application layer MUST reject any finding insert that would leave it with
-- zero rows here (§7.4.1: "no detector may produce a finding without at
-- least one linked evidence record").

CREATE TABLE finding_signals (
    finding_id     UUID NOT NULL REFERENCES findings(finding_id),
    signal_name    TEXT NOT NULL,
    signal_value   NUMERIC,
    is_contradicting BOOLEAN NOT NULL DEFAULT false,
    PRIMARY KEY (finding_id, signal_name)
);

CREATE TABLE review_decisions (
    review_decision_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    finding_id          UUID NOT NULL REFERENCES findings(finding_id),
    decision             TEXT NOT NULL CHECK (decision IN
                            ('CONFIRMED','FALSE_POSITIVE','NEEDS_INVESTIGATION','INSUFFICIENT_EVIDENCE')),
    reviewer_id           UUID REFERENCES users(user_id),
    decided_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    notes                 TEXT
);

-- ---------------------------------------------------------------------
-- Audit (Hackathon Baseline §15.1)
-- ---------------------------------------------------------------------

CREATE TABLE audit_events (
    audit_event_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(user_id),
    action          TEXT NOT NULL,     -- e.g. 'IMPORT_DATASET', 'REVIEW_FINDING', 'EXPORT_REPORT'
    target_type     TEXT,
    target_id       UUID,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    details_json    JSONB
);

CREATE INDEX idx_findings_cse_period ON findings (cse_id, reporting_period_id);
CREATE INDEX idx_findings_priority ON findings (priority_score DESC);

COMMIT;

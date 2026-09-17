-- SAT-SA — KPI Claims schema (003)
-- Innovation Phase 1: Claim-Evidence Integrity

BEGIN;

CREATE TABLE IF NOT EXISTS kpi_claims (
    claim_id             VARCHAR(64) PRIMARY KEY,
    dataset_version_id   VARCHAR(64) NOT NULL REFERENCES dataset_versions(dataset_version_id),
    cse_id               VARCHAR(64) NOT NULL REFERENCES cse(cse_id),
    reporting_period_id  VARCHAR(64) NOT NULL REFERENCES reporting_periods(reporting_period_id),
    metric_name          VARCHAR(128) NOT NULL,
    reported_value       REAL NOT NULL,
    target_value         REAL,
    population           VARCHAR(128),
    context              TEXT,
    source_record_ref    TEXT,
    ingest_time          TIMESTAMP NOT NULL
);

COMMIT;

-- SAT-SA — 002 — Add application settings and evidence messages tables
-- Adds:
--   app_settings: key-value store for durable application-level configuration
--                 (e.g. active dataset version that survives restart).
--   evidence_messages: supervisory evidence inquiry messages linked to findings.
--   finding_signals: decomposed signal rows for findings.
--   model_versions: registered analytical model versions.
--   peer_groups / peer_memberships: peer group definitions.
--   analytical_features: per-run computed features.

BEGIN;

-- Application settings (durable configuration surviving restart)
CREATE TABLE IF NOT EXISTS app_settings (
    setting_key   VARCHAR(128) PRIMARY KEY,
    setting_value TEXT NOT NULL,
    updated_at    TIMESTAMP NOT NULL
);

-- Evidence messages (supervisory evidence inquiry messages)
CREATE TABLE IF NOT EXISTS evidence_messages (
    message_id   VARCHAR(64) PRIMARY KEY,
    finding_id   VARCHAR(64) NOT NULL,
    evidence_id  VARCHAR(128),
    sender_id    VARCHAR(64) NOT NULL,
    sender_name  VARCHAR(128) NOT NULL,
    sender_role  VARCHAR(64) NOT NULL,
    recipient    VARCHAR(128) NOT NULL,
    message      TEXT NOT NULL,
    sent_at      TIMESTAMP NOT NULL
);

COMMIT;

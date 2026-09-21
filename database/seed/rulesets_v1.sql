-- Versioned ruleset weights (SRS §7.2.1 Data Quality Score, §10.5 Evidence Fusion).
-- These are the ONLY place these numbers should live. Application code reads
-- them from this table (via rulesets_repository) - never hardcode a weight
-- inline in a detector or fusion module (AGENTS.md §28 Rule Governance).

INSERT INTO rulesets (ruleset_name, version, weights_json, author, rationale, effective_date)
VALUES
(
    'data_quality_score', 'V1',
    '{
        "completeness_weight": 0.35,
        "consistency_weight": 0.25,
        "coverage_weight": 0.25,
        "sample_sufficiency_weight": 0.15,
        "minimum_sample_size_default": 30
    }'::jsonb,
    'SAT-SA team', 'Pinned per SRS v2.0 §7.2.1 - replaces prior unspecified 92% figure.',
    now()
),
(
    'evidence_fusion_priority', 'V1',
    '{
        "signal_strength_weight": 0.30,
        "peer_deviation_weight": 0.25,
        "persistence_weight": 0.20,
        "asset_criticality_weight": 0.15,
        "data_uncertainty_weight": -0.10,
        "signal_strength_cap": 3,
        "peer_deviation_zscore_cap": 3.0,
        "high_priority_min_independent_signals": 2,
        "high_priority_min_data_quality": 0.6
    }'::jsonb,
    'SAT-SA team', 'Pinned per SRS v2.0 §10.5.',
    now()
),
(
    'fast_closure_detector', 'EG_FAST_CLOSURE_V1',
    '{
        "mad_multiplier": 2.5,
        "investigation_evidence_percentile": 25,
        "min_peer_group_size": 5
    }'::jsonb,
    'SAT-SA team', 'Pinned per SRS v2.0 §7.4.1 FR-030.',
    now()
),
(
    'escalation_gap_detector', 'EG_ESCALATION_GAP_V1',
    '{
        "applies_to_severity": ["CRITICAL"]
    }'::jsonb,
    'SAT-SA team', 'Pinned per SRS v2.0 §7.4.1 FR-032.',
    now()
),
(
    'repeated_unresolved_alerts_detector', 'EG_REPEATED_UNRESOLVED_V1',
    '{
        "min_occurrences": 3,
        "window_days": 30
    }'::jsonb,
    'SAT-SA team', 'Pinned per SRS v2.0 §7.4.1 FR-033.',
    now()
),
(
    'coverage_gap_detector', 'NS_COVERAGE_GAP_V1',
    '{
        "coverage_ratio_threshold": 0.3,
        "min_data_quality_to_flag": 0.7,
        "applies_to_criticality": ["CRITICAL", "HIGH"]
    }'::jsonb,
    'SAT-SA team', 'Pinned per SRS v2.0 §7.5.1 FR-041. Data-quality gate MUST run first.',
    now()
);

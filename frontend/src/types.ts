export type Severity = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "INFO";

export type FindingType =
  | "FAST_CLOSURE"
  | "ESCALATION_GAP"
  | "REPEATED_UNRESOLVED_ALERTS"
  | "COVERAGE_GAP"
  | "SUPERVISORY_DIVERGENCE"
  | "METRIC_OUTCOME_DIVERGENCE"
  | "EVIDENCE_CONTRADICTION";

export type ReviewDecisionState =
  | "CONFIRMED"
  | "FALSE_POSITIVE"
  | "NEEDS_INVESTIGATION"
  | "INSUFFICIENT_EVIDENCE";

export type EvidenceSufficiencyState =
  | "SUPPORTED"
  | "WEAKLY_SUPPORTED"
  | "INSUFFICIENT_EVIDENCE"
  | "NOT_ASSESSABLE";

export interface DataQualityBreakdown {
  overall_score: number;
  completeness: number;
  consistency: number;
  coverage: number;
  sample_sufficiency: number;
}

export interface Finding {
  finding_id: string;
  cse_id: string;
  cse_name: string;
  sector: string;
  finding_type: FindingType;
  detector?: string;
  detector_version?: string;
  reason?: string;
  source_entity?: {
    cse_id: string;
    cse_name: string;
    sector: string;
  };
  source_record_ids?: string[];
  evidence_references?: Array<{
    entity_type: string;
    entity_id: string;
    source_record_ref?: string | null;
  }>;
  calculation_inputs?: Record<string, any>;
  calculation_result?: Record<string, any>;
  dataset_version?: {
    dataset_version_id: string;
    version_number?: number;
  };
  analysis_run?: {
    analysis_run_id: string;
    ruleset_version?: string;
  };
  ruleset_version?: string;
  priority_score: number;
  priority_label: "HIGH" | "MEDIUM" | "LOW";
  evidentiary_confidence: number;
  data_quality_score: number;
  evidence_state?: EvidenceSufficiencyState;
  title: string;
  headline: string;
  expected_behavior: string;
  observed_behavior: string;
  supporting_signals: string[];
  contradicting_signals: string[];
  priority_components: {
    signal_strength: number;
    peer_deviation: number;
    persistence: number;
    asset_criticality: number;
    data_uncertainty: number;
    [key: string]: any;
  };
  data_quality_breakdown: DataQualityBreakdown;
  recommended_action: string;
  evidence_record_count: number;
  review_status: ReviewDecisionState | null;
  review_notes?: string | null;
  created_at: string;
}

export interface EvidenceAlert {
  alert_id: string;
  source_record_id?: string;
  source_record_ref?: string | null;
  severity: Severity;
  alert_category: string;
  source: string;
  status: string;
  event_time: string;
  asset_type: string;
  environment: string;
  asset_criticality: string;
}

export interface EvidenceCase {
  case_id: string;
  source_record_id?: string;
  source_record_ref?: string | null;
  opened_at: string;
  closed_at: string | null;
  severity: Severity;
  outcome: string | null;
}

export interface EvidenceInvestigation {
  investigation_id: string;
  source_record_id?: string;
  source_record_ref?: string | null;
  analyst_id: string | null;
  evidence_count: number;
  started_at: string;
  ended_at: string | null;
  disposition: string | null;
}

export interface EvidenceEscalation {
  escalation_id: string;
  source_record_id?: string;
  source_record_ref?: string | null;
  case_id: string;
  escalated_at: string;
  level: string;
  target: string;
}

export interface EvidenceAction {
  action_id: string;
  source_record_id?: string;
  source_record_ref?: string | null;
  action_type: string;
  performed_at: string;
  outcome: string | null;
}

export interface EvidenceClosure {
  closure_id: string;
  source_record_id?: string;
  source_record_ref?: string | null;
  closed_at: string;
  reason: string;
  reviewer: string | null;
}

export interface EvidenceAsset {
  asset_id: string;
  source_record_id?: string;
  source_record_ref?: string | null;
  asset_type: string;
  criticality: string;
  environment: string;
  expected_monitoring_context: string | null;
}

export interface FindingEvidenceRecords {
  finding_id: string;
  cse_id: string;
  cse_name: string;
  sector: string;
  evidence_state?: EvidenceSufficiencyState;
  total_evidence_count?: number;
  source_record_ids?: string[];
  evidence_references?: Array<{
    entity_type: string;
    entity_id: string;
    source_record_ref?: string | null;
  }>;
  alerts: EvidenceAlert[];
  cases: EvidenceCase[];
  investigations: EvidenceInvestigation[];
  escalations: EvidenceEscalation[];
  actions: EvidenceAction[];
  closures: EvidenceClosure[];
  assets: EvidenceAsset[];
}

export interface FindingProvenance {
  source_file_ref: string;
  sha256_hash?: string | null;
  file_format?: string | null;
  import_time: string;
  dataset_id: string;
  dataset_name: string;
  dataset_version_id: string;
  version_number: number;
  row_count: number;
  data_quality_score: number;
  analysis_run_id: string;
  schema_version: string;
  ruleset_version: string;
  detector_config: Record<string, any>;
  app_version: string;
  git_commit?: string | null;
  started_at: string;
  finished_at?: string | null;
  status: string;
  error_message?: string | null;
  finding_id: string;
  finding_type: string;
  detector?: string;
  detector_version?: string;
  reason?: string;
  source_entity?: Record<string, any>;
  source_record_ids?: string[];
  priority_score: number;
  priority_label: string;
  evidentiary_confidence: number;
  calculation_inputs?: Record<string, any>;
  calculation_result?: Record<string, any>;
  evidence_records_count: number;
  evidence_refs: Array<{
    entity_type: string;
    entity_id: string;
    source_record_ref?: string | null;
  }>;
}

export interface FindingDetail extends Finding {
  explanation: {
    title: string;
    priority_label: string;
    priority_score: number;
    headline: string;
    what_happened?: string;
    why_flagged?: string;
    supporting_evidence_summary?: string;
    confidence_summary?: string;
    peer_context_summary?: string;
    data_quality_limitation?: string;
    expected_behavior: string;
    observed_behavior: string;
    supporting_signals: string[];
    contradicting_signals: string[];
    peer_context?: string;
    temporal_context?: string;
    priority_breakdown: string[];
    data_quality_breakdown: DataQualityBreakdown;
    evidence_record_count: number;
    recommended_action: string;
    analytical_method: string;
    provenance: {
      ruleset_version: string;
      dataset_version_id: string;
      analysis_run_id: string;
    };
  };
  evidence_records: FindingEvidenceRecords;
  provenance?: FindingProvenance;
}


export interface CSEBenchmarkMetric {
  cse_id: string;
  cse_name: string;
  sector: string;
  scale: string;
  operational_profile?: string;
  total_alerts: number;
  critical_alerts_count: number;
  median_critical_closure_minutes: number;
  median_evidence_count: number;
  critical_escalation_ratio: number;
  repeat_alert_rate: number;
  self_reported_sla_compliance: number;
}

export type PeerFallbackState = "DIRECT" | "RELAXED_COHORT" | "GLOBAL_FALLBACK" | "INSUFFICIENT_PEER_DATA";

export interface PeerCohort {
  peer_id: string;
  sector: string;
  scale: string;
  group_size: number;
  is_fallback_global: boolean;
  fallback_state?: PeerFallbackState;
  confidence?: number;
  dimensions?: Record<string, string>;
  closure_duration: {
    median_minutes: number;
    mad_minutes: number;
    p25_minutes: number;
    p75_minutes: number;
  };
  evidence_count: {
    median: number;
    mad: number;
    p25: number;
    p75: number;
  };
  escalation_ratio: {
    median_percent: number;
    mad_percent: number;
  };
}

export interface AssetCohort {
  cohort_key: string;
  asset_class: string;
  criticality: string;
  environment: string;
  operational_profile: string;
  cohort_size: number;
  closure_duration: {
    median_minutes: number;
    mad_minutes: number;
    p25_minutes: number;
    p75_minutes: number;
  };
  evidence_count: {
    median: number;
    mad: number;
    p25: number;
    p75: number;
  };
}

export interface PeerComparisonResult {
  peer_group: string;
  peer_size: number;
  entity_value: number;
  peer_median: number;
  deviation: number;
  confidence: number;
  fallback_state: PeerFallbackState;
  mad: number;
  z_score: number;
  p25: number;
  p75: number;
  dimensions: Record<string, string>;
  dataset_version_id?: string | null;
  analysis_run_id?: string | null;
  ruleset_version?: string;
  is_suppressed: boolean;
  explanation: string;
}

export interface YieldCurvePoint {
  cases_reviewed: number;
  true_weaknesses_captured: number;
  total_true_weaknesses: number;
  yield_percentage: number;
}

export interface ValidationSplitResult {
  dataset_split: string;
  scenarios_evaluated: number;
  total_true_weaknesses: number;
  total_negative_hypotheses?: number;
  true_positives: number;
  false_positives: number;
  true_negatives?: number;
  false_negatives: number;
  precision: number;
  recall: number;
  f1_score: number;
  false_positive_rate?: number;
  top_k_recall: number;
  yield_summary: string;
  yield_curve: YieldCurvePoint[];
  category_summary?: Record<
    string,
    { scenario_count: number; tp: number; fp: number; tn: number; fn: number }
  >;
}

export interface CategoryPerformanceItem {
  category_name: string;
  scenario_count: number;
  tp: number;
  fp: number;
  tn: number;
  fn: number;
  precision: number;
  recall: number;
  false_positive_rate: number;
  status: string;
}

export interface ScenarioValidationItem {
  cse_id: string;
  cse_name: string;
  sector: string;
  scale: string;
  primary_category: string;
  categories: string[];
  self_reported_sla: number;
  expected_weaknesses: string[];
  detected_weaknesses: string[];
  status: string;
  description: string;
}

export interface ProtocolSplitReport {
  split_name: string;
  is_held_out: boolean;
  seed: number;
  total_scenarios: number;
  scenarios: ScenarioValidationItem[];
  confusion_matrix: {
    tp: number;
    fp: number;
    tn: number;
    fn: number;
    total_positives: number;
    total_negatives: number;
    precision: number;
    recall: number;
    f1_score: number;
    false_positive_rate: number;
    top_k_recall: Record<string, number>;
  };
  category_breakdown: CategoryPerformanceItem[];
  yield_curve: any[];
  yield_summary: string;
}

export interface FinalProtocolReport {
  protocol_version: string;
  validation_timestamp: string;
  ruleset_version: string;
  ruleset_id: string;
  held_out_ratio_percentage: number;
  mandatory_categories_verified: string[];
  tuning_split: ProtocolSplitReport;
  held_out_split: ProtocolSplitReport;
  generalization_delta: {
    held_out_ratio_percentage: number;
    meets_min_20pct_held_out_requirement: boolean;
    tuning_recall: number;
    held_out_recall: number;
    recall_delta: number;
    tuning_precision: number;
    held_out_precision: number;
    precision_delta: number;
    tuning_f1: number;
    held_out_f1: number;
    f1_delta: number;
    tuning_fpr: number;
    held_out_fpr: number;
    fpr_delta: number;
    generalization_demonstrated: boolean;
  };
  configuration_path: string;
}

export interface YieldStep {
  rank: number;
  finding_id: string;
  cse_name: string;
  finding_type: string;
  priority_score: number;
  priority_label: string;
  is_true_positive: boolean;
  cumulative_true_positives: number;
  cumulative_false_positives: number;
  precision_at_k: number;
  recall_at_k: number;
  yield_percentage: number;
  assisted_time_minutes: number;
  baseline_equivalent_time_minutes: number;
}

export interface SplitEfficiencyResult {
  split_name: string;
  seed: number;
  total_scenarios: number;
  total_raw_records: number;
  total_raw_cases: number;
  total_true_weaknesses: number;
  total_findings_generated: number;
  baseline_inspection_minutes_per_case: number;
  total_baseline_effort_hours: number;
  baseline_expected_cases_to_first_useful: number;
  baseline_expected_minutes_to_first_useful: number;
  baseline_cases_for_100pct_recall: number;
  baseline_time_for_100pct_recall_hours: number;
  assisted_inspection_minutes_per_finding: number;
  findings_reviewed_for_100pct_recall: number;
  assisted_minutes_to_first_useful: number;
  assisted_time_for_100pct_recall_minutes: number;
  assisted_time_for_100pct_recall_hours: number;
  workload_effort_reduction_percentage: number;
  efficiency_multiplier_speedup: number;
  true_positives: number;
  false_positives: number;
  false_negatives: number;
  precision: number;
  recall: number;
  f1_score: number;
  recall_at_1: number;
  recall_at_3: number;
  recall_at_5: number;
  recall_at_10: number;
  ttuf_first_useful_minutes: number;
  mean_time_to_useful_finding_minutes: number;
  time_to_100pct_recall_minutes: number;
  yield_curve: YieldStep[];
  yield_summary: string;
}

export interface ReviewEfficiencyReport {
  evaluation_timestamp: string;
  ruleset_version: string;
  ruleset_id: string;
  app_version: string;
  methodology: string;
  tuning_split: SplitEfficiencyResult;
  held_out_split: SplitEfficiencyResult;
  cross_split_summary: {
    average_workload_reduction_percentage: number;
    average_efficiency_multiplier_speedup: number;
    tuning_recall: number;
    held_out_recall: number;
    tuning_top5_recall: number;
    held_out_top5_recall: number;
    air_gapped_deterministic: boolean;
    llm_dependency: boolean;
  };
}

export interface ValidationResponse {
  status: string;
  methodology: string;
  disclosure: string;
  tuning_split: ValidationSplitResult;
  held_out_split: ValidationSplitResult;
  review_efficiency?: ReviewEfficiencyReport;
  final_protocol?: FinalProtocolReport;
}

export interface ValidationMetricsResponse {
  tp: number;
  fp: number;
  tn: number;
  fn: number;
  precision: number;
  recall: number;
  f1_score: number;
  fpr: number;
  precision_ci: string | null;
  recall_ci: string | null;
}

export interface RankingMetricsResponse {
  recall_at_1: number;
  recall_at_3: number;
  recall_at_5: number;
}

export interface ThresholdSensitivityResponse {
  threshold: number;
  precision: number;
  recall: number;
  f1: number;
  fpr: number;
}

export interface WeightSensitivityResponse {
  weight: string;
  original: number;
  perturbed: number;
  f1: number;
  delta_f1: number;
  recall_at_1: number;
  recall_at_3: number;
  recall_at_5: number;
  delta_recall_at_5: number;
}

/** Current authoritative robust synthetic-validation API response. */
export interface ValidationProtocolResponse {
  protocol_version: string;
  limitation_notice: string;
  total_scenarios: number;
  tuning_scenarios: number;
  held_out_scenarios: number;
  held_out_ratio: number;
  hard_negative_count: number;
  hard_negative_fp_count: number;
  hard_negative_tn_count: number;
  tuning_metrics: ValidationMetricsResponse;
  held_out_metrics: ValidationMetricsResponse;
  tuning_ranking: RankingMetricsResponse;
  held_out_ranking: RankingMetricsResponse;
  threshold_sensitivity: ThresholdSensitivityResponse[];
  weight_sensitivity: WeightSensitivityResponse[];
}

export interface AuditEventItem {
  audit_event_id: string;
  user_id: string;
  username: string;
  action: string;
  target_type: string;
  target_id: string | null;
  occurred_at: string;
  details: Record<string, any>;
}

export interface DatasetVersionItem {
  dataset_version_id: string;
  version_number: number;
  source_file_ref: string;
  import_time: string;
  row_count: number;
  data_quality_score: number | null;
  data_quality_breakdown?: DataQualityBreakdown;
  provenance?: {
    file_format?: string;
    sha256_hash?: string;
    accepted_rows?: number;
    rejected_rows?: number;
    rejection_reasons?: string[];
  };
}

export interface DatasetItem {
  dataset_id: string;
  name: string;
  description: string;
  created_at: string;
  version_count: number;
  versions: DatasetVersionItem[];
}

export interface StabilityResponse {
  dataset_version_id: string;
  analysis_run_id: string | null;
  baseline_ruleset_version: string;
  baseline_weights: Record<string, number>;
  population_size: number;
  optimizer_seed: number;
  computed_at: string;
  results: Array<{
    configuration: {
      name: string;
      magnitude: number;
      weights: Record<string, number>;
    };
    score_mae: number;
    score_max_delta: number;
    rank_metrics: {
      spearman_rho: number;
      mean_displacement: number;
      max_displacement: number;
      inversions: number;
    };
    review_set_metrics: Record<string, {
      budget_k: number;
      intersection_size: number;
      union_size: number;
      jaccard_similarity: number;
      overlap_percentage: number;
      entrant_count: number;
      exit_count: number;
      explanations: string[];
    }>;
    threshold_crossings: {
      high_tier_crossings_out: number;
      high_tier_crossings_in: number;
    };
  }>;
}

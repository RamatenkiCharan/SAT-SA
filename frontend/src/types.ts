export type Severity = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "INFO";

export type FindingType =
  | "FAST_CLOSURE"
  | "ESCALATION_GAP"
  | "REPEATED_UNRESOLVED_ALERTS"
  | "COVERAGE_GAP";

export type ReviewDecisionState =
  | "CONFIRMED"
  | "FALSE_POSITIVE"
  | "NEEDS_INVESTIGATION"
  | "INSUFFICIENT_EVIDENCE";

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
  priority_score: number;
  priority_label: "HIGH" | "MEDIUM" | "LOW";
  evidentiary_confidence: number;
  data_quality_score: number;
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
  opened_at: string;
  closed_at: string | null;
  severity: Severity;
  outcome: string | null;
}

export interface EvidenceInvestigation {
  investigation_id: string;
  analyst_id: string | null;
  evidence_count: number;
  started_at: string;
  ended_at: string | null;
  disposition: string | null;
}

export interface EvidenceEscalation {
  escalation_id: string;
  case_id: string;
  escalated_at: string;
  level: string;
  target: string;
}

export interface EvidenceAction {
  action_id: string;
  action_type: string;
  performed_at: string;
  outcome: string | null;
}

export interface EvidenceClosure {
  closure_id: string;
  closed_at: string;
  reason: string;
  reviewer: string | null;
}

export interface EvidenceAsset {
  asset_id: string;
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
  alerts: EvidenceAlert[];
  cases: EvidenceCase[];
  investigations: EvidenceInvestigation[];
  escalations: EvidenceEscalation[];
  actions: EvidenceAction[];
  closures: EvidenceClosure[];
  assets: EvidenceAsset[];
}

export interface FindingDetail extends Finding {
  explanation: {
    title: string;
    priority_label: string;
    priority_score: number;
    headline: string;
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
}

export interface CSEBenchmarkMetric {
  cse_id: string;
  cse_name: string;
  sector: string;
  scale: string;
  total_alerts: number;
  critical_alerts_count: number;
  median_critical_closure_minutes: number;
  median_evidence_count: number;
  critical_escalation_ratio: number;
  repeat_alert_rate: number;
  self_reported_sla_compliance: number;
}

export interface PeerCohort {
  peer_id: string;
  sector: string;
  scale: string;
  group_size: number;
  is_fallback_global: boolean;
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
  true_positives: number;
  false_positives: number;
  false_negatives: number;
  precision: number;
  recall: number;
  f1_score: number;
  top_k_recall: number;
  yield_summary: string;
  yield_curve: YieldCurvePoint[];
}

export interface ValidationResponse {
  status: string;
  methodology: string;
  disclosure: string;
  tuning_split: ValidationSplitResult;
  held_out_split: ValidationSplitResult;
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
}

export interface DatasetItem {
  dataset_id: string;
  name: string;
  description: string;
  created_at: string;
  version_count: number;
  versions: DatasetVersionItem[];
}

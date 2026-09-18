import type {
  AuditEventItem,
  DatasetItem,
  Finding,
  FindingDetail,
  PeerCohort,
  CSEBenchmarkMetric,
  ReviewDecisionState,
  ValidationProtocolResponse,
} from "./types";

const API_BASE = import.meta.env.VITE_API_URL || "/api";

// Keep the bearer token only for the lifetime of the current page.  Persisting it
// in localStorage turns any future XSS into a long-lived session compromise.
let _authToken: string | null = null;

export function setAuthToken(token: string | null) {
  _authToken = token;
}

export function getAuthToken(): string | null {
  return _authToken;
}

export async function login(username: string, password: string): Promise<any> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Login failed" }));
    throw new Error(err.detail || "Authentication failed");
  }
  const data = await res.json();
  if (data.access_token) {
    setAuthToken(data.access_token);
  }
  return data;
}

export async function fetchCurrentUser(): Promise<any> {
  return authFetch(`${API_BASE}/auth/me`);
}

async function authFetch(url: string, options: RequestInit = {}): Promise<any> {
  if (!_authToken) throw new Error("Authentication is required. Please sign in.");
  const headers = new Headers(options.headers || {});
  if (_authToken && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${_authToken}`);
  }
  let res = await fetch(url, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Request failed with status ${res.status}`);
  }
  return res.json();
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isValidationMetricsResponse(value: unknown): boolean {
  if (!isRecord(value)) return false;
  return ["tp", "fp", "tn", "fn", "precision", "recall", "f1_score", "fpr"].every(
    (field) => isNumber(value[field]),
  ) && (value.precision_ci === null || typeof value.precision_ci === "string")
    && (value.recall_ci === null || typeof value.recall_ci === "string");
}

function isRankingMetricsResponse(value: unknown): boolean {
  return isRecord(value)
    && isNumber(value.recall_at_1)
    && isNumber(value.recall_at_3)
    && isNumber(value.recall_at_5);
}

function isThresholdSensitivityResponse(value: unknown): boolean {
  return isRecord(value)
    && ["threshold", "precision", "recall", "f1", "fpr"].every((field) => isNumber(value[field]));
}

function isWeightSensitivityResponse(value: unknown): boolean {
  return isRecord(value)
    && typeof value.weight === "string"
    && [
      "original",
      "perturbed",
      "f1",
      "delta_f1",
      "recall_at_1",
      "recall_at_3",
      "recall_at_5",
      "delta_recall_at_5",
    ].every((field) => isNumber(value[field]));
}

function isValidationProtocolResponse(value: unknown): value is ValidationProtocolResponse {
  if (!isRecord(value)) return false;
  return typeof value.protocol_version === "string"
    && typeof value.limitation_notice === "string"
    && [
      "total_scenarios",
      "tuning_scenarios",
      "held_out_scenarios",
      "held_out_ratio",
      "hard_negative_count",
      "hard_negative_fp_count",
      "hard_negative_tn_count",
    ].every((field) => isNumber(value[field]))
    && isValidationMetricsResponse(value.tuning_metrics)
    && isValidationMetricsResponse(value.held_out_metrics)
    && isRankingMetricsResponse(value.tuning_ranking)
    && isRankingMetricsResponse(value.held_out_ranking)
    && Array.isArray(value.threshold_sensitivity)
    && value.threshold_sensitivity.every(isThresholdSensitivityResponse)
    && Array.isArray(value.weight_sensitivity)
    && value.weight_sensitivity.every(isWeightSensitivityResponse);
}


export async function fetchHealth(): Promise<any> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error("Backend health check failed");
  return res.json();
}

export async function fetchDatasets(): Promise<{
  active_version_id: string | null;
  datasets: DatasetItem[];
}> {
  return authFetch(`${API_BASE}/datasets`);
}

export async function loadDemoDataset(
  scenarioType: "critical_infrastructure" | "held_out_test"
): Promise<any> {
  return authFetch(`${API_BASE}/datasets/load-demo`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario_type: scenarioType }),
  });
}

export async function uploadDatasetFile(file: File): Promise<any> {
  const formData = new FormData();
  formData.append("file", file);
  return authFetch(`${API_BASE}/datasets/upload`, {
    method: "POST",
    body: formData,
  });
}

export async function switchDatasetVersion(versionId: string): Promise<any> {
  return authFetch(`${API_BASE}/datasets/switch-version`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset_version_id: versionId }),
  });
}

export async function fetchFindings(params?: {
  sector?: string;
  finding_type?: string;
  min_priority?: number;
  dataset_version_id?: string;
}): Promise<{
  count: number;
  dataset_version_id: string | null;
  findings: Finding[];
}> {
  const query = new URLSearchParams();
  if (params?.sector) query.set("sector", params.sector);
  if (params?.finding_type) query.set("finding_type", params.finding_type);
  if (params?.min_priority) query.set("min_priority", params.min_priority.toString());
  if (params?.dataset_version_id) query.set("dataset_version_id", params.dataset_version_id);

  return authFetch(`${API_BASE}/findings?${query.toString()}`);
}

export async function fetchFindingDetail(findingId: string): Promise<FindingDetail> {
  return authFetch(`${API_BASE}/findings/${findingId}`);
}

export async function submitReviewDecision(
  findingId: string,
  decision: ReviewDecisionState,
  notes?: string
): Promise<any> {
  return authFetch(`${API_BASE}/reviews`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      finding_id: findingId,
      decision,
      notes: notes || "",
    }),
  });
}

export async function sendEvidenceMessage(
  findingId: string,
  message: string,
  evidenceId?: string,
  recipientRole?: string
): Promise<any> {
  return authFetch(`${API_BASE}/findings/${findingId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      finding_id: findingId,
      evidence_id: evidenceId || null,
      message,
      recipient_role: recipientRole || "SOC Leadership / Tier-2 Lead",
    }),
  });
}

export async function fetchEvidenceMessages(findingId: string): Promise<any[]> {
  return authFetch(`${API_BASE}/findings/${findingId}/messages`);
}


export async function fetchBenchmarks(versionId?: string): Promise<{
  dataset_version_id: string;
  entities: CSEBenchmarkMetric[];
  cohorts: PeerCohort[];
}> {
  const query = versionId ? `?dataset_version_id=${versionId}` : "";
  return authFetch(`${API_BASE}/benchmarks${query}`);
}

export async function fetchValidationResults(): Promise<ValidationProtocolResponse> {
  const response: unknown = await authFetch(`${API_BASE}/validation`);
  if (!isValidationProtocolResponse(response)) {
    throw new Error("Validation API returned an invalid protocol response.");
  }
  return response;
}

export async function fetchAuditLogs(): Promise<AuditEventItem[]> {
  return authFetch(`${API_BASE}/audit`);
}

export async function fetchExportReport(versionId?: string): Promise<any> {
  const query = versionId ? `?dataset_version_id=${versionId}` : "";
  return authFetch(`${API_BASE}/export/report${query}`);
}

export async function fetchReviewBudget(params: {
  budget: number;
  dataset_version_id?: string;
  control_fraction?: number;
  seed?: number;
}): Promise<any> {
  return authFetch(`${API_BASE}/review-budget/optimize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
}

export async function fetchStabilityAnalysis(
  dataset_version_id?: string,
  magnitudes: number[] = [0.05, 0.10, 0.15, 0.20],
  budgets: number[] = [1, 5, 10, 25]
): Promise<any> {
  return authFetch(`${API_BASE}/validation/stability`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      dataset_version_id: dataset_version_id || null,
      magnitudes,
      budgets,
    }),
  });
}

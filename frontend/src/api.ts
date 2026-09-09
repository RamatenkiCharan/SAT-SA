import type {
  AuditEventItem,
  DatasetItem,
  Finding,
  FindingDetail,
  PeerCohort,
  CSEBenchmarkMetric,
  ReviewDecisionState,
  ValidationResponse,
} from "./types";

const API_BASE = import.meta.env.VITE_API_URL || "/api";

export async function fetchHealth(): Promise<any> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error("Backend health check failed");
  return res.json();
}

export async function fetchDatasets(): Promise<{
  active_version_id: string | null;
  datasets: DatasetItem[];
}> {
  const res = await fetch(`${API_BASE}/datasets`);
  if (!res.ok) throw new Error("Failed to fetch datasets");
  return res.json();
}

export async function loadDemoDataset(
  scenarioType: "critical_infrastructure" | "held_out_test"
): Promise<any> {
  const res = await fetch(`${API_BASE}/datasets/load-demo`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario_type: scenarioType }),
  });
  if (!res.ok) throw new Error("Failed to load demo dataset");
  return res.json();
}

export async function uploadDatasetFile(file: File): Promise<any> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/datasets/upload`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error("Failed to upload dataset file");
  return res.json();
}

export async function switchDatasetVersion(versionId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/datasets/switch-version`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset_version_id: versionId }),
  });
  if (!res.ok) throw new Error("Failed to switch dataset version");
  return res.json();
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

  const res = await fetch(`${API_BASE}/findings?${query.toString()}`);
  if (!res.ok) throw new Error("Failed to fetch findings");
  return res.json();
}

export async function fetchFindingDetail(findingId: string): Promise<FindingDetail> {
  const res = await fetch(`${API_BASE}/findings/${findingId}`);
  if (!res.ok) throw new Error("Failed to fetch finding details");
  return res.json();
}

export async function submitReviewDecision(
  findingId: string,
  decision: ReviewDecisionState,
  notes?: string
): Promise<any> {
  const res = await fetch(`${API_BASE}/reviews`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      finding_id: findingId,
      decision,
      notes: notes || "",
    }),
  });
  if (!res.ok) throw new Error("Failed to submit review decision");
  return res.json();
}

export async function fetchBenchmarks(versionId?: string): Promise<{
  dataset_version_id: string;
  entities: CSEBenchmarkMetric[];
  cohorts: PeerCohort[];
}> {
  const query = versionId ? `?dataset_version_id=${versionId}` : "";
  const res = await fetch(`${API_BASE}/benchmarks${query}`);
  if (!res.ok) throw new Error("Failed to fetch benchmarks");
  return res.json();
}

export async function fetchValidationResults(): Promise<ValidationResponse> {
  const res = await fetch(`${API_BASE}/validation`);
  if (!res.ok) throw new Error("Failed to fetch validation results");
  return res.json();
}

export async function fetchAuditLogs(): Promise<AuditEventItem[]> {
  const res = await fetch(`${API_BASE}/audit`);
  if (!res.ok) throw new Error("Failed to fetch audit logs");
  return res.json();
}

export async function fetchExportReport(versionId?: string): Promise<any> {
  const query = versionId ? `?dataset_version_id=${versionId}` : "";
  const res = await fetch(`${API_BASE}/export/report${query}`);
  if (!res.ok) throw new Error("Failed to generate export report");
  return res.json();
}

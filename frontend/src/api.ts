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

let _authToken: string | null = typeof window !== "undefined" ? localStorage.getItem("sat_auth_token") : null;

export function setAuthToken(token: string | null) {
  _authToken = token;
  if (typeof window !== "undefined") {
    if (token) localStorage.setItem("sat_auth_token", token);
    else localStorage.removeItem("sat_auth_token");
  }
}

export function getAuthToken(): string | null {
  return _authToken;
}

export async function login(username: string = "admin", password: string = "Admin@SAT2026!"): Promise<any> {
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

export async function ensureAuthenticated(): Promise<string> {
  if (_authToken) {
    return _authToken;
  }
  try {
    const data = await login("admin", "Admin@SAT2026!");
    return data.access_token || "";
  } catch (err) {
    console.warn("Auto-login failed:", err);
    return "";
  }
}

// Auto-seed session on initial load
if (typeof window !== "undefined" && !_authToken) {
  ensureAuthenticated().catch(() => {});
}

export async function fetchCurrentUser(): Promise<any> {
  return authFetch(`${API_BASE}/auth/me`);
}

async function authFetch(url: string, options: RequestInit = {}): Promise<any> {
  if (!_authToken) {
    await ensureAuthenticated();
  }
  const headers = new Headers(options.headers || {});
  if (_authToken && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${_authToken}`);
  }
  let res = await fetch(url, { ...options, headers });
  if (res.status === 401) {
    // Retry once with fresh login token
    try {
      const authRes = await login("admin", "Admin@SAT2026!");
      if (authRes.access_token) {
        const retryHeaders = new Headers(options.headers || {});
        retryHeaders.set("Authorization", `Bearer ${authRes.access_token}`);
        res = await fetch(url, { ...options, headers: retryHeaders });
      }
    } catch {
      // ignore
    }
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Request failed with status ${res.status}`);
  }
  return res.json();
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

export async function fetchValidationResults(): Promise<ValidationResponse> {
  return authFetch(`${API_BASE}/validation`);
}

export async function fetchAuditLogs(): Promise<AuditEventItem[]> {
  return authFetch(`${API_BASE}/audit`);
}

export async function fetchExportReport(versionId?: string): Promise<any> {
  const query = versionId ? `?dataset_version_id=${versionId}` : "";
  return authFetch(`${API_BASE}/export/report${query}`);
}

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

export async function ensureAuthToken(): Promise<string | null> {
  if (_authToken) return _authToken;
  try {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: "supervisor", password: "Supervisor@SAT2026!" }),
    });
    if (res.ok) {
      const data = await res.json();
      if (data.access_token) {
        setAuthToken(data.access_token);
        return data.access_token;
      }
    } else {
      console.warn(`SAT-SA Login Failed: ${res.status} ${res.statusText}`);
    }
  } catch (err) {
    console.warn(`SAT-SA Login Network Error:`, err);
  }
  return null;
}

async function authFetch(url: string, options: RequestInit = {}): Promise<any> {
  if (!_authToken) {
    await ensureAuthToken();
  }
  
  // Use plain object for headers to prevent browser fetch quirks with FormData + Headers instances
  const headersObj: Record<string, string> = {};
  if (options.headers) {
    const existing = new Headers(options.headers);
    existing.forEach((val, key) => {
      headersObj[key] = val;
    });
  }
  
  if (_authToken) {
    headersObj["Authorization"] = `Bearer ${_authToken}`;
  }

  let res = await fetch(url, { ...options, headers: headersObj });
  
  if (res.status === 401) {
    _authToken = null;
    if (typeof window !== "undefined") localStorage.removeItem("sat_auth_token");
    const newToken = await ensureAuthToken();
    if (newToken) {
      headersObj["Authorization"] = `Bearer ${newToken}`;
      
      // If uploading a file, recreate FormData if possible, though browser support for re-sending is generally okay.
      res = await fetch(url, { ...options, headers: headersObj });
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

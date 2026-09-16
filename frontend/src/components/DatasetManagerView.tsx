import React, { useState } from "react";
import { Upload, Zap, Database, FileText, CheckCircle2, AlertCircle, RefreshCw, Layers } from "lucide-react";
import type { DatasetItem } from "../types";
import { loadDemoDataset, switchDatasetVersion, uploadDatasetFile } from "../api";

interface DatasetManagerViewProps {
  datasets: DatasetItem[];
  activeVersionId: string | null;
  onRefresh: () => void;
}

export const DatasetManagerView: React.FC<DatasetManagerViewProps> = ({
  datasets,
  activeVersionId,
  onRefresh,
}) => {
  const [loadingDemo, setLoadingDemo] = useState<boolean>(false);
  const [uploading, setUploading] = useState<boolean>(false);
  const [activeScenario, setActiveScenario] = useState<string | null>(null);

  const handleLoadDemo = async (scenario: "critical_infrastructure" | "held_out_test") => {
    setLoadingDemo(true);
    setActiveScenario(scenario);
    try {
      await loadDemoDataset(scenario);
      onRefresh();
    } catch (err) {
      alert("Failed to load demo dataset: " + String(err));
    } finally {
      setLoadingDemo(false);
      setActiveScenario(null);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    try {
      await uploadDatasetFile(file);
      onRefresh();
    } catch (err) {
      alert("Failed to upload dataset: " + String(err));
    } finally {
      setUploading(false);
    }
  };

  const handleSwitchVersion = async (versionId: string) => {
    try {
      await switchDatasetVersion(versionId);
      onRefresh();
    } catch (err) {
      alert("Failed to switch version: " + String(err));
    }
  };

  const handleDownloadSampleCsv = () => {
    const sampleCsv = `alert_id,event_time,severity,alert_category,source,status,asset_id\nalt_001,2026-01-15T08:30:00Z,CRITICAL,Unauthorized Access,Firewall,OPEN,ast_grid_01\nalt_002,2026-01-15T09:15:00Z,HIGH,Malware Outbreak,EDR_Sensor,INVESTIGATING,ast_grid_02\nalt_003,2026-01-15T10:00:00Z,MEDIUM,Brute Force Attempt,Auth_Gateway,CLOSED,ast_grid_03\nalt_004,2026-01-15T11:20:00Z,LOW,Port Scan Detected,NIDS,CLOSED,ast_grid_04\nalt_005,2026-01-15T12:00:00Z,HIGH,SCADA Telemetry Dropout,Substation_Mon,ESCALATED,ast_grid_05`;
    const blob = new Blob([sampleCsv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", "sat_sa_sample_evidence_template.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="page-fade-enter" style={{ display: "flex", flexDirection: "column", gap: "1.75rem" }}>
      
      {/* Header Banner */}
      <div
        className="glass-card hud-corner"
        style={{
          padding: "2rem",
          background: "linear-gradient(135deg, rgba(14, 21, 38, 0.95) 0%, rgba(8, 13, 26, 0.95) 100%)",
          border: "1px solid rgba(0, 240, 255, 0.2)",
        }}
      >
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: "1rem" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.4rem" }}>
              <span className="badge badge-cyan">
                <Database size={13} /> PROVENANCE &amp; INGESTION CONTROL
              </span>
              <span className="badge badge-purple">
                <Layers size={13} /> IMMUTABILITY PRINCIPLE (§52)
              </span>
            </div>
            <h2 style={{ fontSize: "1.45rem", color: "#fff", fontWeight: 700 }}>
              SOC Operational Evidence Ingestion &amp; Version Management
            </h2>
            <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginTop: "0.25rem", maxWidth: "800px" }}>
              Every imported telemetry file is canonicalized, cryptographically fingerprinted (SHA-256), and assigned an immutable dataset version ID for full supervisory reproducibility.
            </p>
          </div>

          <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
            <button onClick={onRefresh} className="btn-secondary" style={{ fontSize: "0.85rem" }}>
              <RefreshCw size={14} /> Refresh Versions
            </button>
          </div>
        </div>
      </div>

      {/* Quick Action Loaders */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))", gap: "1.25rem" }}>
        
        {/* Synthetic Demo Loader */}
        <div className="glass-card hud-corner" style={{ padding: "1.75rem", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" }}>
              <Zap size={20} color="var(--accent-cyan)" />
              <h3 style={{ fontSize: "1.1rem", color: "#fff", fontWeight: 700 }}>Pre-Bundled Multi-CSE Benchmark Packs</h3>
            </div>
            <p style={{ fontSize: "0.84rem", color: "var(--text-secondary)", marginBottom: "1.5rem", lineHeight: 1.5 }}>
              Instantly load synthetic multi-sector operational evidence across Power Grid, Banking, Transit, Telecom, and Healthcare containing realistic Goodhart's Law execution gaps and empirical review scenarios.
            </p>
          </div>

          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem" }}>
            <button
              onClick={() => handleLoadDemo("critical_infrastructure")}
              disabled={loadingDemo}
              className="btn-primary"
              style={{ fontSize: "0.82rem", flex: "1 1 200px", justifyContent: "center" }}
              id="load-default-demo-pack-btn"
            >
              {loadingDemo && activeScenario === "critical_infrastructure" ? (
                <>
                  <span className="pulse-live" /> Ingesting Benchmark...
                </>
              ) : (
                <>
                  <Zap size={15} /> Load Default Critical Infrastructure Pack
                </>
              )}
            </button>
            <button
              onClick={() => handleLoadDemo("held_out_test")}
              disabled={loadingDemo}
              className="btn-secondary"
              style={{ fontSize: "0.82rem", flex: "1 1 160px", justifyContent: "center" }}
              id="load-held-out-test-pack-btn"
            >
              {loadingDemo && activeScenario === "held_out_test" ? (
                <>
                  <span className="pulse-live" /> Ingesting Held-Out Split...
                </>
              ) : (
                <>
                  <Layers size={15} /> Load Held-Out Test Split
                </>
              )}
            </button>
          </div>
        </div>

        {/* Custom File Uploader */}
        <div className="glass-card hud-corner" style={{ padding: "1.75rem", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" }}>
              <Upload size={20} color="var(--accent-purple)" />
              <h3 style={{ fontSize: "1.1rem", color: "#fff", fontWeight: 700 }}>Upload Custom SOC Evidence</h3>
            </div>
            <p style={{ fontSize: "0.84rem", color: "var(--text-secondary)", marginBottom: "1.25rem", lineHeight: 1.5 }}>
              Ingest raw SOC operational exports (JSON / CSV). Schema validation, entity canonicalization, and 4-dimension Data Trust scoring are computed automatically.
            </p>
          </div>

          <label
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: "0.5rem",
              border: "2px dashed var(--border-cyber)",
              borderRadius: "var(--radius-md)",
              padding: "1.25rem",
              textAlign: "center",
              cursor: "pointer",
              background: "rgba(15, 23, 42, 0.5)",
              transition: "all 0.2s ease",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = "var(--accent-cyan)";
              e.currentTarget.style.background = "rgba(0, 240, 255, 0.04)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = "var(--border-cyber)";
              e.currentTarget.style.background = "rgba(15, 23, 42, 0.5)";
            }}
          >
            <Upload size={22} color="var(--accent-cyan)" />
            <span style={{ fontSize: "0.84rem", color: "var(--text-primary)", fontWeight: 600 }}>
              {uploading ? "Parsing, Canonicalizing & Scoring..." : "Select or drag SOC CSV/JSON evidence file"}
            </span>
            <span style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>
              Supported formats: JSON alerts/cases export, standardized CSV (§3.1)
            </span>
            <input
              type="file"
              accept=".json,.csv"
              onChange={handleFileUpload}
              style={{ display: "none" }}
              id="upload-dataset-input"
            />
          </label>

          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "0.6rem" }}>
            <button
              onClick={handleDownloadSampleCsv}
              className="btn-secondary"
              style={{ fontSize: "0.76rem", padding: "0.35rem 0.75rem", display: "inline-flex", alignItems: "center", gap: "0.35rem" }}
              id="download-sample-csv-btn"
            >
              <FileText size={13} color="var(--accent-cyan)" /> Download Standard Sample CSV Template
            </button>
          </div>
        </div>

      </div>

      {/* Dataset Version History Table */}
      <div className="glass-card" style={{ padding: "1.75rem" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1.25rem", flexWrap: "wrap", gap: "0.5rem" }}>
          <div>
            <h3 style={{ fontSize: "1.1rem", color: "#fff", fontWeight: 700 }}>
              Dataset Version Ledger &amp; Provenance History
            </h3>
            <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "0.15rem" }}>
              Immutable records of all ingested evidence versions with cryptographic integrity hashes.
            </p>
          </div>
          <span className="badge badge-cyan" style={{ fontSize: "0.75rem" }}>
            {datasets.reduce((acc, d) => acc + (d.versions?.length || 0), 0)} Registered Versions
          </span>
        </div>

        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid rgba(0, 240, 255, 0.2)", color: "var(--text-muted)", textAlign: "left" }}>
                <th style={{ padding: "0.85rem 0.75rem" }}>Dataset Name</th>
                <th style={{ padding: "0.85rem 0.75rem" }}>Format</th>
                <th style={{ padding: "0.85rem 0.75rem" }}>Version ID / Cryptographic Hash</th>
                <th style={{ padding: "0.85rem 0.75rem" }}>Telemetry Records</th>
                <th style={{ padding: "0.85rem 0.75rem" }}>Data Trust Score</th>
                <th style={{ padding: "0.85rem 0.75rem" }}>Import Timestamp</th>
                <th style={{ padding: "0.85rem 0.75rem" }}>Supervisory Status</th>
                <th style={{ padding: "0.85rem 0.75rem", textAlign: "right" }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {datasets.flatMap((ds) =>
                (ds.versions || []).map((v) => {
                  const isActive = v.dataset_version_id === activeVersionId;
                  const format = v.provenance?.file_format?.toUpperCase() || (v.source_file_ref.startsWith("synthetic") ? "SYNTHETIC" : "JSON");
                  const hashSnippet = v.provenance?.sha256_hash ? v.provenance.sha256_hash.slice(0, 10) : null;
                  return (
                    <tr
                      key={v.dataset_version_id}
                      style={{
                        borderBottom: "1px solid rgba(255, 255, 255, 0.04)",
                        background: isActive ? "rgba(0, 240, 255, 0.05)" : "transparent",
                        transition: "background 0.15s ease",
                      }}
                      onMouseEnter={(e) => {
                        if (!isActive) e.currentTarget.style.background = "rgba(255, 255, 255, 0.02)";
                      }}
                      onMouseLeave={(e) => {
                        if (!isActive) e.currentTarget.style.background = "transparent";
                      }}
                    >
                      <td style={{ padding: "0.85rem 0.75rem", fontWeight: 600, color: "#fff" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                          <FileText size={15} color={isActive ? "var(--accent-cyan)" : "var(--text-muted)"} />
                          <span>{ds.name} (v{v.version_number})</span>
                        </div>
                      </td>
                      <td style={{ padding: "0.85rem 0.75rem" }}>
                        <span
                          className="badge"
                          style={{
                            background: format === "CSV" ? "rgba(16, 185, 129, 0.15)" : format === "JSON" ? "rgba(139, 92, 246, 0.15)" : "rgba(0, 240, 255, 0.12)",
                            color: format === "CSV" ? "#10b981" : format === "JSON" ? "#a78bfa" : "var(--accent-cyan)",
                            fontSize: "0.68rem",
                            fontWeight: 700,
                          }}
                        >
                          {format}
                        </span>
                      </td>
                      <td style={{ padding: "0.85rem 0.75rem", fontFamily: "var(--font-mono)", fontSize: "0.75rem" }}>
                        <div style={{ color: "var(--text-primary)", fontWeight: 600 }}>{v.dataset_version_id.slice(0, 12)}...</div>
                        {hashSnippet && (
                          <div className="crypto-hash-pill" style={{ marginTop: "0.25rem", width: "fit-content" }}>
                            sha256:{hashSnippet}
                          </div>
                        )}
                      </td>
                      <td style={{ padding: "0.85rem 0.75rem" }}>
                        <div style={{ fontWeight: 600, color: "#fff" }}>{v.row_count.toLocaleString()} alerts</div>
                        {v.provenance && (v.provenance.rejected_rows ?? 0) > 0 ? (
                          <div style={{ fontSize: "0.7rem", color: "var(--accent-crimson)", display: "flex", alignItems: "center", gap: "0.2rem", marginTop: "0.15rem" }}>
                            <AlertCircle size={11} /> {v.provenance.rejected_rows} rejected
                          </div>
                        ) : (
                          <div style={{ fontSize: "0.7rem", color: "var(--accent-emerald)", display: "flex", alignItems: "center", gap: "0.2rem", marginTop: "0.15rem" }}>
                            <CheckCircle2 size={11} /> Clean schema
                          </div>
                        )}
                      </td>
                      <td style={{ padding: "0.85rem 0.75rem" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.45rem" }}>
                          <span style={{ color: "var(--accent-cyan)", fontWeight: 800, fontFamily: "var(--font-mono)" }}>
                            {v.data_quality_score ? `${(v.data_quality_score * 100).toFixed(1)}%` : "N/A"}
                          </span>
                          {v.data_quality_score !== undefined && (
                            <div className="progress-container" style={{ width: "45px", height: "4px" }}>
                              <div
                                className="progress-bar"
                                style={{
                                  width: `${(v.data_quality_score || 0) * 100}%`,
                                  background: (v.data_quality_score || 0) > 0.8 ? "var(--accent-emerald)" : "var(--accent-amber)",
                                }}
                              />
                            </div>
                          )}
                        </div>
                      </td>
                      <td style={{ padding: "0.85rem 0.75rem", color: "var(--text-muted)", fontSize: "0.75rem" }}>
                        {new Date(v.import_time).toLocaleString()}
                      </td>
                      <td style={{ padding: "0.85rem 0.75rem" }}>
                        {isActive ? (
                          <span className="badge badge-cyan" style={{ fontSize: "0.68rem" }}>
                            <span className="pulse-live" /> ACTIVE VERSION
                          </span>
                        ) : (
                          <span className="badge" style={{ background: "rgba(255,255,255,0.06)", color: "var(--text-muted)", fontSize: "0.68rem" }}>
                            ARCHIVED
                          </span>
                        )}
                      </td>
                      <td style={{ padding: "0.85rem 0.75rem", textAlign: "right" }}>
                        {!isActive ? (
                          <button
                            onClick={() => handleSwitchVersion(v.dataset_version_id)}
                            className="btn-secondary"
                            style={{ padding: "0.35rem 0.75rem", fontSize: "0.74rem" }}
                            id={`activate-version-btn-${v.dataset_version_id.slice(0, 8)}`}
                          >
                            Set Active
                          </button>
                        ) : (
                          <span style={{ fontSize: "0.72rem", color: "var(--accent-cyan)", fontWeight: 600 }}>
                            Current Scope
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  );
};


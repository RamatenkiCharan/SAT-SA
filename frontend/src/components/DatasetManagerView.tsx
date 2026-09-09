import React, { useState } from "react";
import { Upload, Zap } from "lucide-react";
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

  const handleLoadDemo = async (scenario: "critical_infrastructure" | "held_out_test") => {
    setLoadingDemo(true);
    try {
      await loadDemoDataset(scenario);
      onRefresh();
    } catch (err) {
      alert("Failed to load demo dataset: " + String(err));
    } finally {
      setLoadingDemo(false);
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

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      
      {/* Header */}
      <div className="glass-card" style={{ padding: "1.5rem" }}>
        <h2 style={{ fontSize: "1.25rem", color: "#fff", marginBottom: "0.2rem" }}>
          SOC Operational Evidence Ingestion & Version Management
        </h2>
        <p style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
          Every import creates an immutable, provenance-tracked dataset version (§52 Immutability Principle).
        </p>
      </div>

      {/* Quick Action Loaders */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.25rem" }}>
        
        {/* Synthetic Demo Loader */}
        <div className="glass-card" style={{ padding: "1.5rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" }}>
            <Zap size={20} color="var(--accent-cyan)" />
            <h3 style={{ fontSize: "1.05rem", color: "#fff" }}>Pre-Bundled Multi-CSE Benchmark Packs</h3>
          </div>
          <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", marginBottom: "1.25rem", lineHeight: 1.4 }}>
            Instantly load synthetic multi-sector operational evidence (Power Grid, Banking, Transit, Telecom, Healthcare) containing realistic Goodhart's Law execution gaps.
          </p>

          <div style={{ display: "flex", gap: "0.75rem" }}>
            <button
              onClick={() => handleLoadDemo("critical_infrastructure")}
              disabled={loadingDemo}
              className="btn-primary"
              style={{ fontSize: "0.82rem" }}
            >
              {loadingDemo ? "Ingesting..." : "Load Default Critical Infrastructure Pack"}
            </button>
            <button
              onClick={() => handleLoadDemo("held_out_test")}
              disabled={loadingDemo}
              className="btn-secondary"
              style={{ fontSize: "0.82rem" }}
            >
              Load Held-Out Test Split
            </button>
          </div>
        </div>

        {/* Custom File Uploader */}
        <div className="glass-card" style={{ padding: "1.5rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" }}>
            <Upload size={20} color="var(--accent-purple)" />
            <h3 style={{ fontSize: "1.05rem", color: "#fff" }}>Upload Custom Evidence (JSON / CSV)</h3>
          </div>
          <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", marginBottom: "1rem", lineHeight: 1.4 }}>
            Upload raw SOC operational export files. Schema validation and canonical models will be applied immediately.
          </p>

          <label
            style={{
              display: "block",
              border: "2px dashed rgba(255, 255, 255, 0.15)",
              borderRadius: "var(--radius-md)",
              padding: "1rem",
              textAlign: "center",
              cursor: "pointer",
              background: "rgba(15, 23, 42, 0.4)",
            }}
          >
            <span style={{ fontSize: "0.82rem", color: "var(--accent-cyan)", fontWeight: 600 }}>
              {uploading ? "Parsing & Canonicalizing..." : "Click to select or drop CSV/JSON"}
            </span>
            <input
              type="file"
              accept=".json,.csv"
              onChange={handleFileUpload}
              style={{ display: "none" }}
            />
          </label>
        </div>

      </div>

      {/* Dataset Version History Table */}
      <div className="glass-card" style={{ padding: "1.5rem" }}>
        <h3 style={{ fontSize: "1.05rem", color: "#fff", marginBottom: "1rem" }}>
          Dataset Version Ledger & Provenance History
        </h3>

        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border-subtle)", color: "var(--text-muted)", textAlign: "left" }}>
                <th style={{ padding: "0.75rem" }}>Dataset Name</th>
                <th style={{ padding: "0.75rem" }}>Version ID</th>
                <th style={{ padding: "0.75rem" }}>Alert Records</th>
                <th style={{ padding: "0.75rem" }}>Data Trust Score</th>
                <th style={{ padding: "0.75rem" }}>Import Timestamp</th>
                <th style={{ padding: "0.75rem" }}>Status</th>
                <th style={{ padding: "0.75rem" }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {datasets.flatMap((ds) =>
                ds.versions.map((v) => {
                  const isActive = v.dataset_version_id === activeVersionId;
                  return (
                    <tr
                      key={v.dataset_version_id}
                      style={{
                        borderBottom: "1px solid rgba(255, 255, 255, 0.04)",
                        background: isActive ? "rgba(0, 240, 255, 0.04)" : "transparent",
                      }}
                    >
                      <td style={{ padding: "0.75rem", fontWeight: 600, color: "#fff" }}>
                        {ds.name} (v{v.version_number})
                      </td>
                      <td style={{ padding: "0.75rem", fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>
                        {v.dataset_version_id.slice(0, 8)}...
                      </td>
                      <td style={{ padding: "0.75rem" }}>{v.row_count} alerts</td>
                      <td style={{ padding: "0.75rem", color: "var(--accent-cyan)", fontWeight: 700 }}>
                        {v.data_quality_score ? `${(v.data_quality_score * 100).toFixed(1)}%` : "N/A"}
                      </td>
                      <td style={{ padding: "0.75rem", color: "var(--text-muted)" }}>
                        {new Date(v.import_time).toLocaleString()}
                      </td>
                      <td style={{ padding: "0.75rem" }}>
                        {isActive ? (
                          <span className="badge badge-cyan" style={{ fontSize: "0.68rem" }}>
                            ACTIVE VERSION
                          </span>
                        ) : (
                          <span className="badge" style={{ background: "rgba(255,255,255,0.06)", fontSize: "0.68rem" }}>
                            ARCHIVED
                          </span>
                        )}
                      </td>
                      <td style={{ padding: "0.75rem" }}>
                        {!isActive && (
                          <button
                            onClick={() => handleSwitchVersion(v.dataset_version_id)}
                            className="btn-secondary"
                            style={{ padding: "0.3rem 0.6rem", fontSize: "0.72rem" }}
                          >
                            Set Active
                          </button>
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

import React from "react";
import { Search } from "lucide-react";
import type { Finding } from "../types";

interface NegativeSpaceViewProps {
  findings: Finding[];
  onSelectFinding: (finding: Finding) => void;
}

export const NegativeSpaceView: React.FC<NegativeSpaceViewProps> = ({
  findings,
  onSelectFinding,
}) => {
  const coverageFindings = findings.filter((f) => f.finding_type === "COVERAGE_GAP");

  const monitoredAssets = [
    {
      name: "SCADA Substation Master Node Alpha",
      sector: "Power & Energy",
      criticality: "CRITICAL",
      expected: 40,
      observed: 38,
      status: "HEALTHY_COVERAGE",
      desc: "Continuous SIEM & EDR telemetry stream.",
    },
    {
      name: "High Voltage Transformer Control Bus",
      sector: "Power & Energy",
      criticality: "CRITICAL",
      expected: 45,
      observed: 0,
      status: "BLIND_SPOT_GAP",
      desc: "ZERO security events observed despite active production load (Data quality: 92%).",
    },
    {
      name: "Core Banking Transaction DB Cluster",
      sector: "Financial Services",
      criticality: "CRITICAL",
      expected: 50,
      observed: 48,
      status: "HEALTHY_COVERAGE",
      desc: "Robust audit logging and privilege access telemetry.",
    },
    {
      name: "State Healthcare Records Exchange",
      sector: "Healthcare & Defense",
      criticality: "CRITICAL",
      expected: 40,
      observed: 0,
      status: "BLIND_SPOT_GAP",
      desc: "EHR database completely silent. Gated by healthy data ingestion score.",
    },
    {
      name: "Coastal Water Distribution Station",
      sector: "Power & Energy",
      criticality: "HIGH",
      expected: 40,
      observed: 5,
      status: "DATA_OUTAGE_UNCERTAINTY",
      desc: "Low volume caused by sensor link failure. Correctly classified as data uncertainty.",
    },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      
      {/* Header Info */}
      <div className="glass-card" style={{ padding: "1.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <h2 style={{ fontSize: "1.25rem", color: "#fff" }}>Negative Space & Monitoring Coverage Map</h2>
            <p style={{ fontSize: "0.82rem", color: "var(--text-muted)", marginTop: "0.2rem" }}>
              Detects evidence that <em>should</em> exist under expected operating context but doesn't (FR-041). Gated by Data Trust to distinguish blind spots from data ingestion outages.
            </p>
          </div>
          <span className="badge badge-purple" style={{ fontSize: "0.75rem" }}>
            <Search size={14} /> NEGATIVE-SPACE HYPOTHESIS ENGINE
          </span>
        </div>
      </div>

      {/* Grid of Monitored Assets */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "1.25rem" }}>
        {monitoredAssets.map((asset, i) => {
          const isGap = asset.status === "BLIND_SPOT_GAP";
          const isOutage = asset.status === "DATA_OUTAGE_UNCERTAINTY";
          const ratio = (asset.observed / asset.expected) * 100;

          return (
            <div
              key={i}
              className="glass-card"
              style={{
                padding: "1.25rem 1.5rem",
                border: isGap ? "1px solid rgba(239, 68, 68, 0.4)" : (isOutage ? "1px solid rgba(245, 158, 11, 0.4)" : "1px solid var(--border-subtle)"),
                background: isGap ? "rgba(239, 68, 68, 0.05)" : "var(--bg-card)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "0.75rem" }}>
                <div>
                  <h3 style={{ fontSize: "1rem", color: "#fff" }}>{asset.name}</h3>
                  <span style={{ fontSize: "0.75rem", color: "var(--accent-cyan)" }}>{asset.sector}</span>
                </div>
                <span className={`badge badge-${asset.criticality === "CRITICAL" ? "high" : "medium"}`}>
                  {asset.criticality}
                </span>
              </div>

              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: "0.8rem", marginBottom: "0.4rem" }}>
                <span style={{ color: "var(--text-muted)" }}>Telemetry Volume Ratio</span>
                <span style={{ fontWeight: 700, color: isGap ? "var(--accent-crimson)" : (isOutage ? "var(--accent-amber)" : "var(--accent-emerald)") }}>
                  {asset.observed} / {asset.expected} events ({ratio.toFixed(0)}%)
                </span>
              </div>

              <div className="progress-container" style={{ marginBottom: "0.75rem" }}>
                <div
                  className="progress-bar"
                  style={{
                    width: `${ratio}%`,
                    background: isGap ? "var(--accent-crimson)" : (isOutage ? "var(--accent-amber)" : "var(--accent-emerald)"),
                  }}
                ></div>
              </div>

              <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", lineHeight: 1.4 }}>
                {asset.desc}
              </p>

              <div style={{ marginTop: "0.75rem", paddingTop: "0.5rem", borderTop: "1px solid rgba(255, 255, 255, 0.05)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>
                  {isGap ? "⚠️ High-Risk Monitoring Blind Spot" : (isOutage ? "ℹ️ Data Quality Outage Gated" : "✓ Telemetry Active")}
                </span>
                {isGap && coverageFindings.length > 0 && (
                  <button
                    onClick={() => onSelectFinding(coverageFindings[0])}
                    className="btn-primary"
                    style={{ fontSize: "0.75rem", padding: "0.3rem 0.6rem" }}
                  >
                    View Finding
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

    </div>
  );
};

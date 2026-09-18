import React from "react";
import { Search, EyeOff } from "lucide-react";
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
      desc: "Continuous SIEM & EDR telemetry stream. Consistent event frequency.",
    },
    {
      name: "High Voltage Transformer Control Bus",
      sector: "Power & Energy",
      criticality: "CRITICAL",
      expected: 45,
      observed: 0,
      status: "BLIND_SPOT_GAP",
      desc: "No security events observed in the active simulated load (Data Trust: 92%). Data-trust-gated signal for supervisory review.",
    },
    {
      name: "Core Banking Transaction DB Cluster",
      sector: "Financial Services",
      criticality: "CRITICAL",
      expected: 50,
      observed: 48,
      status: "HEALTHY_COVERAGE",
      desc: "Robust audit logging and privilege access telemetry stream.",
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
      desc: "Low volume caused by sensor link failure. Correctly classified as data uncertainty (DQ Gate active).",
    },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      
      {/* Header Info */}
      <div className="glass-card hud-corner" style={{ padding: "1.65rem" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "1rem" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.35rem" }}>
              <EyeOff size={20} color="var(--accent-purple)" />
              <h2 style={{ fontSize: "1.25rem", color: "#fff", fontWeight: 700, margin: 0 }}>
                Negative Space & Monitoring Coverage Map
              </h2>
            </div>
            <p style={{ fontSize: "0.82rem", color: "#64748b", margin: 0 }}>
              Detects evidence that <em>should</em> exist under expected operating context but doesn't (FR-041). Gated by Data Trust (§7.2.1) to distinguish blind spots from data ingestion outages.
            </p>
          </div>
          <span className="badge badge-purple" style={{ fontSize: "0.75rem" }}>
            <Search size={13} /> NEGATIVE-SPACE HYPOTHESIS ENGINE
          </span>
        </div>
      </div>

      {/* Grid of Monitored Assets */}
      <div className="stats-grid-2">
        {monitoredAssets.map((asset, i) => {
          const isGap = asset.status === "BLIND_SPOT_GAP";
          const isOutage = asset.status === "DATA_OUTAGE_UNCERTAINTY";
          const ratio = (asset.observed / asset.expected) * 100;

          return (
            <div
              key={i}
              className="glass-card hud-corner"
              style={{
                padding: "1.45rem 1.65rem",
                border: isGap
                  ? "1px solid rgba(239, 68, 68, 0.45)"
                  : isOutage
                  ? "1px solid rgba(245, 158, 11, 0.45)"
                  : "1px solid var(--border-subtle)",
                background: isGap
                  ? "rgba(239, 68, 68, 0.05)"
                  : isOutage
                  ? "rgba(245, 158, 11, 0.04)"
                  : "var(--bg-card)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "0.85rem", flexWrap: "wrap", gap: "0.5rem" }}>
                <div>
                  <h3 style={{ fontSize: "1.05rem", color: "#fff", fontWeight: 700 }}>{asset.name}</h3>
                  <span style={{ fontSize: "0.76rem", color: "var(--accent-cyan)" }}>{asset.sector}</span>
                </div>
                <span className={`badge badge-${asset.criticality === "CRITICAL" ? "high" : "medium"}`}>
                  {asset.criticality}
                </span>
              </div>

              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: "0.82rem", marginBottom: "0.45rem" }}>
                <span style={{ color: "#64748b" }}>Telemetry Volume Ratio</span>
                <span
                  style={{
                    fontWeight: 700,
                    fontFamily: "var(--font-mono)",
                    color: isGap ? "var(--accent-crimson)" : isOutage ? "var(--accent-amber)" : "var(--accent-emerald)",
                  }}
                >
                  {asset.observed} / {asset.expected} events ({ratio.toFixed(0)}%)
                </span>
              </div>

              <div className="progress-container" style={{ marginBottom: "0.85rem" }}>
                <div
                  className="progress-bar"
                  style={{
                    width: `${ratio}%`,
                    background: isGap
                      ? "var(--accent-crimson)"
                      : isOutage
                      ? "var(--accent-amber)"
                      : "var(--accent-emerald)",
                  }}
                ></div>
              </div>

              <p style={{ fontSize: "0.83rem", color: "#94a3b8", lineHeight: 1.45 }}>
                {asset.desc}
              </p>

              <div style={{ marginTop: "1rem", paddingTop: "0.65rem", borderTop: "1px solid rgba(255, 255, 255, 0.06)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: "0.74rem", color: isGap ? "var(--accent-crimson)" : isOutage ? "var(--accent-amber)" : "var(--accent-emerald)", fontWeight: 600 }}>
                  {isGap ? "⚠️ High-Risk Monitoring Blind Spot" : isOutage ? "ℹ️ Data Quality Outage Gated" : "✓ Telemetry Active & Healthy"}
                </span>
                {isGap && coverageFindings.length > 0 && (
                  <button
                    onClick={() => onSelectFinding(coverageFindings[0])}
                    className="btn-primary"
                    id={`view-coverage-finding-btn-${i}`}
                    style={{ fontSize: "0.75rem", padding: "0.35rem 0.75rem" }}
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


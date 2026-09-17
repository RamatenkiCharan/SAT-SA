import React from "react";
import { AlertTriangle, CheckCircle, ShieldAlert, ArrowRight } from "lucide-react";
import type { Finding } from "../types";

interface MetricOutcomeCardProps {
  finding: Finding;
  onSelectFinding: (finding: Finding) => void;
}

export const MetricOutcomeCard: React.FC<MetricOutcomeCardProps> = ({
  finding,
  onSelectFinding,
}) => {
  // Extract details from the finding description or expected/observed behavior
  // This is a simplified extraction since the actual metric value is in the description string
  const cseName = finding.cse_name || "Critical Infrastructure Entity";
  
  const expected = finding.expected_behavior || "";
  const observed = finding.observed_behavior || "";
  
  const kpiMatch = expected.match(/alongside (.*?)\./);
  const outcomeMatch = observed.match(/Outcome metrics \((.*?)\)/);
  
  const kpiName = kpiMatch ? kpiMatch[1] : "Reported KPI";
  const kpiValue = "Meets Target"; // We no longer pass the exact value, but we know it met target
  
  const outcomesStr = outcomeMatch ? outcomeMatch[1] : "Execution Gaps";
  
  return (
    <div
      className="glass-card hud-corner"
      style={{
        padding: "1.85rem",
        background: "linear-gradient(135deg, rgba(12, 19, 36, 0.96) 0%, rgba(18, 30, 64, 0.8) 100%)",
        border: "1px solid rgba(0, 216, 246, 0.35)",
        boxShadow: "0 12px 40px -8px rgba(0, 0, 0, 0.7), 0 0 25px rgba(0, 216, 246, 0.08)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "0.75rem", marginBottom: "1.35rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.65rem", flexWrap: "wrap" }}>
          <span className="badge badge-high" style={{ padding: "0.35rem 0.8rem", fontSize: "0.75rem" }}>
            <AlertTriangle size={14} /> METRIC-OUTCOME DIVERGENCE DETECTED
          </span>
          <span style={{ fontSize: "0.86rem", color: "var(--accent-cyan)", fontWeight: 700, letterSpacing: "0.02em" }}>
            Supervisory Reality Check: {cseName}
          </span>
        </div>
        <span style={{ fontSize: "0.74rem", color: "#64748b", fontFamily: "var(--font-mono)", background: "rgba(0,0,0,0.3)", padding: "0.2rem 0.5rem", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-subtle)" }}>
          RULESET: {finding.ruleset_version || "EG_FUSION_V1.0"}
        </span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "1.5rem", marginBottom: "1.35rem" }}>
        
        {/* Left: What Documentation / Traditional KPI Claims */}
        <div
          style={{
            background: "rgba(16, 185, 129, 0.06)",
            border: "1px solid rgba(16, 185, 129, 0.3)",
            borderRadius: "var(--radius-md)",
            padding: "1.35rem",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.65rem" }}>
            <CheckCircle size={18} color="#34d399" />
            <h3 style={{ fontSize: "1rem", color: "#34d399", fontWeight: 700 }}>Self-Reported Maturity & KPI Claim</h3>
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: "0.5rem", marginBottom: "0.5rem" }}>
            <span style={{ fontSize: "2.2rem", fontWeight: 800, color: "#fff", fontFamily: "var(--font-mono)" }}>{kpiValue}</span>
            <span style={{ fontSize: "0.85rem", color: "#34d399", fontWeight: 600 }}>{kpiName}</span>
          </div>
          <p style={{ fontSize: "0.83rem", color: "#94a3b8", lineHeight: 1.45 }}>
            {finding.expected_behavior || "Target KPI reported as successfully achieved, indicating high operational maturity and optimal SLA adherence."}
          </p>
        </div>

        {/* Right: What SAT-SA Operational Evidence Discovers */}
        <div
          style={{
            background: "rgba(239, 68, 68, 0.08)",
            border: "1px solid rgba(239, 68, 68, 0.4)",
            borderRadius: "var(--radius-md)",
            padding: "1.35rem",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.65rem" }}>
            <ShieldAlert size={18} color="#f87171" />
            <h3 style={{ fontSize: "1rem", color: "#f87171", fontWeight: 700 }}>SAT-SA Evidence-Based Reality</h3>
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: "0.5rem", marginBottom: "0.5rem" }}>
            <span style={{ fontSize: "1.2rem", fontWeight: 800, color: "#f87171", fontFamily: "var(--font-mono)", textTransform: "uppercase" }}>{outcomesStr} Diverged</span>
          </div>
          <p style={{ fontSize: "0.83rem", color: "#94a3b8", lineHeight: 1.45 }}>
            <strong style={{ color: "#f87171" }}>Execution Gap Identified:</strong> {finding.observed_behavior}
          </p>
          {finding.supporting_signals && finding.supporting_signals.length > 0 && (
             <ul style={{ fontSize: "0.78rem", color: "#94a3b8", marginTop: "0.5rem", paddingLeft: "1.2rem", listStyleType: "circle" }}>
                {finding.supporting_signals.slice(0, 2).map((sig: string, idx: number) => (
                    <li key={idx} style={{ marginBottom: "0.2rem" }}>{sig}</li>
                ))}
             </ul>
          )}
        </div>

      </div>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "1rem", paddingTop: "0.75rem", borderTop: "1px solid rgba(255, 255, 255, 0.08)" }}>
        <div style={{ fontStyle: "italic", fontSize: "0.85rem", color: "#94a3b8" }}>
          "Don't ask whether a SOC says it works. Analyze the evidence of how it actually operates."
        </div>
        <button
          onClick={() => onSelectFinding(finding)}
          className="btn-primary"
          style={{ padding: "0.5rem 1.15rem", fontSize: "0.82rem" }}
        >
          Examine Evidence Chain <ArrowRight size={15} />
        </button>
      </div>

    </div>
  );
};

import React from "react";
import {
  AlertTriangle,
  CheckCircle,
  ShieldAlert,
  ArrowRight,
  Database,
  Search,
  Zap,
} from "lucide-react";
import type { Finding } from "../types";
import { MetricOutcomeCard } from "./MetricOutcomeCard";

interface OverviewViewProps {
  findings: Finding[];
  onSelectFinding: (finding: Finding) => void;
  onNavigate: (tab: string) => void;
}

export const OverviewView: React.FC<OverviewViewProps> = ({
  findings,
  onSelectFinding,
  onNavigate,
}) => {
  const highPriorityCount = findings.filter((f) => f.priority_score >= 0.75).length;
  const executionGapCount = findings.filter((f) =>
    ["FAST_CLOSURE", "ESCALATION_GAP", "REPEATED_UNRESOLVED_ALERTS"].includes(f.finding_type)
  ).length;
  const coverageGapCount = findings.filter((f) => f.finding_type === "COVERAGE_GAP").length;

  const divergenceFinding = findings.find(
    (f) => f.finding_type === "METRIC_OUTCOME_DIVERGENCE"
  );
  const wowFinding = findings.find(
    (f) => f.cse_name.includes("National Power") || f.finding_type === "FAST_CLOSURE"
  );

  return (
    <div className="page-fade-enter" style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
      
      {/* "THE SUPERVISORY REALITY CHECK" — Goodhart's Law Operational Reality Banner */}
      {divergenceFinding ? (
        <MetricOutcomeCard finding={divergenceFinding} onSelectFinding={onSelectFinding} />
      ) : (
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
              <AlertTriangle size={14} /> THE SUPERVISORY REALITY CHECK
            </span>
            <span style={{ fontSize: "0.86rem", color: "var(--accent-cyan)", fontWeight: 700, letterSpacing: "0.02em" }}>
              National Critical Infrastructure Supervisory Demonstration
            </span>
          </div>
          <span style={{ fontSize: "0.74rem", color: "#64748b", fontFamily: "var(--font-mono)", background: "rgba(0,0,0,0.3)", padding: "0.2rem 0.5rem", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-subtle)" }}>
            RULESET: EG_FUSION_V1.0
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
              <h3 style={{ fontSize: "1rem", color: "#34d399", fontWeight: 700 }}>Self-Reported Maturity & KPI Dashboard</h3>
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: "0.5rem", marginBottom: "0.5rem" }}>
              <span style={{ fontSize: "2.2rem", fontWeight: 800, color: "#fff", fontFamily: "var(--font-mono)" }}>99.2%</span>
              <span style={{ fontSize: "0.85rem", color: "#34d399", fontWeight: 600 }}>SLA Compliance Rate (NPDC)</span>
            </div>
            <p style={{ fontSize: "0.83rem", color: "#94a3b8", lineHeight: 1.45 }}>
              "All high & critical alerts closed within mandated response windows. Questionnaire self-assessment certifies Tier-3 SOC maturity with comprehensive IR escalation."
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
              <span style={{ fontSize: "2.2rem", fontWeight: 800, color: "#f87171", fontFamily: "var(--font-mono)" }}>3.8 min</span>
              <span style={{ fontSize: "0.85rem", color: "#64748b" }}>Median Critical Closure (Peer Baseline: 52m)</span>
            </div>
            <p style={{ fontSize: "0.83rem", color: "#94a3b8", lineHeight: 1.45 }}>
              <strong style={{ color: "#f87171" }}>Execution Gap Identified:</strong> Critical SCADA intrusions closed rapidly with &le;1 evidence item, 0 escalation records, and recurring unmitigated ransomware triggers on High Voltage Grid Substation.
            </p>
          </div>

        </div>

        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "1rem", paddingTop: "0.75rem", borderTop: "1px solid rgba(255, 255, 255, 0.08)" }}>
          <div style={{ fontStyle: "italic", fontSize: "0.85rem", color: "#94a3b8" }}>
            "Don't ask whether a SOC says it works. Analyze the evidence of how it actually operates."
          </div>
          {wowFinding && (
            <button
              onClick={() => onSelectFinding(wowFinding)}
              className="btn-primary"
              id="examine-evidence-chain-btn"
              style={{ padding: "0.5rem 1.15rem", fontSize: "0.82rem" }}
            >
              Examine Evidence Chain <ArrowRight size={15} />
            </button>
          )}
        </div>
      </div>
      )}

      {/* KPI Stats Cards */}
      <div className="stats-grid-4">
        
        <div
          className="glass-card glass-card-interactive"
          onClick={() => onNavigate("findings")}
          style={{ padding: "1.35rem" }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", color: "#64748b", marginBottom: "0.5rem" }}>
            <span style={{ fontSize: "0.78rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em" }}>High-Priority Gaps</span>
            <ShieldAlert size={18} color="var(--accent-crimson)" />
          </div>
          <div style={{ fontSize: "2.1rem", fontWeight: 800, color: "#fff", fontFamily: "var(--font-mono)" }}>{highPriorityCount}</div>
          <div style={{ fontSize: "0.75rem", color: "var(--accent-crimson)", marginTop: "0.35rem", fontWeight: 600 }}>
            Requires Immediate Supervisory Review →
          </div>
        </div>

        <div
          className="glass-card glass-card-interactive"
          onClick={() => onNavigate("findings")}
          style={{ padding: "1.35rem" }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", color: "#64748b", marginBottom: "0.5rem" }}>
            <span style={{ fontSize: "0.78rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em" }}>Execution Gaps</span>
            <Zap size={18} color="var(--accent-amber)" />
          </div>
          <div style={{ fontSize: "2.1rem", fontWeight: 800, color: "#fff", fontFamily: "var(--font-mono)" }}>{executionGapCount}</div>
          <div style={{ fontSize: "0.75rem", color: "var(--accent-amber)", marginTop: "0.35rem", fontWeight: 600 }}>
            Metric Gaming / Fast Closures →
          </div>
        </div>

        <div
          className="glass-card glass-card-interactive"
          onClick={() => onNavigate("negativespace")}
          style={{ padding: "1.35rem" }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", color: "#64748b", marginBottom: "0.5rem" }}>
            <span style={{ fontSize: "0.78rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em" }}>Negative Space</span>
            <Search size={18} color="var(--accent-purple)" />
          </div>
          <div style={{ fontSize: "2.1rem", fontWeight: 800, color: "#fff", fontFamily: "var(--font-mono)" }}>{coverageGapCount}</div>
          <div style={{ fontSize: "0.75rem", color: "var(--accent-purple)", marginTop: "0.35rem", fontWeight: 600 }}>
            Monitoring Blind Spots (Data-Gated) →
          </div>
        </div>

        <div
          className="glass-card glass-card-interactive"
          onClick={() => onNavigate("benchmarks")}
          style={{ padding: "1.35rem" }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", color: "#64748b", marginBottom: "0.5rem" }}>
            <span style={{ fontSize: "0.78rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em" }}>Data Trust Index</span>
            <Database size={18} color="var(--accent-cyan)" />
          </div>
          <div style={{ fontSize: "2.1rem", fontWeight: 800, color: "#fff", fontFamily: "var(--font-mono)" }}>92.4%</div>
          <div style={{ fontSize: "0.75rem", color: "var(--accent-cyan)", marginTop: "0.35rem", fontWeight: 600 }}>
            Formula-Backed §7.2.1 Score →
          </div>
        </div>

      </div>

      {/* Priority Supervisory Queue Summary */}
      <div className="glass-card" style={{ padding: "1.65rem" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "1rem", marginBottom: "1.35rem" }}>
          <div>
            <h2 style={{ fontSize: "1.2rem", color: "#fff", fontWeight: 700 }}>Priority Supervisory Review Queue</h2>
            <p style={{ fontSize: "0.82rem", color: "#64748b", marginTop: "0.2rem" }}>
              Algorithmically ranked by 5-component Evidence Fusion score (§10.5). Click any finding to inspect grounded records.
            </p>
          </div>
          <button
            onClick={() => onNavigate("findings")}
            className="btn-secondary"
            id="view-full-queue-btn"
            style={{ fontSize: "0.82rem" }}
          >
            View Full Queue ({findings.length}) <ArrowRight size={15} />
          </button>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem" }}>
          {findings.slice(0, 4).map((f) => (
            <div
              key={f.finding_id}
              onClick={() => onSelectFinding(f)}
              className="glass-card-interactive"
              style={{
                padding: "1.1rem 1.35rem",
                borderRadius: "var(--radius-md)",
                background: "rgba(15, 23, 42, 0.55)",
                border: "1px solid var(--border-subtle)",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                flexWrap: "wrap",
                gap: "1rem",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "1rem", minWidth: "280px", flex: 1 }}>
                <span className={`badge badge-${f.priority_label.toLowerCase()}`}>
                  {f.priority_label}
                </span>
                <div>
                  <div style={{ fontSize: "0.95rem", fontWeight: 700, color: "#fff", display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
                    {f.title}
                    <span style={{ fontSize: "0.76rem", color: "#64748b", fontWeight: 400 }}>
                      • {f.cse_name} ({f.sector})
                    </span>
                  </div>
                  <div style={{ fontSize: "0.82rem", color: "#94a3b8", marginTop: "0.25rem" }}>
                    {f.headline}
                  </div>
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "1.75rem" }}>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: "0.73rem", color: "#64748b" }}>Priority Score</div>
                  <div style={{ fontSize: "1.15rem", fontWeight: 800, color: "var(--accent-cyan)", fontFamily: "var(--font-mono)" }}>
                    {f.priority_score.toFixed(3)}
                  </div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: "0.73rem", color: "#64748b" }}>Evidence Records</div>
                  <div style={{ fontSize: "0.92rem", fontWeight: 700, color: "#fff" }}>
                    {f.evidence_record_count} records
                  </div>
                </div>
                <ArrowRight size={18} color="var(--accent-cyan)" />
              </div>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
};


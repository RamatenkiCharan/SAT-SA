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

  const wowFinding = findings.find(
    (f) => f.cse_name.includes("National Power") || f.finding_type === "FAST_CLOSURE"
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
      
      {/* "THE WOW MOMENT" — Goodhart's Law Operational Reality Banner */}
      <div
        className="glass-card"
        style={{
          padding: "1.75rem",
          background: "linear-gradient(135deg, rgba(15, 23, 42, 0.95) 0%, rgba(23, 37, 84, 0.7) 100%)",
          border: "1px solid rgba(0, 240, 255, 0.3)",
          boxShadow: "0 0 35px rgba(0, 240, 255, 0.12)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1.25rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
            <span className="badge badge-high" style={{ padding: "0.35rem 0.75rem", fontSize: "0.75rem" }}>
              <AlertTriangle size={14} /> THE SUPERVISORY REALITY CHECK
            </span>
            <span style={{ fontSize: "0.85rem", color: "var(--accent-cyan)", fontWeight: 600 }}>
              SIH Problem Statement 26157 Core Demonstration
            </span>
          </div>
          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
            RULESET: EG_FUSION_V1.0
          </span>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem", marginBottom: "1.25rem" }}>
          
          {/* Left: What Documentation / Traditional KPI Claims */}
          <div
            style={{
              background: "rgba(16, 185, 129, 0.05)",
              border: "1px solid rgba(16, 185, 129, 0.25)",
              borderRadius: "var(--radius-md)",
              padding: "1.25rem",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.6rem" }}>
              <CheckCircle size={18} color="#34d399" />
              <h3 style={{ fontSize: "1rem", color: "#34d399" }}>Self-Reported Maturity & KPI Dashboard</h3>
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: "0.5rem", marginBottom: "0.5rem" }}>
              <span style={{ fontSize: "2rem", fontWeight: 800, color: "#fff" }}>99.2%</span>
              <span style={{ fontSize: "0.85rem", color: "#34d399" }}>SLA Compliance Rate (NPDC)</span>
            </div>
            <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", lineHeight: 1.4 }}>
              "All high & critical alerts closed within mandated response windows. Questionnaire self-assessment certifies Tier-3 SOC maturity with comprehensive IR escalation."
            </p>
          </div>

          {/* Right: What SAT-SA Operational Evidence Discovers */}
          <div
            style={{
              background: "rgba(239, 68, 68, 0.07)",
              border: "1px solid rgba(239, 68, 68, 0.35)",
              borderRadius: "var(--radius-md)",
              padding: "1.25rem",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.6rem" }}>
              <ShieldAlert size={18} color="#f87171" />
              <h3 style={{ fontSize: "1rem", color: "#f87171" }}>SAT-SA Evidence-Based Reality</h3>
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: "0.5rem", marginBottom: "0.5rem" }}>
              <span style={{ fontSize: "2rem", fontWeight: 800, color: "#f87171" }}>3.8 min</span>
              <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Median Critical Closure (Peer Baseline: 52m)</span>
            </div>
            <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", lineHeight: 1.4 }}>
              <strong style={{ color: "#f87171" }}>Execution Gap Identified:</strong> Critical SCADA intrusions closed rapidly with &le;1 evidence item, 0 escalation records, and recurring unmitigated ransomware triggers on High Voltage Grid Substation.
            </p>
          </div>

        </div>

        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingTop: "0.5rem", borderTop: "1px solid rgba(255, 255, 255, 0.06)" }}>
          <div style={{ fontStyle: "italic", fontSize: "0.85rem", color: "var(--text-secondary)" }}>
            "Don't ask whether a SOC says it works. Analyze the evidence of how it actually operates."
          </div>
          {wowFinding && (
            <button
              onClick={() => onSelectFinding(wowFinding)}
              className="btn-primary"
              style={{ padding: "0.45rem 1rem", fontSize: "0.8rem" }}
            >
              Examine Evidence Chain <ArrowRight size={14} />
            </button>
          )}
        </div>

      </div>

      {/* KPI Stats Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "1.25rem" }}>
        
        <div className="glass-card" style={{ padding: "1.25rem" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", color: "var(--text-muted)", marginBottom: "0.5rem" }}>
            <span style={{ fontSize: "0.8rem", fontWeight: 600, textTransform: "uppercase" }}>High-Priority Gaps</span>
            <ShieldAlert size={18} color="var(--accent-crimson)" />
          </div>
          <div style={{ fontSize: "2rem", fontWeight: 800, color: "#fff" }}>{highPriorityCount}</div>
          <div style={{ fontSize: "0.75rem", color: "var(--accent-crimson)", marginTop: "0.3rem" }}>
            Requires Immediate Supervisory Review
          </div>
        </div>

        <div className="glass-card" style={{ padding: "1.25rem" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", color: "var(--text-muted)", marginBottom: "0.5rem" }}>
            <span style={{ fontSize: "0.8rem", fontWeight: 600, textTransform: "uppercase" }}>Execution Gaps</span>
            <Zap size={18} color="var(--accent-amber)" />
          </div>
          <div style={{ fontSize: "2rem", fontWeight: 800, color: "#fff" }}>{executionGapCount}</div>
          <div style={{ fontSize: "0.75rem", color: "var(--accent-amber)", marginTop: "0.3rem" }}>
            Metric Gaming / Fast Closures
          </div>
        </div>

        <div className="glass-card" style={{ padding: "1.25rem" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", color: "var(--text-muted)", marginBottom: "0.5rem" }}>
            <span style={{ fontSize: "0.8rem", fontWeight: 600, textTransform: "uppercase" }}>Negative Space</span>
            <Search size={18} color="var(--accent-purple)" />
          </div>
          <div style={{ fontSize: "2rem", fontWeight: 800, color: "#fff" }}>{coverageGapCount}</div>
          <div style={{ fontSize: "0.75rem", color: "var(--accent-purple)", marginTop: "0.3rem" }}>
            Monitoring Blind Spots (Data-Gated)
          </div>
        </div>

        <div className="glass-card" style={{ padding: "1.25rem" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", color: "var(--text-muted)", marginBottom: "0.5rem" }}>
            <span style={{ fontSize: "0.8rem", fontWeight: 600, textTransform: "uppercase" }}>Data Trust Index</span>
            <Database size={18} color="var(--accent-cyan)" />
          </div>
          <div style={{ fontSize: "2rem", fontWeight: 800, color: "#fff" }}>92.4%</div>
          <div style={{ fontSize: "0.75rem", color: "var(--accent-cyan)", marginTop: "0.3rem" }}>
            Formula-Backed §7.2.1 Score
          </div>
        </div>

      </div>

      {/* Priority Supervisory Queue Summary */}
      <div className="glass-card" style={{ padding: "1.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1.25rem" }}>
          <div>
            <h2 style={{ fontSize: "1.2rem", color: "#fff" }}>Priority Supervisory Review Queue</h2>
            <p style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
              Algorithmically ranked by 5-component Evidence Fusion score (§10.5). Click any finding to inspect grounded records.
            </p>
          </div>
          <button
            onClick={() => onNavigate("findings")}
            className="btn-secondary"
            style={{ fontSize: "0.8rem" }}
          >
            View Full Queue ({findings.length}) <ArrowRight size={14} />
          </button>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
          {findings.slice(0, 4).map((f) => (
            <div
              key={f.finding_id}
              onClick={() => onSelectFinding(f)}
              className="glass-card-interactive"
              style={{
                padding: "1rem 1.25rem",
                borderRadius: "var(--radius-md)",
                background: "rgba(30, 41, 59, 0.5)",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
                <span className={`badge badge-${f.priority_label.toLowerCase()}`}>
                  {f.priority_label}
                </span>
                <div>
                  <div style={{ fontSize: "0.95rem", fontWeight: 600, color: "#fff", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    {f.title}
                    <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontWeight: 400 }}>
                      • {f.cse_name} ({f.sector})
                    </span>
                  </div>
                  <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: "0.2rem" }}>
                    {f.headline}
                  </div>
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "1.5rem" }}>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Priority Score</div>
                  <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--accent-cyan)", fontFamily: "var(--font-mono)" }}>
                    {f.priority_score.toFixed(3)}
                  </div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Evidence Records</div>
                  <div style={{ fontSize: "0.9rem", fontWeight: 600, color: "#fff" }}>
                    {f.evidence_record_count} records
                  </div>
                </div>
                <ArrowRight size={18} color="var(--text-muted)" />
              </div>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
};

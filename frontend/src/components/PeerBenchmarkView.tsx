import React, { useState, useEffect } from "react";
import { BarChart3, Activity } from "lucide-react";
import type { CSEBenchmarkMetric, PeerCohort } from "../types";
import { fetchBenchmarks } from "../api";

interface PeerBenchmarkViewProps {
  activeVersionId: string | null;
}

export const PeerBenchmarkView: React.FC<PeerBenchmarkViewProps> = ({ activeVersionId }) => {
  const [entities, setEntities] = useState<CSEBenchmarkMetric[]>([]);
  const [cohorts, setCohorts] = useState<PeerCohort[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    fetchBenchmarks(activeVersionId || undefined)
      .then((data) => {
        setEntities(data.entities || []);
        setCohorts(data.cohorts || []);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Failed to fetch benchmarks:", err);
        setLoading(false);
      });
  }, [activeVersionId]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      
      {/* Header Info */}
      <div className="glass-card hud-corner" style={{ padding: "1.65rem" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "1rem" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.35rem" }}>
              <BarChart3 size={20} color="var(--accent-cyan)" />
              <h2 style={{ fontSize: "1.25rem", color: "#fff", fontWeight: 700, margin: 0 }}>Peer Cohort Benchmarking Engine</h2>
            </div>
            <p style={{ fontSize: "0.82rem", color: "#64748b", margin: 0 }}>
              Robust non-parametric statistical comparison (Median & MAD) grouped by sector and entity scale (min cohort size: 5, with global fallback).
            </p>
          </div>
          <span className="badge badge-purple" style={{ fontSize: "0.75rem" }}>
            STATISTICAL MAD THRESHOLDING
          </span>
        </div>
      </div>

      {/* Cohorts Summary Cards */}
      <div className="stats-grid-3">
        {cohorts.slice(0, 3).map((c, i) => (
          <div key={i} className="glass-card" style={{ padding: "1.35rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
              <span style={{ fontSize: "0.92rem", fontWeight: 700, color: "var(--accent-cyan)" }}>
                {c.sector} ({c.scale})
              </span>
              <span className="badge" style={{ background: "rgba(255,255,255,0.08)", color: "#f8fafc", fontSize: "0.68rem" }}>
                {c.group_size} Peers
              </span>
            </div>
            
            <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem", fontSize: "0.82rem", marginTop: "0.5rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", paddingBottom: "0.35rem", borderBottom: "1px solid rgba(255, 255, 255, 0.05)" }}>
                <span style={{ color: "#64748b" }}>Median Critical Closure:</span>
                <strong style={{ color: "#fff", fontFamily: "var(--font-mono)" }}>{c.closure_duration.median_minutes} min</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", paddingBottom: "0.35rem", borderBottom: "1px solid rgba(255, 255, 255, 0.05)" }}>
                <span style={{ color: "#64748b" }}>Cohort MAD Dispersion:</span>
                <span style={{ color: "var(--accent-amber)", fontFamily: "var(--font-mono)", fontWeight: 700 }}>&plusmn;{c.closure_duration.mad_minutes} min</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", paddingBottom: "0.35rem", borderBottom: "1px solid rgba(255, 255, 255, 0.05)" }}>
                <span style={{ color: "#64748b" }}>Median Investigation Evidence:</span>
                <strong style={{ color: "#fff" }}>{c.evidence_count.median} items</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "#64748b" }}>Critical Escalation Ratio:</span>
                <strong style={{ color: "var(--accent-emerald)", fontFamily: "var(--font-mono)" }}>{c.escalation_ratio.median_percent}%</strong>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Cross-Entity Operational Comparison Table */}
      <div className="glass-card" style={{ padding: "1.65rem" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1.15rem", flexWrap: "wrap", gap: "0.5rem" }}>
          <h3 style={{ fontSize: "1.1rem", color: "#fff", fontWeight: 700, margin: 0 }}>
            Entity Operational Evidence vs Baseline Matrix
          </h3>
          <span style={{ fontSize: "0.75rem", color: "#64748b" }}>
            {entities.length} Critical Sector Entities Evaluated
          </span>
        </div>

        {loading ? (
          <div style={{ padding: "3rem", textAlign: "center", color: "#64748b" }}>
            <Activity size={24} style={{ margin: "0 auto 0.75rem", animation: "spin 2s linear infinite", color: "var(--accent-cyan)" }} />
            Computing peer statistics and MAD baselines...
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border-subtle)", color: "#64748b", textAlign: "left" }}>
                  <th style={{ padding: "0.75rem 0.6rem" }}>Critical Sector Entity</th>
                  <th style={{ padding: "0.75rem 0.6rem" }}>Sector & Scale</th>
                  <th style={{ padding: "0.75rem 0.6rem" }}>Total Alerts</th>
                  <th style={{ padding: "0.75rem 0.6rem" }}>Self-Reported SLA</th>
                  <th style={{ padding: "0.75rem 0.6rem" }}>Median Critical Closure</th>
                  <th style={{ padding: "0.75rem 0.6rem" }}>Investigation Depth</th>
                  <th style={{ padding: "0.75rem 0.6rem" }}>Escalation Ratio</th>
                  <th style={{ padding: "0.75rem 0.6rem" }}>Supervisory Status</th>
                </tr>
              </thead>
              <tbody>
                {entities.map((m) => {
                  const isAnomaly = m.median_critical_closure_minutes < 10 || m.critical_escalation_ratio < 20;
                  return (
                    <tr
                      key={m.cse_id}
                      style={{
                        borderBottom: "1px solid rgba(255, 255, 255, 0.04)",
                        background: isAnomaly ? "rgba(239, 68, 68, 0.03)" : "transparent",
                      }}
                    >
                      <td style={{ padding: "0.75rem 0.6rem", fontWeight: 700, color: "#fff" }}>{m.cse_name}</td>
                      <td style={{ padding: "0.75rem 0.6rem", color: "var(--accent-cyan)" }}>{m.sector} ({m.scale})</td>
                      <td style={{ padding: "0.75rem 0.6rem", color: "#94a3b8" }}>{m.total_alerts} ({m.critical_alerts_count} crit)</td>
                      <td style={{ padding: "0.75rem 0.6rem", color: "var(--accent-emerald)", fontWeight: 700, fontFamily: "var(--font-mono)" }}>
                        {m.self_reported_sla_compliance}%
                      </td>
                      <td style={{ padding: "0.75rem 0.6rem", color: m.median_critical_closure_minutes < 10 ? "var(--accent-crimson)" : "#fff", fontWeight: 700, fontFamily: "var(--font-mono)" }}>
                        {m.median_critical_closure_minutes} min
                      </td>
                      <td style={{ padding: "0.75rem 0.6rem", color: m.median_evidence_count <= 1 ? "var(--accent-crimson)" : "#fff", fontWeight: 600 }}>
                        {m.median_evidence_count} items
                      </td>
                      <td style={{ padding: "0.75rem 0.6rem", color: m.critical_escalation_ratio < 20 ? "var(--accent-crimson)" : "var(--accent-emerald)", fontWeight: 700, fontFamily: "var(--font-mono)" }}>
                        {m.critical_escalation_ratio}%
                      </td>
                      <td style={{ padding: "0.75rem 0.6rem" }}>
                        {isAnomaly ? (
                          <span className="badge badge-high" style={{ fontSize: "0.68rem" }}>
                            ⚠️ EXECUTION GAP
                          </span>
                        ) : (
                          <span className="badge badge-confirmed" style={{ fontSize: "0.68rem" }}>
                            ✓ NORMAL COHORT
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

    </div>
  );
};


import React, { useState, useEffect } from "react";
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
    setLoading(true);
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
      <div className="glass-card" style={{ padding: "1.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <h2 style={{ fontSize: "1.25rem", color: "#fff" }}>Peer Cohort Benchmarking Engine</h2>
            <p style={{ fontSize: "0.82rem", color: "var(--text-muted)", marginTop: "0.2rem" }}>
              Robust statistical comparison (Median & MAD) grouped by sector and entity scale (min cohort size: 5, with global fallback).
            </p>
          </div>
          <span className="badge badge-purple" style={{ fontSize: "0.75rem" }}>
            STATISTICAL MAD THRESHOLDING
          </span>
        </div>
      </div>

      {/* Cohorts Summary Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "1rem" }}>
        {cohorts.slice(0, 3).map((c, i) => (
          <div key={i} className="glass-card" style={{ padding: "1.25rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem" }}>
              <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "var(--accent-cyan)" }}>
                {c.sector} ({c.scale})
              </span>
              <span className="badge" style={{ background: "rgba(255,255,255,0.08)", fontSize: "0.68rem" }}>
                {c.group_size} Peers
              </span>
            </div>
            
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", fontSize: "0.8rem", marginTop: "0.75rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "var(--text-muted)" }}>Median Critical Closure:</span>
                <strong style={{ color: "#fff" }}>{c.closure_duration.median_minutes} min</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "var(--text-muted)" }}>Cohort MAD Dispersion:</span>
                <span style={{ color: "var(--accent-amber)" }}>&plusmn;{c.closure_duration.mad_minutes} min</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "var(--text-muted)" }}>Median Investigation Evidence:</span>
                <strong style={{ color: "#fff" }}>{c.evidence_count.median} items</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "var(--text-muted)" }}>Critical Escalation Ratio:</span>
                <strong style={{ color: "var(--accent-emerald)" }}>{c.escalation_ratio.median_percent}%</strong>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Cross-Entity Operational Comparison Table */}
      <div className="glass-card" style={{ padding: "1.5rem" }}>
        <h3 style={{ fontSize: "1.05rem", color: "#fff", marginBottom: "1rem" }}>
          Entity Operational Evidence vs Baseline Matrix
        </h3>

        {loading ? (
          <div style={{ padding: "2rem", textAlign: "center", color: "var(--text-muted)" }}>
            Computing peer statistics...
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border-subtle)", color: "var(--text-muted)", textAlign: "left" }}>
                  <th style={{ padding: "0.75rem" }}>Critical Sector Entity</th>
                  <th style={{ padding: "0.75rem" }}>Sector & Scale</th>
                  <th style={{ padding: "0.75rem" }}>Total Alerts</th>
                  <th style={{ padding: "0.75rem" }}>Self-Reported SLA</th>
                  <th style={{ padding: "0.75rem" }}>Median Critical Closure</th>
                  <th style={{ padding: "0.75rem" }}>Investigation Depth</th>
                  <th style={{ padding: "0.75rem" }}>Escalation Ratio</th>
                  <th style={{ padding: "0.75rem" }}>Supervisory Status</th>
                </tr>
              </thead>
              <tbody>
                {entities.map((m) => {
                  const isAnomaly = m.median_critical_closure_minutes < 10 || m.critical_escalation_ratio < 20;
                  return (
                    <tr key={m.cse_id} style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.04)" }}>
                      <td style={{ padding: "0.75rem", fontWeight: 600, color: "#fff" }}>{m.cse_name}</td>
                      <td style={{ padding: "0.75rem", color: "var(--accent-cyan)" }}>{m.sector} ({m.scale})</td>
                      <td style={{ padding: "0.75rem" }}>{m.total_alerts} ({m.critical_alerts_count} crit)</td>
                      <td style={{ padding: "0.75rem", color: "var(--accent-emerald)", fontWeight: 700 }}>
                        {m.self_reported_sla_compliance}%
                      </td>
                      <td style={{ padding: "0.75rem", color: m.median_critical_closure_minutes < 10 ? "var(--accent-crimson)" : "#fff", fontWeight: 600 }}>
                        {m.median_critical_closure_minutes} min
                      </td>
                      <td style={{ padding: "0.75rem", color: m.median_evidence_count <= 1 ? "var(--accent-crimson)" : "#fff" }}>
                        {m.median_evidence_count} items
                      </td>
                      <td style={{ padding: "0.75rem", color: m.critical_escalation_ratio < 20 ? "var(--accent-crimson)" : "var(--accent-emerald)" }}>
                        {m.critical_escalation_ratio}%
                      </td>
                      <td style={{ padding: "0.75rem" }}>
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

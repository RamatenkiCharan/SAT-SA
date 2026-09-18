import React, { useState } from "react";
import {
  Target,
  ShieldCheck,
  AlertTriangle,
  Shuffle,
  BarChart3,
  ArrowRight,
  RefreshCw,
} from "lucide-react";
import { fetchReviewBudget } from "../api";
import type { Finding } from "../types";

interface ReviewSampleViewProps {
  findings: Finding[];
  onSelectFinding: (finding: Finding) => void;
  activeVersionId: string | null;
}

const BADGE_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  control: { bg: "rgba(139, 92, 246, 0.15)", border: "rgba(139, 92, 246, 0.5)", text: "#a78bfa" },
  uncertainty: { bg: "rgba(251, 191, 36, 0.12)", border: "rgba(251, 191, 36, 0.4)", text: "#fbbf24" },
  contradiction: { bg: "rgba(239, 68, 68, 0.12)", border: "rgba(239, 68, 68, 0.4)", text: "#f87171" },
  coverage: { bg: "rgba(16, 185, 129, 0.12)", border: "rgba(16, 185, 129, 0.4)", text: "#34d399" },
  priority: { bg: "rgba(0, 216, 246, 0.12)", border: "rgba(0, 216, 246, 0.4)", text: "#00d8f6" },
  diversity: { bg: "rgba(99, 102, 241, 0.12)", border: "rgba(99, 102, 241, 0.4)", text: "#818cf8" },
};

export const ReviewSampleView: React.FC<ReviewSampleViewProps> = ({
  findings,
  onSelectFinding,
  activeVersionId,
}) => {
  const [budget, setBudget] = useState(10);
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const runOptimization = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchReviewBudget({
        budget,
        dataset_version_id: activeVersionId || undefined,
      });
      setReport(result);
    } catch (err: any) {
      setError(err?.message || "Failed to optimize review budget.");
    } finally {
      setLoading(false);
    }
  };

  const getReasonBadge = (reason: string) => {
    if (reason.includes("control")) return { label: "CONTROL", style: BADGE_COLORS.control };
    if (reason.includes("uncertainty")) return { label: "UNCERTAINTY", style: BADGE_COLORS.uncertainty };
    if (reason.includes("contradiction")) return { label: "CONTRADICTION", style: BADGE_COLORS.contradiction };
    if (reason.includes("entity") || reason.includes("period") || reason.includes("finding type"))
      return { label: "COVERAGE", style: BADGE_COLORS.coverage };
    if (reason.includes("priority")) return { label: "PRIORITY", style: BADGE_COLORS.priority };
    if (reason.includes("pattern") || reason.includes("behavior"))
      return { label: "DIVERSITY", style: BADGE_COLORS.diversity };
    return { label: "SELECTED", style: BADGE_COLORS.priority };
  };

  return (
    <div className="page-fade-enter" style={{ display: "flex", flexDirection: "column", gap: "1.75rem" }}>
      {/* Header */}
      <div
        className="glass-card hud-corner"
        style={{
          padding: "1.65rem",
          background: "linear-gradient(135deg, rgba(12, 19, 36, 0.96) 0%, rgba(18, 30, 64, 0.8) 100%)",
          border: "1px solid rgba(0, 216, 246, 0.35)",
          boxShadow: "0 12px 40px -8px rgba(0, 0, 0, 0.7), 0 0 25px rgba(0, 216, 246, 0.08)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "1rem", marginBottom: "1rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.65rem" }}>
            <Target size={22} color="var(--accent-cyan)" />
            <h2 style={{ fontSize: "1.2rem", color: "#fff", fontWeight: 700, margin: 0 }}>
              Supervisory Review-Budget Optimizer
            </h2>
          </div>
          <span style={{ fontSize: "0.76rem", color: "#64748b", fontFamily: "var(--font-mono)", background: "rgba(0,0,0,0.3)", padding: "0.2rem 0.6rem", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-subtle)" }}>
            INNOVATION 4
          </span>
        </div>
        <p style={{ fontSize: "0.85rem", color: "#94a3b8", lineHeight: 1.55, marginBottom: "1.25rem" }}>
          Select a diverse, informative, evidence-grounded sample that gives supervisors maximum useful coverage
          of SOC operational behavior — balancing priority, uncertainty, coverage, diversity, and control samples.
        </p>

        {/* Budget Controls */}
        <div style={{ display: "flex", alignItems: "center", gap: "1.25rem", flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <label style={{ fontSize: "0.82rem", color: "#94a3b8", fontWeight: 600 }}>Review Budget:</label>
            <select
              value={budget}
              onChange={(e) => setBudget(Number(e.target.value))}
              id="review-budget-select"
              style={{
                background: "rgba(15, 23, 42, 0.8)",
                border: "1px solid var(--border-card)",
                borderRadius: "var(--radius-sm)",
                color: "#fff",
                padding: "0.4rem 0.75rem",
                fontSize: "0.85rem",
                fontFamily: "var(--font-mono)",
              }}
            >
              {[5, 10, 15, 25, 50].map((n) => (
                <option key={n} value={n}>{n} cases</option>
              ))}
            </select>
          </div>
          <button
            onClick={runOptimization}
            disabled={loading}
            className="btn-primary"
            id="run-optimization-btn"
            style={{ padding: "0.5rem 1.15rem", fontSize: "0.82rem", display: "flex", alignItems: "center", gap: "0.4rem" }}
          >
            {loading ? <RefreshCw size={15} className="spin-animation" /> : <Shuffle size={15} />}
            {loading ? "Optimizing..." : "Optimize Sample"}
          </button>
          <div style={{ fontSize: "0.78rem", color: "#64748b" }}>
            Candidate pool: <strong style={{ color: "#fff" }}>{findings.length}</strong> findings
          </div>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div className="glass-card" style={{ padding: "1.25rem", border: "1px solid var(--border-danger)", background: "rgba(239, 68, 68, 0.06)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "#f87171", fontSize: "0.9rem", fontWeight: 600 }}>
            <AlertTriangle size={16} /> {error}
          </div>
        </div>
      )}

      {/* Results */}
      {report && (
        <>
          {/* Coverage Summary Cards */}
          <div className="stats-grid-4">
            <div className="glass-card" style={{ padding: "1.25rem" }}>
              <div style={{ fontSize: "0.76rem", color: "#64748b", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.4rem" }}>Selected</div>
              <div style={{ fontSize: "2rem", fontWeight: 800, color: "#fff", fontFamily: "var(--font-mono)" }}>{report.selected_count}</div>
              <div style={{ fontSize: "0.75rem", color: "var(--accent-cyan)", marginTop: "0.2rem" }}>of {report.candidate_count} candidates</div>
            </div>
            <div className="glass-card" style={{ padding: "1.25rem" }}>
              <div style={{ fontSize: "0.76rem", color: "#64748b", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.4rem" }}>Entities</div>
              <div style={{ fontSize: "2rem", fontWeight: 800, color: "#fff", fontFamily: "var(--font-mono)" }}>{report.coverage?.cses_represented}/{report.coverage?.cses_total}</div>
              <div style={{ fontSize: "0.75rem", color: "#34d399", marginTop: "0.2rem" }}>CSEs represented</div>
            </div>
            <div className="glass-card" style={{ padding: "1.25rem" }}>
              <div style={{ fontSize: "0.76rem", color: "#64748b", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.4rem" }}>Finding Types</div>
              <div style={{ fontSize: "2rem", fontWeight: 800, color: "#fff", fontFamily: "var(--font-mono)" }}>{report.coverage?.finding_types_represented}/{report.coverage?.finding_types_total}</div>
              <div style={{ fontSize: "0.75rem", color: "#818cf8", marginTop: "0.2rem" }}>types covered</div>
            </div>
            <div className="glass-card" style={{ padding: "1.25rem" }}>
              <div style={{ fontSize: "0.76rem", color: "#64748b", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.4rem" }}>Control</div>
              <div style={{ fontSize: "2rem", fontWeight: 800, color: "#fff", fontFamily: "var(--font-mono)" }}>{report.coverage?.control_samples}</div>
              <div style={{ fontSize: "0.75rem", color: "#a78bfa", marginTop: "0.2rem" }}>bias-detection samples</div>
            </div>
          </div>

          {/* Selected Items */}
          <div className="glass-card" style={{ padding: "1.65rem" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1.25rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <ShieldCheck size={18} color="var(--accent-cyan)" />
                <h3 style={{ fontSize: "1.05rem", color: "#fff", fontWeight: 700, margin: 0 }}>
                  Optimized Review Sample
                </h3>
              </div>
              <span style={{ fontSize: "0.73rem", color: "#64748b", fontFamily: "var(--font-mono)" }}>
                Seed: {report.selection_seed}
              </span>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              {report.selected_items?.map((item: any) => {
                const matchingFinding = findings.find((f) => f.finding_id === item.finding_id);
                return (
                  <div
                    key={item.finding_id}
                    onClick={() => matchingFinding && onSelectFinding(matchingFinding)}
                    className="glass-card-interactive"
                    style={{
                      padding: "1rem 1.25rem",
                      borderRadius: "var(--radius-md)",
                      background: item.is_control_sample
                        ? "rgba(139, 92, 246, 0.06)"
                        : "rgba(15, 23, 42, 0.55)",
                      border: `1px solid ${item.is_control_sample ? "rgba(139, 92, 246, 0.3)" : "var(--border-subtle)"}`,
                      cursor: matchingFinding ? "pointer" : "default",
                      display: "flex",
                      flexDirection: "column",
                      gap: "0.65rem",
                    }}
                  >
                    {/* Top row: rank + type + reasons */}
                    <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
                      <span style={{ fontSize: "0.78rem", fontWeight: 800, color: "var(--accent-cyan)", fontFamily: "var(--font-mono)", minWidth: "28px" }}>
                        #{item.selection_rank}
                      </span>
                      <span style={{
                        fontSize: "0.72rem", fontWeight: 700, padding: "0.15rem 0.55rem",
                        borderRadius: "var(--radius-sm)", background: "rgba(0,216,246,0.1)",
                        border: "1px solid rgba(0,216,246,0.3)", color: "var(--accent-cyan)",
                        textTransform: "uppercase", letterSpacing: "0.04em",
                      }}>
                        {item.finding_type?.replace(/_/g, " ")}
                      </span>
                      {item.selection_reasons?.map((reason: string, ri: number) => {
                        const badge = getReasonBadge(reason);
                        return (
                          <span
                            key={ri}
                            style={{
                              fontSize: "0.68rem", fontWeight: 700, padding: "0.12rem 0.45rem",
                              borderRadius: "var(--radius-sm)", background: badge.style.bg,
                              border: `1px solid ${badge.style.border}`, color: badge.style.text,
                              textTransform: "uppercase", letterSpacing: "0.03em",
                            }}
                          >
                            {badge.label}
                          </span>
                        );
                      })}
                    </div>

                    {/* Middle: explanation */}
                    <div style={{ fontSize: "0.82rem", color: "#94a3b8", lineHeight: 1.4 }}>
                      {item.selection_reasons?.map((r: string) => r).join(" • ")}
                    </div>

                    {/* Bottom: scores */}
                    <div style={{ display: "flex", gap: "1.5rem", fontSize: "0.75rem", color: "#64748b", flexWrap: "wrap" }}>
                      <span>Priority: <strong style={{ color: "#fff" }}>{item.priority_score?.toFixed(3)}</strong></span>
                      <span>Confidence: <strong style={{ color: "#fff" }}>{item.evidentiary_confidence?.toFixed(2)}</strong></span>
                      <span>Evidence: <strong style={{ color: "#fff" }}>{item.evidence_record_count} records</strong></span>
                      <span>Marginal: <strong style={{ color: "var(--accent-cyan)" }}>{item.marginal_value?.toFixed(3)}</strong></span>
                      {matchingFinding && (
                        <span style={{ marginLeft: "auto", color: "var(--accent-cyan)", cursor: "pointer", display: "flex", alignItems: "center", gap: "0.25rem" }}>
                          Examine <ArrowRight size={13} />
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Coverage Breakdown */}
          <div className="glass-card" style={{ padding: "1.35rem" }}>
            <h4 style={{ fontSize: "0.9rem", color: "#fff", fontWeight: 700, marginBottom: "0.75rem", display: "flex", alignItems: "center", gap: "0.4rem" }}>
              <BarChart3 size={16} color="var(--accent-cyan)" /> Sample Coverage Analysis
            </h4>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem" }}>
              <div>
                <div style={{ fontSize: "0.76rem", color: "#64748b", marginBottom: "0.3rem" }}>Entity Coverage</div>
                <div style={{ fontSize: "0.9rem", color: "#fff" }}>
                  {report.coverage?.cses_represented} of {report.coverage?.cses_total} CSEs
                </div>
                <div style={{ height: "4px", background: "rgba(255,255,255,0.08)", borderRadius: "2px", marginTop: "0.4rem" }}>
                  <div style={{ height: "100%", width: `${report.coverage?.cses_total > 0 ? (report.coverage.cses_represented / report.coverage.cses_total) * 100 : 0}%`, background: "#34d399", borderRadius: "2px" }} />
                </div>
              </div>
              <div>
                <div style={{ fontSize: "0.76rem", color: "#64748b", marginBottom: "0.3rem" }}>Period Coverage</div>
                <div style={{ fontSize: "0.9rem", color: "#fff" }}>
                  {report.coverage?.periods_represented} of {report.coverage?.periods_total} periods
                </div>
                <div style={{ height: "4px", background: "rgba(255,255,255,0.08)", borderRadius: "2px", marginTop: "0.4rem" }}>
                  <div style={{ height: "100%", width: `${report.coverage?.periods_total > 0 ? (report.coverage.periods_represented / report.coverage.periods_total) * 100 : 0}%`, background: "#818cf8", borderRadius: "2px" }} />
                </div>
              </div>
              <div>
                <div style={{ fontSize: "0.76rem", color: "#64748b", marginBottom: "0.3rem" }}>Type Coverage</div>
                <div style={{ fontSize: "0.9rem", color: "#fff" }}>
                  {report.coverage?.finding_types_represented} of {report.coverage?.finding_types_total} types
                </div>
                <div style={{ height: "4px", background: "rgba(255,255,255,0.08)", borderRadius: "2px", marginTop: "0.4rem" }}>
                  <div style={{ height: "100%", width: `${report.coverage?.finding_types_total > 0 ? (report.coverage.finding_types_represented / report.coverage.finding_types_total) * 100 : 0}%`, background: "var(--accent-cyan)", borderRadius: "2px" }} />
                </div>
              </div>
            </div>
          </div>
        </>
      )}

      {/* No-finding state */}
      {!report && !loading && !error && (
        <div className="glass-card" style={{ padding: "3rem", textAlign: "center" }}>
          <Target size={48} color="#334155" style={{ margin: "0 auto 1rem" }} />
          <p style={{ fontSize: "0.95rem", color: "#64748b", fontWeight: 600 }}>
            Configure your review budget and click "Optimize Sample" to generate a supervisory review selection.
          </p>
          <p style={{ fontSize: "0.82rem", color: "#475569", marginTop: "0.5rem" }}>
            The optimizer recommends a diverse sample — the human supervisor remains the decision-maker.
          </p>
        </div>
      )}
    </div>
  );
};

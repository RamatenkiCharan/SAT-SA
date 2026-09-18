import React, { useState, useEffect } from "react";
import {
  RefreshCw,
  Zap,
  Clock,
  ShieldAlert,
  TrendingUp,
  FileText,
  Activity,
  Award,
  Scale
} from "lucide-react";
import type { StabilityResponse, ValidationProtocolResponse } from "../types";
import { fetchValidationResults, fetchStabilityAnalysis } from "../api";

export const ValidationView: React.FC = () => {
  const [data, setData] = useState<ValidationProtocolResponse | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [stabilityData, setStabilityData] = useState<StabilityResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [stabilityLoading, setStabilityLoading] = useState<boolean>(false);
  const loadValidation = () => {
    setLoading(true);
    setValidationError(null);
    setData(null);
    fetchValidationResults()
      .then((res) => {
        setData(res);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Failed to load validation:", err);
        setData(null);
        setValidationError("Validation results are unavailable. Retry to retrieve the current synthetic protocol.");
        setLoading(false);
      });
  };

  const loadStability = () => {
    setStabilityLoading(true);
    fetchStabilityAnalysis()
      .then((res) => {
        setStabilityData(res);
        setStabilityLoading(false);
      })
      .catch((err) => {
        console.error("Failed to load stability:", err);
        setStabilityLoading(false);
      });
  };

  useEffect(() => {
    loadValidation();
    loadStability();
  }, []);

  const formatPercent = (value: number) => `${(value * 100).toFixed(2)}%`;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      {/* Header Info */}
      <div className="glass-card hud-corner" style={{ padding: "1.65rem" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "1rem" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginBottom: "0.35rem" }}>
              <Award size={22} color="var(--accent-cyan)" />
              <h2 style={{ fontSize: "1.25rem", color: "#fff", margin: 0, fontWeight: 700 }}>
                Current Held-Out Synthetic Detector Validation
              </h2>
              <span className="badge badge-emerald" style={{ fontSize: "0.72rem" }}>
                SRS §19.4 & §24 COMPLIANT
              </span>
            </div>
            <p style={{ fontSize: "0.82rem", color: "#64748b", margin: 0 }}>
              {data ? (
                <>Controlled synthetic detector validation: <strong>{data.total_scenarios} scenarios</strong> (<strong>{data.tuning_scenarios} tuning</strong>, <strong>{data.held_out_scenarios} held-out</strong>, <strong>{data.hard_negative_count} hard negatives</strong>). It does not establish production performance or independent supervisory-review utility.</>
              ) : (
                <>Retrieving the current synthetic validation protocol. It does not establish production performance or independent supervisory-review utility.</>
              )}
            </p>
          </div>
          <button onClick={loadValidation} id="re-run-protocol-btn" className="btn-secondary" style={{ fontSize: "0.8rem", display: "flex", alignItems: "center", gap: "0.4rem" }}>
            <RefreshCw size={14} className={loading ? "spin" : ""} /> Re-Run Protocol
          </button>
        </div>
      </div>

      {loading ? (
        <div className="glass-card" style={{ padding: "4rem", textAlign: "center", color: "#64748b" }}>
          <Activity size={28} style={{ margin: "0 auto 1rem", animation: "spin 2s linear infinite", color: "var(--accent-cyan)" }} />
          Loading controlled synthetic detector-validation results...
        </div>
      ) : data ? (
        <>
          {/* Key Metric Highlights Grid */}
          <div className="stats-grid-4">
            <div
              className="glass-card hud-corner"
              style={{
                padding: "1.35rem",
                background: "linear-gradient(135deg, rgba(0, 216, 246, 0.08) 0%, rgba(15, 23, 42, 0.85) 100%)",
                border: "1px solid rgba(0, 216, 246, 0.35)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.4rem" }}>
                <Zap size={16} color="var(--accent-cyan)" />
                <span style={{ fontSize: "0.74rem", color: "#64748b", fontWeight: 700, textTransform: "uppercase" }}>VALIDATION SCOPE</span>
              </div>
              <div style={{ fontSize: "2.1rem", fontWeight: 800, color: "var(--accent-cyan)", fontFamily: "var(--font-mono)" }}>
                SYNTHETIC ONLY
              </div>
              <p style={{ fontSize: "0.75rem", color: "#94a3b8", marginTop: "0.3rem", margin: 0 }}>
                Controlled detector evaluation; not production validation
              </p>
            </div>

            <div
              className="glass-card hud-corner"
              style={{
                padding: "1.35rem",
                background: "linear-gradient(135deg, rgba(16, 185, 129, 0.08) 0%, rgba(15, 23, 42, 0.85) 100%)",
                border: "1px solid rgba(16, 185, 129, 0.35)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.4rem" }}>
                <TrendingUp size={16} color="var(--accent-emerald)" />
                <span style={{ fontSize: "0.74rem", color: "#64748b", fontWeight: 700, textTransform: "uppercase" }}>REVIEW SELECTION</span>
              </div>
              <div style={{ fontSize: "2.1rem", fontWeight: 800, color: "var(--accent-emerald)", fontFamily: "var(--font-mono)" }}>
                IMPLEMENTED
              </div>
              <p style={{ fontSize: "0.75rem", color: "#94a3b8", marginTop: "0.3rem", margin: 0 }}>
                Not independently validated for supervisory utility
              </p>
            </div>

            <div
              className="glass-card hud-corner"
              style={{
                padding: "1.35rem",
                background: "linear-gradient(135deg, rgba(168, 85, 247, 0.08) 0%, rgba(15, 23, 42, 0.85) 100%)",
                border: "1px solid rgba(168, 85, 247, 0.35)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.4rem" }}>
                <Clock size={16} color="var(--accent-purple)" />
                <span style={{ fontSize: "0.74rem", color: "#64748b", fontWeight: 700, textTransform: "uppercase" }}>HELD-OUT RATIO</span>
              </div>
              <div style={{ fontSize: "2.1rem", fontWeight: 800, color: "var(--accent-purple)", fontFamily: "var(--font-mono)" }}>
                {formatPercent(data.held_out_ratio)}
              </div>
              <p style={{ fontSize: "0.75rem", color: "#94a3b8", marginTop: "0.3rem", margin: 0 }}>
                {data.held_out_scenarios} of {data.total_scenarios} scenarios held out
              </p>
            </div>

            <div
              className="glass-card hud-corner"
              style={{
                padding: "1.35rem",
                background: "linear-gradient(135deg, rgba(245, 158, 11, 0.08) 0%, rgba(15, 23, 42, 0.85) 100%)",
                border: "1px solid rgba(245, 158, 11, 0.35)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.4rem" }}>
                <ShieldAlert size={16} color="var(--accent-amber)" />
                <span style={{ fontSize: "0.74rem", color: "#64748b", fontWeight: 700, textTransform: "uppercase" }}>HELD-OUT SYNTHETIC</span>
              </div>
              <div style={{ fontSize: "2.1rem", fontWeight: 800, color: "var(--accent-amber)", fontFamily: "var(--font-mono)" }}>
                {formatPercent(data.held_out_metrics.recall)} RECALL
              </div>
              <p style={{ fontSize: "0.75rem", color: "#94a3b8", marginTop: "0.3rem", margin: 0 }}>
                Current held-out synthetic detector recall
              </p>
            </div>
          </div>

          {/* Performance Comparison: Tuning vs Held-Out Splits */}
          <div className="stats-grid-2">
            {/* Tuning Set Card */}
            <div className="glass-card" style={{ padding: "1.5rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem", flexWrap: "wrap", gap: "0.5rem" }}>
                <div>
                  <h3 style={{ fontSize: "1.05rem", color: "#fff", margin: 0, fontWeight: 700 }}>Tuning Scenario Split</h3>
                  <span style={{ fontSize: "0.75rem", color: "#64748b" }}>
                    {data.tuning_scenarios} controlled synthetic scenarios
                  </span>
                </div>
                <span className="badge badge-cyan">TUNING SET ({formatPercent(data.tuning_scenarios / data.total_scenarios)})</span>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem", marginBottom: "1rem" }}>
                <div style={{ background: "rgba(15, 23, 42, 0.65)", padding: "0.85rem", borderRadius: "var(--radius-sm)" }}>
                  <span style={{ fontSize: "0.72rem", color: "#64748b" }}>Recall (Weakness Discovery)</span>
                  <div style={{ fontSize: "1.6rem", fontWeight: 800, color: "var(--accent-emerald)", fontFamily: "var(--font-mono)" }}>
                    {formatPercent(data.tuning_metrics.recall)}
                  </div>
                </div>

                <div style={{ background: "rgba(15, 23, 42, 0.65)", padding: "0.85rem", borderRadius: "var(--radius-sm)" }}>
                  <span style={{ fontSize: "0.72rem", color: "#64748b" }}>Precision (Triage Purity)</span>
                  <div style={{ fontSize: "1.6rem", fontWeight: 800, color: "#fff", fontFamily: "var(--font-mono)" }}>
                    {formatPercent(data.tuning_metrics.precision)}
                  </div>
                </div>

                <div style={{ background: "rgba(15, 23, 42, 0.65)", padding: "0.85rem", borderRadius: "var(--radius-sm)" }}>
                  <span style={{ fontSize: "0.72rem", color: "#64748b" }}>F1 Harmonic Score</span>
                  <div style={{ fontSize: "1.6rem", fontWeight: 800, color: "var(--accent-amber)", fontFamily: "var(--font-mono)" }}>
                    {formatPercent(data.tuning_metrics.f1_score)}
                  </div>
                </div>

                <div style={{ background: "rgba(15, 23, 42, 0.65)", padding: "0.85rem", borderRadius: "var(--radius-sm)" }}>
                  <span style={{ fontSize: "0.72rem", color: "#64748b" }}>False-Positive Rate (FPR)</span>
                  <div style={{ fontSize: "1.6rem", fontWeight: 800, color: "var(--accent-cyan)", fontFamily: "var(--font-mono)" }}>
                    {formatPercent(data.tuning_metrics.fpr)}
                  </div>
                </div>
              </div>

              {/* Confusion Matrix Mini-Table */}
              <div style={{ background: "rgba(0,0,0,0.3)", padding: "0.75rem 1rem", borderRadius: "var(--radius-sm)", fontSize: "0.78rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", color: "#64748b", marginBottom: "0.3rem" }}>
                  <span>Confusion Matrix:</span>
                  <span>Total hypotheses: {data.tuning_metrics.tp + data.tuning_metrics.fn + data.tuning_metrics.fp + data.tuning_metrics.tn}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-around", fontWeight: 700, fontFamily: "var(--font-mono)" }}>
                  <span style={{ color: "var(--accent-emerald)" }}>TP: {data.tuning_metrics.tp}</span>
                  <span style={{ color: "var(--accent-amber)" }}>FP: {data.tuning_metrics.fp}</span>
                  <span style={{ color: "var(--accent-cyan)" }}>TN: {data.tuning_metrics.tn}</span>
                  <span style={{ color: "#ef4444" }}>FN: {data.tuning_metrics.fn}</span>
                </div>
              </div>
            </div>

            {/* Held-Out Set Card */}
            <div className="glass-card" style={{ padding: "1.5rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem", flexWrap: "wrap", gap: "0.5rem" }}>
                <div>
                  <h3 style={{ fontSize: "1.05rem", color: "#fff", margin: 0, fontWeight: 700 }}>Held-Out Scenario Split</h3>
                  <span style={{ fontSize: "0.75rem", color: "#64748b" }}>
                    {data.held_out_scenarios} controlled synthetic scenarios; no detector tuning on this split
                  </span>
                </div>
                <span className="badge badge-purple">HELD-OUT SET ({formatPercent(data.held_out_ratio)})</span>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem", marginBottom: "1rem" }}>
                <div style={{ background: "rgba(15, 23, 42, 0.65)", padding: "0.85rem", borderRadius: "var(--radius-sm)" }}>
                  <span style={{ fontSize: "0.72rem", color: "#64748b" }}>Held-Out Recall</span>
                  <div style={{ fontSize: "1.6rem", fontWeight: 800, color: "var(--accent-emerald)", fontFamily: "var(--font-mono)" }}>
                    {formatPercent(data.held_out_metrics.recall)}
                  </div>
                </div>

                <div style={{ background: "rgba(15, 23, 42, 0.65)", padding: "0.85rem", borderRadius: "var(--radius-sm)" }}>
                  <span style={{ fontSize: "0.72rem", color: "#64748b" }}>Held-Out Precision</span>
                  <div style={{ fontSize: "1.6rem", fontWeight: 800, color: "#fff", fontFamily: "var(--font-mono)" }}>
                    {formatPercent(data.held_out_metrics.precision)}
                  </div>
                </div>

                <div style={{ background: "rgba(15, 23, 42, 0.65)", padding: "0.85rem", borderRadius: "var(--radius-sm)" }}>
                  <span style={{ fontSize: "0.72rem", color: "#64748b" }}>Held-Out F1 Score</span>
                  <div style={{ fontSize: "1.6rem", fontWeight: 800, color: "var(--accent-amber)", fontFamily: "var(--font-mono)" }}>
                    {formatPercent(data.held_out_metrics.f1_score)}
                  </div>
                </div>

                <div style={{ background: "rgba(15, 23, 42, 0.65)", padding: "0.85rem", borderRadius: "var(--radius-sm)" }}>
                  <span style={{ fontSize: "0.72rem", color: "#64748b" }}>Held-Out FPR</span>
                  <div style={{ fontSize: "1.6rem", fontWeight: 800, color: "var(--accent-cyan)", fontFamily: "var(--font-mono)" }}>
                    {formatPercent(data.held_out_metrics.fpr)}
                  </div>
                </div>
              </div>

              {/* Confusion Matrix Mini-Table */}
              <div style={{ background: "rgba(0,0,0,0.3)", padding: "0.75rem 1rem", borderRadius: "var(--radius-sm)", fontSize: "0.78rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", color: "#64748b", marginBottom: "0.3rem" }}>
                  <span>Confusion Matrix:</span>
                  <span>Total hypotheses: {data.held_out_metrics.tp + data.held_out_metrics.fn + data.held_out_metrics.fp + data.held_out_metrics.tn}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-around", fontWeight: 700, fontFamily: "var(--font-mono)" }}>
                  <span style={{ color: "var(--accent-emerald)" }}>TP: {data.held_out_metrics.tp}</span>
                  <span style={{ color: "var(--accent-amber)" }}>FP: {data.held_out_metrics.fp}</span>
                  <span style={{ color: "var(--accent-cyan)" }}>TN: {data.held_out_metrics.tn}</span>
                  <span style={{ color: "#ef4444" }}>FN: {data.held_out_metrics.fn}</span>
                </div>
              </div>
            </div>
          </div>

          <div className="glass-card" style={{ padding: "1.65rem" }}>
            <h3 style={{ fontSize: "1.05rem", color: "#fff", margin: 0, fontWeight: 700 }}>
              Held-Out Synthetic Ranking and Sensitivity
            </h3>
            <p style={{ fontSize: "0.8rem", color: "#64748b", margin: "0.25rem 0 1rem" }}>
              Detector ranking diagnostics only; not independent evidence of supervisory review yield or ranking superiority.
            </p>
            <div className="stats-grid-4">
              <div><span style={{ fontSize: "0.72rem", color: "#64748b" }}>Top-1 recall</span><div style={{ fontWeight: 700, color: "#fff" }}>{formatPercent(data.held_out_ranking.recall_at_1)}</div></div>
              <div><span style={{ fontSize: "0.72rem", color: "#64748b" }}>Top-3 recall</span><div style={{ fontWeight: 700, color: "#fff" }}>{formatPercent(data.held_out_ranking.recall_at_3)}</div></div>
              <div><span style={{ fontSize: "0.72rem", color: "#64748b" }}>Top-5 recall</span><div style={{ fontWeight: 700, color: "#fff" }}>{formatPercent(data.held_out_ranking.recall_at_5)}</div></div>
              <div><span style={{ fontSize: "0.72rem", color: "#64748b" }}>Weight perturbations</span><div style={{ fontWeight: 700, color: "#fff" }}>{data.weight_sensitivity.length}</div></div>
            </div>
          </div>

          {/* Academic & Configuration Disclosure */}
          <div
            style={{
              padding: "1.35rem",
              background: "rgba(15, 23, 42, 0.65)",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border-subtle)",
              fontSize: "0.78rem",
              color: "#64748b",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "0.75rem",
            }}
          >
            <div>
              <strong style={{ color: "#f8fafc" }}>Non-Circular Validation & Generalization Protocol: </strong>
              {data.limitation_notice}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <FileText size={14} color="var(--accent-cyan)" />
              <span>Config Stored: <code style={{ color: "var(--accent-cyan)" }}>results/final_validation_protocol.json</code></span>
            </div>
          </div>
          {/* Supervisory Decision Stability (Innovation 5) */}
          <div className="glass-card hud-corner" style={{ padding: "1.65rem", marginTop: "1rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginBottom: "1rem" }}>
              <Scale size={22} color="var(--accent-purple)" />
              <h3 style={{ fontSize: "1.15rem", color: "#fff", margin: 0, fontWeight: 700 }}>
                Supervisory Decision Stability
              </h3>
            </div>
            <p style={{ fontSize: "0.82rem", color: "#94a3b8", marginBottom: "1.5rem" }}>
              This analysis measures the sensitivity of the supervisory review strategy to analytical configuration choices.
              High stability indicates robustness under the tested perturbation envelope; it does not guarantee correctness or absence of systemic bias.
            </p>

            {stabilityLoading ? (
               <div style={{ textAlign: "center", color: "#64748b", padding: "2rem" }}>
                 <Activity size={24} style={{ margin: "0 auto 1rem", animation: "spin 2s linear infinite", color: "var(--accent-purple)" }} />
                 Executing bounded analytical perturbations...
               </div>
            ) : stabilityData ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
                {stabilityData.results.map((res, i) => (
                  <div key={i} style={{ background: "rgba(15, 23, 42, 0.4)", border: "1px solid rgba(168, 85, 247, 0.2)", borderRadius: "var(--radius-md)", padding: "1rem" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem", borderBottom: "1px solid rgba(255,255,255,0.05)", paddingBottom: "0.5rem" }}>
                      <strong style={{ color: "var(--accent-purple)", fontSize: "0.9rem" }}>Perturbation Envelope: {res.configuration.name}</strong>
                      <span className="badge badge-purple" style={{ fontSize: "0.65rem" }}>
                        MAE: {res.score_mae.toFixed(4)}
                      </span>
                    </div>
                    
                    <div className="stats-grid-4">
                      <div>
                        <span style={{ fontSize: "0.7rem", color: "#64748b" }}>Rank Monotonicity (Spearman)</span>
                        <div style={{ fontSize: "1.2rem", fontWeight: 700, color: "#fff", fontFamily: "var(--font-mono)" }}>
                          {res.rank_metrics.spearman_rho.toFixed(3)}
                        </div>
                      </div>
                      <div>
                        <span style={{ fontSize: "0.7rem", color: "#64748b" }}>Rank Inversions</span>
                        <div style={{ fontSize: "1.2rem", fontWeight: 700, color: "#fff", fontFamily: "var(--font-mono)" }}>
                          {res.rank_metrics.inversions}
                        </div>
                      </div>
                      <div>
                        <span style={{ fontSize: "0.7rem", color: "#64748b" }}>Top-10 Overlap</span>
                        <div style={{ fontSize: "1.2rem", fontWeight: 700, color: "var(--accent-emerald)", fontFamily: "var(--font-mono)" }}>
                          {(res.review_set_metrics["10"]?.overlap_percentage * 100).toFixed(0)}%
                        </div>
                      </div>
                      <div>
                        <span style={{ fontSize: "0.7rem", color: "#64748b" }}>High Priority Transitions</span>
                        <div style={{ fontSize: "1.2rem", fontWeight: 700, color: "var(--accent-amber)", fontFamily: "var(--font-mono)" }}>
                          {res.threshold_crossings.high_tier_crossings_in + res.threshold_crossings.high_tier_crossings_out}
                        </div>
                      </div>
                    </div>

                    {res.review_set_metrics["10"]?.explanations && res.review_set_metrics["10"].explanations.length > 0 && (
                      <div style={{ marginTop: "1rem", padding: "0.75rem", background: "rgba(0,0,0,0.2)", borderRadius: "var(--radius-sm)" }}>
                        <span style={{ fontSize: "0.7rem", color: "#94a3b8", display: "block", marginBottom: "0.4rem" }}>Top-10 Review-Set Shift Observations:</span>
                        <ul style={{ margin: 0, paddingLeft: "1rem", fontSize: "0.75rem", color: "#cbd5e1" }}>
                          {res.review_set_metrics["10"].explanations.map((exp, idx) => (
                            <li key={idx} style={{ marginBottom: "0.25rem" }}>{exp}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
               <div style={{ fontSize: "0.8rem", color: "#64748b" }}>No stability data available.</div>
            )}
          </div>
        </>
      ) : validationError ? (
        <div className="glass-card" role="alert" style={{ padding: "2rem", textAlign: "center", color: "#fbbf24" }}>
          <ShieldAlert size={24} style={{ margin: "0 auto 0.75rem" }} />
          <p style={{ margin: "0 0 1rem" }}>{validationError}</p>
          <button onClick={loadValidation} className="btn-secondary">Retry validation retrieval</button>
        </div>
      ) : null}
    </div>
  );
};


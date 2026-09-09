import React, { useState, useEffect } from "react";
import {
  X,
  Send,
} from "lucide-react";
import type { Finding, FindingDetail, ReviewDecisionState } from "../types";
import { fetchFindingDetail, submitReviewDecision } from "../api";

interface FindingDetailModalProps {
  finding: Finding;
  onClose: () => void;
  onReviewSubmitted: () => void;
}

export const FindingDetailModal: React.FC<FindingDetailModalProps> = ({
  finding,
  onClose,
  onReviewSubmitted,
}) => {
  const [detail, setDetail] = useState<FindingDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [activeEvidenceTab, setActiveEvidenceTab] = useState<string>("alerts");
  const [decision, setDecision] = useState<ReviewDecisionState>(
    finding.review_status || "CONFIRMED"
  );
  const [notes, setNotes] = useState<string>(finding.review_notes || "");
  const [submitting, setSubmitting] = useState<boolean>(false);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    fetchFindingDetail(finding.finding_id)
      .then((data) => {
        if (isMounted) {
          setDetail(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        console.error("Failed to load finding details:", err);
        setLoading(false);
      });
    return () => {
      isMounted = false;
    };
  }, [finding.finding_id]);

  const handleSubmitReview = async () => {
    setSubmitting(true);
    try {
      await submitReviewDecision(finding.finding_id, decision, notes);
      onReviewSubmitted();
      onClose();
    } catch (err) {
      alert("Failed to submit review decision: " + String(err));
    } finally {
      setSubmitting(false);
    }
  };

  const dq = finding.data_quality_breakdown;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        
        {/* Modal Header */}
        <div
          style={{
            padding: "1.5rem",
            borderBottom: "1px solid var(--border-subtle)",
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            background: "rgba(15, 23, 42, 0.95)",
            position: "sticky",
            top: 0,
            zIndex: 10,
          }}
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginBottom: "0.4rem" }}>
              <span className={`badge badge-${finding.priority_label.toLowerCase()}`}>
                {finding.priority_label} PRIORITY
              </span>
              <span className="badge badge-purple">{finding.finding_type}</span>
              <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                ID: <code className="font-mono">{finding.finding_id.slice(0, 8)}</code>
              </span>
            </div>
            <h2 style={{ fontSize: "1.35rem", color: "#fff" }}>{finding.title}</h2>
            <p style={{ fontSize: "0.85rem", color: "var(--accent-cyan)", marginTop: "0.2rem" }}>
              Entity: <strong>{finding.cse_name}</strong> • Sector: <strong>{finding.sector}</strong>
            </p>
          </div>

          <button
            onClick={onClose}
            style={{
              background: "transparent",
              border: "none",
              color: "var(--text-muted)",
              cursor: "pointer",
              padding: "0.4rem",
              borderRadius: "var(--radius-sm)",
            }}
          >
            <X size={22} />
          </button>
        </div>

        {/* Modal Body */}
        <div style={{ padding: "1.5rem", display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          
          {/* Section 1: Template-Grounded Rationale */}
          <div
            style={{
              background: "rgba(30, 41, 59, 0.4)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              padding: "1.25rem",
            }}
          >
            <h4 style={{ fontSize: "0.85rem", color: "var(--accent-cyan)", textTransform: "uppercase", marginBottom: "0.75rem" }}>
              Supervisory Analytical Rationale (Non-Generative Template Grounded)
            </h4>

            <p style={{ fontSize: "0.95rem", color: "#fff", marginBottom: "1rem", lineHeight: 1.5 }}>
              {finding.headline}
            </p>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1rem" }}>
              <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "0.85rem", borderRadius: "var(--radius-sm)" }}>
                <div style={{ fontSize: "0.75rem", color: "var(--accent-emerald)", fontWeight: 600, marginBottom: "0.3rem" }}>
                  EXPECTED OPERATIONAL BEHAVIOR
                </div>
                <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}>
                  {finding.expected_behavior}
                </p>
              </div>

              <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "0.85rem", borderRadius: "var(--radius-sm)" }}>
                <div style={{ fontSize: "0.75rem", color: "var(--accent-crimson)", fontWeight: 600, marginBottom: "0.3rem" }}>
                  OBSERVED EVIDENCE
                </div>
                <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}>
                  {finding.observed_behavior}
                </p>
              </div>
            </div>

            {/* Supporting & Contradicting Signals */}
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              <div style={{ fontSize: "0.78rem", fontWeight: 600, color: "var(--text-muted)" }}>
                CONTRIBUTING SUPPORTING SIGNALS:
              </div>
              <ul style={{ paddingLeft: "1.25rem", fontSize: "0.82rem", color: "var(--text-secondary)" }}>
                {finding.supporting_signals.map((sig, idx) => (
                  <li key={idx} style={{ marginBottom: "0.25rem" }}>{sig}</li>
                ))}
              </ul>

              {finding.contradicting_signals && finding.contradicting_signals.length > 0 && (
                <>
                  <div style={{ fontSize: "0.78rem", fontWeight: 600, color: "var(--accent-amber)", marginTop: "0.4rem" }}>
                    CONTRADICTING / LIMITING SIGNALS:
                  </div>
                  <ul style={{ paddingLeft: "1.25rem", fontSize: "0.82rem", color: "var(--text-secondary)" }}>
                    {finding.contradicting_signals.map((sig, idx) => (
                      <li key={idx}>{sig}</li>
                    ))}
                  </ul>
                </>
              )}
            </div>

            {/* Recommended Action */}
            <div style={{ marginTop: "1rem", padding: "0.75rem", background: "rgba(0, 240, 255, 0.05)", border: "1px solid rgba(0, 240, 255, 0.2)", borderRadius: "var(--radius-sm)" }}>
              <strong style={{ fontSize: "0.8rem", color: "var(--accent-cyan)" }}>Recommended Supervisory Action: </strong>
              <span style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}>{finding.recommended_action}</span>
            </div>
          </div>

          {/* Section 2: Data Quality & Uncertainty Decomposed Gauges (§7.2.1) */}
          <div
            style={{
              background: "rgba(30, 41, 59, 0.4)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              padding: "1.25rem",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
              <h4 style={{ fontSize: "0.85rem", color: "var(--accent-cyan)", textTransform: "uppercase" }}>
                Data Trust Breakdown (§7.2.1 Formula)
              </h4>
              <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "#fff" }}>
                Overall Data Quality: {dq.overall_score}%
              </span>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "1rem" }}>
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", marginBottom: "0.25rem" }}>
                  <span style={{ color: "var(--text-muted)" }}>Completeness (35%)</span>
                  <span style={{ color: "#fff" }}>{dq.completeness}%</span>
                </div>
                <div className="progress-container">
                  <div className="progress-bar" style={{ width: `${dq.completeness}%`, background: "var(--accent-cyan)" }}></div>
                </div>
              </div>

              <div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", marginBottom: "0.25rem" }}>
                  <span style={{ color: "var(--text-muted)" }}>Consistency (25%)</span>
                  <span style={{ color: "#fff" }}>{dq.consistency}%</span>
                </div>
                <div className="progress-container">
                  <div className="progress-bar" style={{ width: `${dq.consistency}%`, background: "var(--accent-blue)" }}></div>
                </div>
              </div>

              <div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", marginBottom: "0.25rem" }}>
                  <span style={{ color: "var(--text-muted)" }}>Coverage (25%)</span>
                  <span style={{ color: "#fff" }}>{dq.coverage}%</span>
                </div>
                <div className="progress-container">
                  <div className="progress-bar" style={{ width: `${dq.coverage}%`, background: "var(--accent-purple)" }}></div>
                </div>
              </div>

              <div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", marginBottom: "0.25rem" }}>
                  <span style={{ color: "var(--text-muted)" }}>Sufficiency (15%)</span>
                  <span style={{ color: "#fff" }}>{dq.sample_sufficiency}%</span>
                </div>
                <div className="progress-container">
                  <div className="progress-bar" style={{ width: `${dq.sample_sufficiency}%`, background: "var(--accent-emerald)" }}></div>
                </div>
              </div>
            </div>
          </div>

          {/* Section 3: Clickable Evidence Records Drill-Down */}
          <div
            style={{
              background: "rgba(30, 41, 59, 0.4)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              padding: "1.25rem",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
              <h4 style={{ fontSize: "0.85rem", color: "var(--accent-cyan)", textTransform: "uppercase" }}>
                Underlying Evidence Records ({finding.evidence_record_count} Linked Items)
              </h4>
              <div style={{ display: "flex", gap: "0.4rem" }}>
                {["alerts", "cases", "investigations", "escalations", "actions", "closures"].map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setActiveEvidenceTab(tab)}
                    style={{
                      background: activeEvidenceTab === tab ? "rgba(0, 240, 255, 0.15)" : "transparent",
                      color: activeEvidenceTab === tab ? "var(--accent-cyan)" : "var(--text-muted)",
                      border: "none",
                      padding: "0.3rem 0.6rem",
                      borderRadius: "var(--radius-sm)",
                      fontSize: "0.75rem",
                      fontWeight: 600,
                      cursor: "pointer",
                      textTransform: "capitalize",
                    }}
                  >
                    {tab}
                  </button>
                ))}
              </div>
            </div>

            {loading ? (
              <div style={{ padding: "1.5rem", textAlign: "center", color: "var(--text-muted)", fontSize: "0.85rem" }}>
                Loading verified evidence records...
              </div>
            ) : detail?.evidence_records ? (
              <div style={{ maxHeight: "250px", overflowY: "auto" }}>
                
                {activeEvidenceTab === "alerts" && (
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.78rem" }}>
                    <thead>
                      <tr style={{ borderBottom: "1px solid var(--border-subtle)", color: "var(--text-muted)", textAlign: "left" }}>
                        <th style={{ padding: "0.5rem" }}>Alert ID</th>
                        <th style={{ padding: "0.5rem" }}>Severity</th>
                        <th style={{ padding: "0.5rem" }}>Category</th>
                        <th style={{ padding: "0.5rem" }}>Asset</th>
                        <th style={{ padding: "0.5rem" }}>Criticality</th>
                        <th style={{ padding: "0.5rem" }}>Timestamp</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.evidence_records.alerts.map((a) => (
                        <tr key={a.alert_id} style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.04)" }}>
                          <td style={{ padding: "0.5rem", fontFamily: "var(--font-mono)" }}>{a.alert_id.slice(0, 8)}...</td>
                          <td style={{ padding: "0.5rem" }}>
                            <span className={`badge badge-${a.severity.toLowerCase()}`} style={{ fontSize: "0.65rem" }}>
                              {a.severity}
                            </span>
                          </td>
                          <td style={{ padding: "0.5rem", color: "#fff" }}>{a.alert_category}</td>
                          <td style={{ padding: "0.5rem" }}>{a.asset_type} ({a.environment})</td>
                          <td style={{ padding: "0.5rem", color: a.asset_criticality === "CRITICAL" ? "var(--accent-crimson)" : "var(--text-secondary)" }}>
                            {a.asset_criticality}
                          </td>
                          <td style={{ padding: "0.5rem", color: "var(--text-muted)" }}>
                            {new Date(a.event_time).toLocaleString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}

                {activeEvidenceTab === "investigations" && (
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.78rem" }}>
                    <thead>
                      <tr style={{ borderBottom: "1px solid var(--border-subtle)", color: "var(--text-muted)", textAlign: "left" }}>
                        <th style={{ padding: "0.5rem" }}>Investigation ID</th>
                        <th style={{ padding: "0.5rem" }}>Analyst</th>
                        <th style={{ padding: "0.5rem" }}>Evidence Items</th>
                        <th style={{ padding: "0.5rem" }}>Started At</th>
                        <th style={{ padding: "0.5rem" }}>Disposition</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.evidence_records.investigations.map((inv) => (
                        <tr key={inv.investigation_id} style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.04)" }}>
                          <td style={{ padding: "0.5rem", fontFamily: "var(--font-mono)" }}>{inv.investigation_id.slice(0, 8)}...</td>
                          <td style={{ padding: "0.5rem", color: "#fff" }}>{inv.analyst_id || "Unassigned"}</td>
                          <td style={{ padding: "0.5rem", fontWeight: 700, color: inv.evidence_count <= 1 ? "var(--accent-crimson)" : "var(--accent-emerald)" }}>
                            {inv.evidence_count} items
                          </td>
                          <td style={{ padding: "0.5rem", color: "var(--text-muted)" }}>
                            {new Date(inv.started_at).toLocaleTimeString()}
                          </td>
                          <td style={{ padding: "0.5rem", color: "var(--text-secondary)" }}>{inv.disposition || "None"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}

                {activeEvidenceTab === "escalations" && (
                  <div style={{ padding: "0.75rem", color: "var(--text-muted)", fontSize: "0.8rem" }}>
                    {detail.evidence_records.escalations.length === 0 ? (
                      <div style={{ color: "var(--accent-crimson)", fontStyle: "italic" }}>
                        ⚠️ ZERO escalation records exist for these critical incidents (Escalation Gap).
                      </div>
                    ) : (
                      detail.evidence_records.escalations.map((e) => (
                        <div key={e.escalation_id}>Escalated to: {e.target} ({e.level}) at {e.escalated_at}</div>
                      ))
                    )}
                  </div>
                )}

                {activeEvidenceTab === "actions" && (
                  <div style={{ padding: "0.75rem", color: "var(--text-muted)", fontSize: "0.8rem" }}>
                    {detail.evidence_records.actions.length === 0 ? (
                      <div style={{ color: "var(--accent-amber)", fontStyle: "italic" }}>
                        ⚠️ No linked permanent remediation action records found (Repeated Unresolved Pattern).
                      </div>
                    ) : (
                      detail.evidence_records.actions.map((act) => (
                        <div key={act.action_id}>Action: {act.action_type} - {act.outcome} ({act.performed_at})</div>
                      ))
                    )}
                  </div>
                )}

                {activeEvidenceTab === "closures" && (
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.78rem" }}>
                    <thead>
                      <tr style={{ borderBottom: "1px solid var(--border-subtle)", color: "var(--text-muted)", textAlign: "left" }}>
                        <th style={{ padding: "0.5rem" }}>Closure ID</th>
                        <th style={{ padding: "0.5rem" }}>Closed At</th>
                        <th style={{ padding: "0.5rem" }}>Reason</th>
                        <th style={{ padding: "0.5rem" }}>Reviewer</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.evidence_records.closures.map((c) => (
                        <tr key={c.closure_id} style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.04)" }}>
                          <td style={{ padding: "0.5rem", fontFamily: "var(--font-mono)" }}>{c.closure_id.slice(0, 8)}...</td>
                          <td style={{ padding: "0.5rem", color: "var(--text-muted)" }}>{new Date(c.closed_at).toLocaleTimeString()}</td>
                          <td style={{ padding: "0.5rem", color: "#fff" }}>{c.reason}</td>
                          <td style={{ padding: "0.5rem", color: "var(--text-secondary)" }}>{c.reviewer || "Auto"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}

                {activeEvidenceTab === "cases" && (
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.78rem" }}>
                    <thead>
                      <tr style={{ borderBottom: "1px solid var(--border-subtle)", color: "var(--text-muted)", textAlign: "left" }}>
                        <th style={{ padding: "0.5rem" }}>Case ID</th>
                        <th style={{ padding: "0.5rem" }}>Severity</th>
                        <th style={{ padding: "0.5rem" }}>Opened At</th>
                        <th style={{ padding: "0.5rem" }}>Closed At</th>
                        <th style={{ padding: "0.5rem" }}>Outcome</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.evidence_records.cases.map((c) => (
                        <tr key={c.case_id} style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.04)" }}>
                          <td style={{ padding: "0.5rem", fontFamily: "var(--font-mono)" }}>{c.case_id.slice(0, 8)}...</td>
                          <td style={{ padding: "0.5rem" }}>{c.severity}</td>
                          <td style={{ padding: "0.5rem", color: "var(--text-muted)" }}>{new Date(c.opened_at).toLocaleTimeString()}</td>
                          <td style={{ padding: "0.5rem", color: "var(--text-muted)" }}>{c.closed_at ? new Date(c.closed_at).toLocaleTimeString() : "Open"}</td>
                          <td style={{ padding: "0.5rem", color: "#fff" }}>{c.outcome || "Pending"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}

              </div>
            ) : null}
          </div>

          {/* Section 4: Supervisory Human Decision Workflow */}
          <div
            style={{
              background: "rgba(15, 23, 42, 0.8)",
              border: "1px solid rgba(0, 240, 255, 0.3)",
              borderRadius: "var(--radius-md)",
              padding: "1.25rem",
            }}
          >
            <h4 style={{ fontSize: "0.85rem", color: "var(--accent-cyan)", textTransform: "uppercase", marginBottom: "0.75rem" }}>
              Supervisory Review & Disposition Workflow (Human Examiner Final Decision)
            </h4>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr auto", gap: "1rem", alignItems: "flex-end" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "0.35rem" }}>
                  Supervisory Decision
                </label>
                <select
                  value={decision}
                  onChange={(e) => setDecision(e.target.value as ReviewDecisionState)}
                  style={{
                    width: "100%",
                    background: "var(--bg-input)",
                    border: "1px solid var(--border-subtle)",
                    borderRadius: "var(--radius-sm)",
                    padding: "0.55rem",
                    color: "#fff",
                    fontSize: "0.82rem",
                  }}
                >
                  <option value="CONFIRMED">CONFIRMED (Execution Gap Validated)</option>
                  <option value="FALSE_POSITIVE">FALSE_POSITIVE (Authorized Deviation)</option>
                  <option value="NEEDS_INVESTIGATION">NEEDS_INVESTIGATION (Request More Data)</option>
                  <option value="INSUFFICIENT_EVIDENCE">INSUFFICIENT_EVIDENCE</option>
                </select>
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "0.35rem" }}>
                  Examiner Audit Notes & Action Order
                </label>
                <input
                  type="text"
                  placeholder="e.g., Scheduled on-site supervisory inspection of L1 alert closures with SOC leadership."
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  style={{
                    width: "100%",
                    background: "var(--bg-input)",
                    border: "1px solid var(--border-subtle)",
                    borderRadius: "var(--radius-sm)",
                    padding: "0.55rem 0.75rem",
                    color: "#fff",
                    fontSize: "0.82rem",
                  }}
                />
              </div>

              <button
                onClick={handleSubmitReview}
                disabled={submitting}
                className="btn-primary"
                style={{ padding: "0.55rem 1.25rem", whiteSpace: "nowrap" }}
              >
                <Send size={15} /> {submitting ? "Saving..." : "Submit Decision"}
              </button>
            </div>
          </div>

        </div>

      </div>
    </div>
  );
};

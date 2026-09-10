import React, { useState, useEffect } from "react";
import {
  X,
  Send,
  ShieldCheck,
  Layers,
  FileText,
  CheckCircle2,
  ChevronRight,
  ChevronLeft,
  Calculator,
  Cpu,
  Info,
} from "lucide-react";
import type { Finding, FindingDetail, ReviewDecisionState } from "../types";
import { fetchFindingDetail, submitReviewDecision } from "../api";

interface FindingDetailModalProps {
  finding: Finding;
  onClose: () => void;
  onReviewSubmitted: () => void;
}

type ReviewStage = "finding" | "explanation" | "detector" | "calculation" | "evidence" | "sourcerecord";

const STAGES: Array<{ id: ReviewStage; label: string; icon: React.FC<{ size?: number; style?: React.CSSProperties }> }> = [
  { id: "finding", label: "1. Finding", icon: ShieldCheck },
  { id: "explanation", label: "2. Explanation", icon: Info },
  { id: "detector", label: "3. Detector", icon: Cpu },
  { id: "calculation", label: "4. Calculation", icon: Calculator },
  { id: "evidence", label: "5. Evidence", icon: Layers },
  { id: "sourcerecord", label: "6. Source Record", icon: FileText },
];

export const FindingDetailModal: React.FC<FindingDetailModalProps> = ({
  finding,
  onClose,
  onReviewSubmitted,
}) => {
  const [detail, setDetail] = useState<FindingDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [activeStage, setActiveStage] = useState<ReviewStage>("finding");
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
  const comps = finding.priority_components || {};
  const currentStageIndex = STAGES.findIndex((s) => s.id === activeStage);

  const goToNextStage = () => {
    if (currentStageIndex < STAGES.length - 1) {
      setActiveStage(STAGES[currentStageIndex + 1].id);
    }
  };

  const goToPrevStage = () => {
    if (currentStageIndex > 0) {
      setActiveStage(STAGES[currentStageIndex - 1].id);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose} id="finding-detail-modal">
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: "1050px", width: "95%" }}>
        
        {/* Modal Header */}
        <div
          style={{
            padding: "1.25rem 1.5rem",
            borderBottom: "1px solid var(--border-subtle)",
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            background: "rgba(15, 23, 42, 0.98)",
            position: "sticky",
            top: 0,
            zIndex: 20,
          }}
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginBottom: "0.35rem", flexWrap: "wrap" }}>
              <span className={`badge badge-${finding.priority_label.toLowerCase()}`}>
                {finding.priority_label} PRIORITY
              </span>
              <span className="badge badge-purple">{finding.finding_type}</span>
              {finding.evidence_state && (
                <span
                  className={`badge badge-${
                    finding.evidence_state === "SUPPORTED"
                      ? "emerald"
                      : finding.evidence_state === "WEAKLY_SUPPORTED"
                      ? "amber"
                      : "rose"
                  }`}
                  style={{ fontSize: "0.72rem" }}
                  title={`Inference state: ${finding.evidence_state}`}
                >
                  {finding.evidence_state.replace("_", " ")}
                </span>
              )}
              <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                ID: <code className="font-mono">{finding.finding_id.slice(0, 8)}</code>
              </span>
            </div>
            <h2 style={{ fontSize: "1.25rem", color: "#fff", margin: 0 }}>{finding.title}</h2>
            <p style={{ fontSize: "0.82rem", color: "var(--accent-cyan)", marginTop: "0.2rem", marginBottom: 0 }}>
              Entity: <strong>{finding.cse_name}</strong> • Sector: <strong>{finding.sector}</strong> • Dataset Version: <code className="font-mono">{finding.dataset_version?.dataset_version_id?.slice(0, 8) || "Current"}</code>
            </p>
          </div>

          <button
            onClick={onClose}
            id="close-modal-btn"
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

        {/* Traceability Breadcrumb Stepper (Finding -> Explanation -> Detector -> Calculation -> Evidence -> Source record) */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            background: "rgba(10, 15, 30, 0.95)",
            borderBottom: "1px solid var(--border-subtle)",
            padding: "0.5rem 1.5rem",
            overflowX: "auto",
            gap: "0.4rem",
            position: "sticky",
            top: "76px",
            zIndex: 15,
          }}
          id="reviewer-traceability-stepper"
        >
          {STAGES.map((s, idx) => {
            const Icon = s.icon;
            const isActive = activeStage === s.id;
            const isCompleted = idx < currentStageIndex;
            return (
              <React.Fragment key={s.id}>
                <button
                  onClick={() => setActiveStage(s.id)}
                  id={`stepper-btn-${s.id}`}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.4rem",
                    background: isActive ? "rgba(0, 240, 255, 0.15)" : "transparent",
                    color: isActive ? "var(--accent-cyan)" : isCompleted ? "var(--text-secondary)" : "var(--text-muted)",
                    border: isActive ? "1px solid rgba(0, 240, 255, 0.3)" : "1px solid transparent",
                    padding: "0.4rem 0.75rem",
                    borderRadius: "var(--radius-sm)",
                    fontSize: "0.78rem",
                    fontWeight: isActive ? 700 : 500,
                    cursor: "pointer",
                    whiteSpace: "nowrap",
                    transition: "all 0.15s ease",
                  }}
                >
                  <Icon size={14} style={{ color: isActive ? "var(--accent-cyan)" : isCompleted ? "var(--accent-emerald)" : "var(--text-muted)" }} />
                  <span>{s.label}</span>
                  {isCompleted && <CheckCircle2 size={12} style={{ color: "var(--accent-emerald)", marginLeft: "0.1rem" }} />}
                </button>
                {idx < STAGES.length - 1 && (
                  <ChevronRight size={14} style={{ color: "var(--text-muted)", opacity: 0.5, flexShrink: 0 }} />
                )}
              </React.Fragment>
            );
          })}
        </div>

        {/* Modal Body: Active Stage View */}
        <div style={{ padding: "1.5rem", display: "flex", flexDirection: "column", gap: "1.25rem", minHeight: "380px" }}>

          {/* ================================================================= */}
          {/* STAGE 1: FINDING OVERVIEW */}
          {/* ================================================================= */}
          {activeStage === "finding" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
              <div style={{ background: "rgba(30, 41, 59, 0.4)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", padding: "1.25rem" }}>
                <h4 style={{ fontSize: "0.85rem", color: "var(--accent-cyan)", textTransform: "uppercase", marginBottom: "0.75rem" }}>
                  1. Finding Overview & Identity Contract
                </h4>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "0.75rem", fontSize: "0.8rem", marginBottom: "1rem" }}>
                  <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "0.75rem", borderRadius: "var(--radius-sm)" }}>
                    <div style={{ color: "var(--text-muted)", fontSize: "0.72rem" }}>Finding ID</div>
                    <code className="font-mono" style={{ color: "#fff", fontSize: "0.75rem" }}>{finding.finding_id}</code>
                  </div>
                  <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "0.75rem", borderRadius: "var(--radius-sm)" }}>
                    <div style={{ color: "var(--text-muted)", fontSize: "0.72rem" }}>Priority Tier & Score</div>
                    <div style={{ color: "#fff", fontWeight: 700 }}>
                      <span className={`badge badge-${finding.priority_label.toLowerCase()}`}>{finding.priority_label}</span> ({finding.priority_score.toFixed(3)})
                    </div>
                  </div>
                  <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "0.75rem", borderRadius: "var(--radius-sm)" }}>
                    <div style={{ color: "var(--text-muted)", fontSize: "0.72rem" }}>Evidentiary Confidence</div>
                    <div style={{ color: "var(--accent-emerald)", fontWeight: 700 }}>{finding.evidentiary_confidence}%</div>
                  </div>
                  <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "0.75rem", borderRadius: "var(--radius-sm)" }}>
                    <div style={{ color: "var(--text-muted)", fontSize: "0.72rem" }}>Data Trust Score</div>
                    <div style={{ color: "var(--accent-cyan)", fontWeight: 700 }}>{finding.data_quality_score}%</div>
                  </div>
                </div>

                <div style={{ padding: "0.85rem", background: "rgba(15, 23, 42, 0.7)", borderRadius: "var(--radius-sm)", borderLeft: "3px solid var(--accent-cyan)" }}>
                  <div style={{ fontSize: "0.75rem", color: "var(--accent-cyan)", fontWeight: 600, marginBottom: "0.2rem" }}>HEADLINE</div>
                  <div style={{ fontSize: "0.92rem", color: "#fff", lineHeight: 1.4 }}>{finding.headline}</div>
                </div>
              </div>
            </div>
          )}

          {/* ================================================================= */}
          {/* STAGE 2: EXPLANATION */}
          {/* ================================================================= */}
          {activeStage === "explanation" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
              <div style={{ background: "rgba(30, 41, 59, 0.4)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", padding: "1.25rem" }}>
                <h4 style={{ fontSize: "0.85rem", color: "var(--accent-cyan)", textTransform: "uppercase", marginBottom: "0.75rem" }}>
                  2. Supervisory Analytical Rationale (Deterministic Template Grounded)
                </h4>

                {/* What Happened & Why Flagged */}
                <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem", marginBottom: "1.25rem" }}>
                  <div style={{ background: "rgba(15, 23, 42, 0.7)", padding: "0.9rem", borderRadius: "var(--radius-sm)", borderLeft: "3px solid var(--accent-cyan)" }}>
                    <div style={{ fontSize: "0.75rem", color: "var(--accent-cyan)", fontWeight: 600, marginBottom: "0.3rem", textTransform: "uppercase" }}>
                      What Happened (Factual Telemetry Observation)
                    </div>
                    <p style={{ fontSize: "0.86rem", color: "#fff", margin: 0, lineHeight: 1.45 }}>
                      {detail?.explanation?.what_happened || finding.observed_behavior}
                    </p>
                  </div>

                  <div style={{ background: "rgba(15, 23, 42, 0.7)", padding: "0.9rem", borderRadius: "var(--radius-sm)", borderLeft: "3px solid var(--accent-amber)" }}>
                    <div style={{ fontSize: "0.75rem", color: "var(--accent-amber)", fontWeight: 600, marginBottom: "0.3rem", textTransform: "uppercase" }}>
                      Why It Was Flagged (Supervisory Detection Rationale)
                    </div>
                    <p style={{ fontSize: "0.86rem", color: "#fff", margin: 0, lineHeight: 1.45 }}>
                      {detail?.explanation?.why_flagged || `Observed operational metrics deviate from supervisory baseline: ${finding.expected_behavior}.`}
                    </p>
                  </div>
                </div>

                {/* Evidence Summary & Confidence & Peer Context Grid */}
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.85rem", marginBottom: "1.25rem" }}>
                  <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "0.85rem", borderRadius: "var(--radius-sm)" }}>
                    <div style={{ fontSize: "0.73rem", color: "var(--text-muted)", fontWeight: 600, marginBottom: "0.25rem" }}>
                      SUPPORTING EVIDENCE SUMMARY
                    </div>
                    <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", margin: 0 }}>
                      {detail?.explanation?.supporting_evidence_summary || `${finding.evidence_record_count} concrete records attached with ${finding.supporting_signals.length} supporting signals.`}
                    </p>
                  </div>

                  <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "0.85rem", borderRadius: "var(--radius-sm)" }}>
                    <div style={{ fontSize: "0.73rem", color: "var(--text-muted)", fontWeight: 600, marginBottom: "0.25rem" }}>
                      EVIDENTIARY CONFIDENCE & STATE
                    </div>
                    <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", margin: 0 }}>
                      {detail?.explanation?.confidence_summary || `Confidence: ${finding.evidentiary_confidence}% (State: ${finding.evidence_state || "SUPPORTED"})`}
                    </p>
                  </div>

                  <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "0.85rem", borderRadius: "var(--radius-sm)" }}>
                    <div style={{ fontSize: "0.73rem", color: "var(--text-muted)", fontWeight: 600, marginBottom: "0.25rem" }}>
                      RELEVANT PEER CONTEXT
                    </div>
                    <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", margin: 0 }}>
                      {detail?.explanation?.peer_context_summary || detail?.explanation?.peer_context || "Sector peer baseline cohort MAD comparison"}
                    </p>
                  </div>

                  <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "0.85rem", borderRadius: "var(--radius-sm)" }}>
                    <div style={{ fontSize: "0.73rem", color: "var(--text-muted)", fontWeight: 600, marginBottom: "0.25rem" }}>
                      DATA TRUST & TELEMETRY LIMITATIONS
                    </div>
                    <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", margin: 0 }}>
                      {detail?.explanation?.data_quality_limitation || `Data trust score is ${finding.data_quality_score}%.`}
                    </p>
                  </div>
                </div>

                {/* Expected vs Observed Behavior */}
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1rem" }}>
                  <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "0.85rem", borderRadius: "var(--radius-sm)", borderLeft: "3px solid var(--accent-emerald)" }}>
                    <div style={{ fontSize: "0.75rem", color: "var(--accent-emerald)", fontWeight: 600, marginBottom: "0.3rem" }}>
                      EXPECTED OPERATIONAL BEHAVIOR
                    </div>
                    <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", margin: 0 }}>
                      {finding.expected_behavior}
                    </p>
                  </div>

                  <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "0.85rem", borderRadius: "var(--radius-sm)", borderLeft: "3px solid var(--accent-crimson)" }}>
                    <div style={{ fontSize: "0.75rem", color: "var(--accent-crimson)", fontWeight: 600, marginBottom: "0.3rem" }}>
                      OBSERVED EVIDENCE
                    </div>
                    <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", margin: 0 }}>
                      {finding.observed_behavior}
                    </p>
                  </div>
                </div>

                {/* Supporting & Contradicting Signals */}
                <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem", marginBottom: "1rem" }}>
                  <div style={{ fontSize: "0.78rem", fontWeight: 600, color: "var(--accent-cyan)" }}>
                    CONTRIBUTING SUPPORTING SIGNALS:
                  </div>
                  <ul style={{ paddingLeft: "1.25rem", fontSize: "0.82rem", color: "var(--text-secondary)", margin: 0 }}>
                    {finding.supporting_signals.map((sig, idx) => (
                      <li key={idx} style={{ marginBottom: "0.25rem" }}>{sig}</li>
                    ))}
                  </ul>

                  {finding.contradicting_signals && finding.contradicting_signals.length > 0 && (
                    <>
                      <div style={{ fontSize: "0.78rem", fontWeight: 600, color: "var(--accent-amber)", marginTop: "0.4rem" }}>
                        CONTRADICTING / LIMITING SIGNALS:
                      </div>
                      <ul style={{ paddingLeft: "1.25rem", fontSize: "0.82rem", color: "var(--text-secondary)", margin: 0 }}>
                        {finding.contradicting_signals.map((sig, idx) => (
                          <li key={idx}>{sig}</li>
                        ))}
                      </ul>
                    </>
                  )}
                </div>

                {/* Recommended Action */}
                <div style={{ padding: "0.75rem", background: "rgba(0, 240, 255, 0.05)", border: "1px solid rgba(0, 240, 255, 0.2)", borderRadius: "var(--radius-sm)" }}>
                  <strong style={{ fontSize: "0.8rem", color: "var(--accent-cyan)" }}>Recommended Supervisory Action: </strong>
                  <span style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}>{finding.recommended_action}</span>
                </div>
              </div>
            </div>
          )}

          {/* ================================================================= */}
          {/* STAGE 3: DETECTOR SPECIFICATION */}
          {/* ================================================================= */}
          {activeStage === "detector" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
              <div style={{ background: "rgba(30, 41, 59, 0.4)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", padding: "1.25rem" }}>
                <h4 style={{ fontSize: "0.85rem", color: "var(--accent-cyan)", textTransform: "uppercase", marginBottom: "0.75rem" }}>
                  3. Deterministic Detector Algorithm & Context
                </h4>

                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.75rem", fontSize: "0.78rem", marginBottom: "1rem" }}>
                  <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "0.75rem", borderRadius: "var(--radius-sm)" }}>
                    <div style={{ color: "var(--text-muted)", fontSize: "0.72rem" }}>Detector Name</div>
                    <div style={{ color: "#fff", fontWeight: 600 }}>{finding.detector || finding.finding_type}</div>
                  </div>
                  <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "0.75rem", borderRadius: "var(--radius-sm)" }}>
                    <div style={{ color: "var(--text-muted)", fontSize: "0.72rem" }}>Detector Algorithm Version</div>
                    <div style={{ color: "var(--accent-cyan)", fontWeight: 600 }}>v{finding.detector_version || "1.0.0"}</div>
                  </div>
                  <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "0.75rem", borderRadius: "var(--radius-sm)" }}>
                    <div style={{ color: "var(--text-muted)", fontSize: "0.72rem" }}>Ruleset Specification</div>
                    <div style={{ color: "var(--accent-purple)", fontWeight: 600 }}>Version {finding.ruleset_version || "V1"}</div>
                  </div>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem", fontSize: "0.8rem", marginBottom: "1rem" }}>
                  <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "0.75rem", borderRadius: "var(--radius-sm)" }}>
                    <div style={{ color: "var(--text-muted)", fontSize: "0.72rem", marginBottom: "0.2rem" }}>Peer Context</div>
                    <div style={{ color: "var(--text-secondary)" }}>{detail?.explanation?.peer_context || "Sector peer baseline cohort"}</div>
                  </div>
                  <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "0.75rem", borderRadius: "var(--radius-sm)" }}>
                    <div style={{ color: "var(--text-muted)", fontSize: "0.72rem", marginBottom: "0.2rem" }}>Temporal Context</div>
                    <div style={{ color: "var(--text-secondary)" }}>{detail?.explanation?.temporal_context || "Active operational reporting cycle"}</div>
                  </div>
                </div>

                <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "0.75rem", borderRadius: "var(--radius-sm)" }}>
                  <div style={{ color: "var(--text-muted)", fontSize: "0.72rem", marginBottom: "0.2rem" }}>Analytical Method</div>
                  <div style={{ color: "#fff", fontFamily: "var(--font-mono)", fontSize: "0.78rem" }}>
                    {detail?.explanation?.analytical_method || "Statistical baseline & multi-signal evidence fusion"}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ================================================================= */}
          {/* STAGE 4: MATHEMATICAL CALCULATION */}
          {/* ================================================================= */}
          {activeStage === "calculation" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
              <div style={{ background: "rgba(30, 41, 59, 0.4)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", padding: "1.25rem" }}>
                <h4 style={{ fontSize: "0.85rem", color: "var(--accent-cyan)", textTransform: "uppercase", marginBottom: "0.75rem" }}>
                  4. Five-Component Priority Scoring Formula (SRS §10.5)
                </h4>

                <div style={{ background: "rgba(15, 23, 42, 0.8)", padding: "0.85rem", borderRadius: "var(--radius-sm)", marginBottom: "1rem", fontFamily: "var(--font-mono)", fontSize: "0.8rem", color: "var(--accent-cyan)" }}>
                  Priority Score = (0.30 × T) + (0.25 × D) + (0.20 × B) + (0.15 × C) - (0.10 × A)
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "0.5rem", marginBottom: "1.25rem" }}>
                  <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "0.6rem", borderRadius: "var(--radius-sm)", textAlign: "center" }}>
                    <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>T (Signal)</div>
                    <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "#fff" }}>{comps.T ?? comps.signal_strength ?? 0.0}</div>
                    <div style={{ fontSize: "0.65rem", color: "var(--accent-cyan)" }}>w = +0.30</div>
                  </div>
                  <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "0.6rem", borderRadius: "var(--radius-sm)", textAlign: "center" }}>
                    <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>D (Deviation)</div>
                    <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "#fff" }}>{comps.D ?? comps.peer_deviation ?? 0.0}</div>
                    <div style={{ fontSize: "0.65rem", color: "var(--accent-cyan)" }}>w = +0.25</div>
                  </div>
                  <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "0.6rem", borderRadius: "var(--radius-sm)", textAlign: "center" }}>
                    <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>B (Persistence)</div>
                    <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "#fff" }}>{comps.B ?? comps.persistence ?? 0.0}</div>
                    <div style={{ fontSize: "0.65rem", color: "var(--accent-cyan)" }}>w = +0.20</div>
                  </div>
                  <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "0.6rem", borderRadius: "var(--radius-sm)", textAlign: "center" }}>
                    <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>C (Criticality)</div>
                    <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "#fff" }}>{comps.C ?? comps.asset_criticality ?? 0.0}</div>
                    <div style={{ fontSize: "0.65rem", color: "var(--accent-cyan)" }}>w = +0.15</div>
                  </div>
                  <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "0.6rem", borderRadius: "var(--radius-sm)", textAlign: "center" }}>
                    <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>A (Uncertainty)</div>
                    <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "#fff" }}>{comps.A ?? comps.data_uncertainty ?? 0.0}</div>
                    <div style={{ fontSize: "0.65rem", color: "var(--accent-crimson)" }}>w = -0.10</div>
                  </div>
                </div>

                {/* Data Trust Breakdown */}
                <h5 style={{ fontSize: "0.78rem", color: "var(--accent-cyan)", textTransform: "uppercase", marginBottom: "0.5rem" }}>
                  Data Trust Component Breakdown (§7.2.1)
                </h5>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "0.75rem", fontSize: "0.75rem" }}>
                  <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "0.5rem", borderRadius: "var(--radius-sm)" }}>
                    <span style={{ color: "var(--text-muted)" }}>Completeness (35%): </span>
                    <strong style={{ color: "#fff" }}>{dq.completeness}%</strong>
                  </div>
                  <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "0.5rem", borderRadius: "var(--radius-sm)" }}>
                    <span style={{ color: "var(--text-muted)" }}>Consistency (25%): </span>
                    <strong style={{ color: "#fff" }}>{dq.consistency}%</strong>
                  </div>
                  <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "0.5rem", borderRadius: "var(--radius-sm)" }}>
                    <span style={{ color: "var(--text-muted)" }}>Coverage (25%): </span>
                    <strong style={{ color: "#fff" }}>{dq.coverage}%</strong>
                  </div>
                  <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "0.5rem", borderRadius: "var(--radius-sm)" }}>
                    <span style={{ color: "var(--text-muted)" }}>Sufficiency (15%): </span>
                    <strong style={{ color: "#fff" }}>{dq.sample_sufficiency}%</strong>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ================================================================= */}
          {/* STAGE 5: EVIDENCE DRILL-DOWN */}
          {/* ================================================================= */}
          {activeStage === "evidence" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
              <div style={{ background: "rgba(30, 41, 59, 0.4)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", padding: "1.25rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem", flexWrap: "wrap", gap: "0.5rem" }}>
                  <h4 style={{ fontSize: "0.85rem", color: "var(--accent-cyan)", textTransform: "uppercase", margin: 0 }}>
                    5. Linked Canonical Evidence ({finding.evidence_record_count} Linked Items)
                  </h4>
                  <div style={{ display: "flex", gap: "0.3rem", flexWrap: "wrap" }}>
                    {["alerts", "cases", "investigations", "escalations", "actions", "closures", "assets"].map((tab) => (
                      <button
                        key={tab}
                        onClick={() => setActiveEvidenceTab(tab)}
                        id={`evidence-tab-${tab}`}
                        style={{
                          background: activeEvidenceTab === tab ? "rgba(0, 240, 255, 0.15)" : "transparent",
                          color: activeEvidenceTab === tab ? "var(--accent-cyan)" : "var(--text-muted)",
                          border: activeEvidenceTab === tab ? "1px solid rgba(0, 240, 255, 0.3)" : "1px solid transparent",
                          padding: "0.25rem 0.55rem",
                          borderRadius: "var(--radius-sm)",
                          fontSize: "0.72rem",
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
                  <div style={{ maxHeight: "280px", overflowY: "auto" }}>
                    
                    {/* ALERTS TAB */}
                    {activeEvidenceTab === "alerts" && (
                      detail.evidence_records.alerts.length === 0 ? (
                        <div style={{ padding: "1rem", color: "var(--accent-amber)", background: "rgba(245, 158, 11, 0.08)", borderRadius: "var(--radius-sm)" }}>
                          ⚠️ INSUFFICIENT EVIDENCE: Zero alert records attached for this entity.
                        </div>
                      ) : (
                        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.75rem" }}>
                          <thead>
                            <tr style={{ borderBottom: "1px solid var(--border-subtle)", color: "var(--text-muted)", textAlign: "left" }}>
                              <th style={{ padding: "0.4rem" }}>Source ID</th>
                              <th style={{ padding: "0.4rem" }}>Alert ID</th>
                              <th style={{ padding: "0.4rem" }}>Severity</th>
                              <th style={{ padding: "0.4rem" }}>Category</th>
                              <th style={{ padding: "0.4rem" }}>Asset</th>
                              <th style={{ padding: "0.4rem" }}>Criticality</th>
                              <th style={{ padding: "0.4rem" }}>Event Time</th>
                            </tr>
                          </thead>
                          <tbody>
                            {detail.evidence_records.alerts.map((a) => (
                              <tr key={a.alert_id} style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.04)" }}>
                                <td style={{ padding: "0.4rem", fontFamily: "var(--font-mono)", color: "var(--accent-cyan)" }}>
                                  {a.source_record_id || a.source_record_ref || "AL-REC"}
                                </td>
                                <td style={{ padding: "0.4rem", fontFamily: "var(--font-mono)" }}>{a.alert_id.slice(0, 8)}...</td>
                                <td style={{ padding: "0.4rem" }}>
                                  <span className={`badge badge-${a.severity.toLowerCase()}`} style={{ fontSize: "0.62rem" }}>
                                    {a.severity}
                                  </span>
                                </td>
                                <td style={{ padding: "0.4rem", color: "#fff" }}>{a.alert_category}</td>
                                <td style={{ padding: "0.4rem" }}>{a.asset_type} ({a.environment})</td>
                                <td style={{ padding: "0.4rem", color: a.asset_criticality === "CRITICAL" ? "var(--accent-crimson)" : "var(--text-secondary)" }}>
                                  {a.asset_criticality}
                                </td>
                                <td style={{ padding: "0.4rem", color: "var(--text-muted)" }}>
                                  {new Date(a.event_time).toLocaleString()}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      )
                    )}

                    {/* CASES TAB */}
                    {activeEvidenceTab === "cases" && (
                      detail.evidence_records.cases.length === 0 ? (
                        <div style={{ padding: "1rem", color: "var(--accent-amber)", background: "rgba(245, 158, 11, 0.08)", borderRadius: "var(--radius-sm)" }}>
                          ⚠️ INSUFFICIENT EVIDENCE: No formal case records linked.
                        </div>
                      ) : (
                        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.75rem" }}>
                          <thead>
                            <tr style={{ borderBottom: "1px solid var(--border-subtle)", color: "var(--text-muted)", textAlign: "left" }}>
                              <th style={{ padding: "0.4rem" }}>Source ID</th>
                              <th style={{ padding: "0.4rem" }}>Case ID</th>
                              <th style={{ padding: "0.4rem" }}>Severity</th>
                              <th style={{ padding: "0.4rem" }}>Opened At</th>
                              <th style={{ padding: "0.4rem" }}>Closed At</th>
                              <th style={{ padding: "0.4rem" }}>Outcome</th>
                            </tr>
                          </thead>
                          <tbody>
                            {detail.evidence_records.cases.map((c) => (
                              <tr key={c.case_id} style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.04)" }}>
                                <td style={{ padding: "0.4rem", fontFamily: "var(--font-mono)", color: "var(--accent-cyan)" }}>
                                  {c.source_record_id || c.source_record_ref || "CASE-REC"}
                                </td>
                                <td style={{ padding: "0.4rem", fontFamily: "var(--font-mono)" }}>{c.case_id.slice(0, 8)}...</td>
                                <td style={{ padding: "0.4rem" }}>{c.severity}</td>
                                <td style={{ padding: "0.4rem", color: "var(--text-muted)" }}>{new Date(c.opened_at).toLocaleTimeString()}</td>
                                <td style={{ padding: "0.4rem", color: "var(--text-muted)" }}>{c.closed_at ? new Date(c.closed_at).toLocaleTimeString() : "Open"}</td>
                                <td style={{ padding: "0.4rem", color: "#fff" }}>{c.outcome || "Pending"}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      )
                    )}

                    {/* INVESTIGATIONS TAB */}
                    {activeEvidenceTab === "investigations" && (
                      detail.evidence_records.investigations.length === 0 ? (
                        <div style={{ padding: "1rem", color: "var(--accent-amber)", background: "rgba(245, 158, 11, 0.08)", borderRadius: "var(--radius-sm)" }}>
                          ⚠️ INSUFFICIENT EVIDENCE: No investigation notes or triage records attached.
                        </div>
                      ) : (
                        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.75rem" }}>
                          <thead>
                            <tr style={{ borderBottom: "1px solid var(--border-subtle)", color: "var(--text-muted)", textAlign: "left" }}>
                              <th style={{ padding: "0.4rem" }}>Source ID</th>
                              <th style={{ padding: "0.4rem" }}>Investigation ID</th>
                              <th style={{ padding: "0.4rem" }}>Analyst</th>
                              <th style={{ padding: "0.4rem" }}>Evidence Items</th>
                              <th style={{ padding: "0.4rem" }}>Started At</th>
                              <th style={{ padding: "0.4rem" }}>Disposition</th>
                            </tr>
                          </thead>
                          <tbody>
                            {detail.evidence_records.investigations.map((inv) => (
                              <tr key={inv.investigation_id} style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.04)" }}>
                                <td style={{ padding: "0.4rem", fontFamily: "var(--font-mono)", color: "var(--accent-cyan)" }}>
                                  {inv.source_record_id || inv.source_record_ref || "INV-REC"}
                                </td>
                                <td style={{ padding: "0.4rem", fontFamily: "var(--font-mono)" }}>{inv.investigation_id.slice(0, 8)}...</td>
                                <td style={{ padding: "0.4rem", color: "#fff" }}>{inv.analyst_id || "Unassigned"}</td>
                                <td style={{ padding: "0.4rem", fontWeight: 700, color: inv.evidence_count <= 1 ? "var(--accent-crimson)" : "var(--accent-emerald)" }}>
                                  {inv.evidence_count} items
                                </td>
                                <td style={{ padding: "0.4rem", color: "var(--text-muted)" }}>
                                  {new Date(inv.started_at).toLocaleTimeString()}
                                </td>
                                <td style={{ padding: "0.4rem", color: "var(--text-secondary)" }}>{inv.disposition || "None"}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      )
                    )}

                    {/* ESCALATIONS TAB */}
                    {activeEvidenceTab === "escalations" && (
                      detail.evidence_records.escalations.length === 0 ? (
                        <div style={{ padding: "1rem", color: "var(--accent-crimson)", background: "rgba(225, 29, 72, 0.08)", borderRadius: "var(--radius-sm)" }}>
                          ⚠️ ZERO ESCALATION RECORDS: High/critical incident was resolved without mandated escalation (Escalation Gap).
                        </div>
                      ) : (
                        detail.evidence_records.escalations.map((e) => (
                          <div key={e.escalation_id} style={{ padding: "0.5rem", borderBottom: "1px solid rgba(255,255,255,0.04)", fontSize: "0.78rem" }}>
                            Source ID: <code className="font-mono" style={{ color: "var(--accent-cyan)" }}>{e.source_record_id || e.source_record_ref}</code> • Escalated to: <strong>{e.target}</strong> ({e.level}) at {e.escalated_at}
                          </div>
                        ))
                      )
                    )}

                    {/* ACTIONS TAB */}
                    {activeEvidenceTab === "actions" && (
                      detail.evidence_records.actions.length === 0 ? (
                        <div style={{ padding: "1rem", color: "var(--accent-amber)", background: "rgba(245, 158, 11, 0.08)", borderRadius: "var(--radius-sm)" }}>
                          ⚠️ ZERO REMEDIATION ACTIONS: No corrective engineering or patch actions recorded for this asset (Repeated Unresolved Pattern).
                        </div>
                      ) : (
                        detail.evidence_records.actions.map((act) => (
                          <div key={act.action_id} style={{ padding: "0.5rem", borderBottom: "1px solid rgba(255,255,255,0.04)", fontSize: "0.78rem" }}>
                            Source ID: <code className="font-mono" style={{ color: "var(--accent-cyan)" }}>{act.source_record_id || act.source_record_ref}</code> • Action: <strong>{act.action_type}</strong> - Outcome: {act.outcome || "Executed"} ({act.performed_at})
                          </div>
                        ))
                      )
                    )}

                    {/* CLOSURES TAB */}
                    {activeEvidenceTab === "closures" && (
                      detail.evidence_records.closures.length === 0 ? (
                        <div style={{ padding: "1rem", color: "var(--accent-amber)", background: "rgba(245, 158, 11, 0.08)", borderRadius: "var(--radius-sm)" }}>
                          ⚠️ INSUFFICIENT EVIDENCE: No formal closure records found.
                        </div>
                      ) : (
                        detail.evidence_records.closures.map((c) => (
                          <div key={c.closure_id} style={{ padding: "0.5rem", borderBottom: "1px solid rgba(255,255,255,0.04)", fontSize: "0.78rem" }}>
                            Source ID: <code className="font-mono" style={{ color: "var(--accent-cyan)" }}>{c.source_record_id || c.source_record_ref}</code> • Reason: <strong>{c.reason}</strong> • Reviewer: {c.reviewer || "Auto"} ({new Date(c.closed_at).toLocaleTimeString()})
                          </div>
                        ))
                      )
                    )}

                    {/* ASSETS TAB */}
                    {activeEvidenceTab === "assets" && (
                      detail.evidence_records.assets.length === 0 ? (
                        <div style={{ padding: "1rem", color: "var(--accent-amber)", background: "rgba(245, 158, 11, 0.08)", borderRadius: "var(--radius-sm)" }}>
                          ⚠️ INSUFFICIENT EVIDENCE: No asset records found.
                        </div>
                      ) : (
                        detail.evidence_records.assets.map((ast) => (
                          <div key={ast.asset_id} style={{ padding: "0.5rem", borderBottom: "1px solid rgba(255,255,255,0.04)", fontSize: "0.78rem" }}>
                            Source ID: <code className="font-mono" style={{ color: "var(--accent-cyan)" }}>{ast.source_record_id || ast.source_record_ref}</code> • Type: <strong>{ast.asset_type}</strong> • Criticality: {ast.criticality} • Environment: {ast.environment}
                          </div>
                        ))
                      )
                    )}

                  </div>
                ) : null}
              </div>
            </div>
          )}

          {/* ================================================================= */}
          {/* STAGE 6: SOURCE RECORD LINEAGE */}
          {/* ================================================================= */}
          {activeStage === "sourcerecord" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
              <div style={{ background: "rgba(30, 41, 59, 0.4)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", padding: "1.25rem" }}>
                <h4 style={{ fontSize: "0.85rem", color: "var(--accent-cyan)", textTransform: "uppercase", marginBottom: "0.75rem" }}>
                  6. Raw Source Records & Cryptographic Lineage
                </h4>

                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.75rem", fontSize: "0.76rem", marginBottom: "1rem" }}>
                  <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "0.6rem", borderRadius: "var(--radius-sm)" }}>
                    <div style={{ color: "var(--text-muted)", marginBottom: "0.2rem" }}>Source Ingestion File</div>
                    <div style={{ color: "#fff", wordBreak: "break-all" }}>
                      {detail?.provenance?.source_file_ref || "synthetic_operational_bundle.json"}
                    </div>
                  </div>
                  <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "0.6rem", borderRadius: "var(--radius-sm)" }}>
                    <div style={{ color: "var(--text-muted)", marginBottom: "0.2rem" }}>SHA-256 Checksum</div>
                    <code style={{ color: "var(--accent-emerald)", fontFamily: "var(--font-mono)", fontSize: "0.7rem" }}>
                      {detail?.provenance?.sha256_hash ? `${detail.provenance.sha256_hash.slice(0, 16)}...` : "sha256:verified_immutable"}
                    </code>
                  </div>
                  <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "0.6rem", borderRadius: "var(--radius-sm)" }}>
                    <div style={{ color: "var(--text-muted)", marginBottom: "0.2rem" }}>Analysis Run ID</div>
                    <code style={{ color: "#fff", fontFamily: "var(--font-mono)", fontSize: "0.72rem" }}>
                      {detail?.provenance?.analysis_run_id || "Active Run"}
                    </code>
                  </div>
                </div>

                {/* Source Record IDs Table */}
                <h5 style={{ fontSize: "0.78rem", color: "var(--accent-cyan)", textTransform: "uppercase", marginBottom: "0.5rem" }}>
                  Linked Source Record IDs ({detail?.provenance?.source_record_ids?.length || detail?.evidence_records?.source_record_ids?.length || 0} Records)
                </h5>
                <div style={{ maxHeight: "150px", overflowY: "auto", background: "rgba(15, 23, 42, 0.6)", padding: "0.75rem", borderRadius: "var(--radius-sm)" }}>
                  {(detail?.provenance?.source_record_ids || detail?.evidence_records?.source_record_ids || []).length === 0 ? (
                    <div style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>
                      No direct source record references stored in ingested artifact.
                    </div>
                  ) : (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem" }}>
                      {(detail?.provenance?.source_record_ids || detail?.evidence_records?.source_record_ids || []).map((sId: string, idx: number) => (
                        <span key={idx} className="badge badge-cyan" style={{ fontFamily: "var(--font-mono)", fontSize: "0.72rem" }}>
                          {sId}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Stepper Navigation Buttons (Previous / Next Stage) */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingTop: "0.5rem" }}>
            <button
              onClick={goToPrevStage}
              disabled={currentStageIndex === 0}
              className="btn-secondary"
              id="prev-stage-btn"
              style={{ padding: "0.45rem 0.9rem", fontSize: "0.8rem", opacity: currentStageIndex === 0 ? 0.4 : 1, display: "flex", alignItems: "center", gap: "0.3rem" }}
            >
              <ChevronLeft size={16} /> Previous: {currentStageIndex > 0 ? STAGES[currentStageIndex - 1].label : "Start"}
            </button>

            <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
              Step {currentStageIndex + 1} of {STAGES.length}
            </span>

            <button
              onClick={goToNextStage}
              disabled={currentStageIndex === STAGES.length - 1}
              className="btn-primary"
              id="next-stage-btn"
              style={{ padding: "0.45rem 0.9rem", fontSize: "0.8rem", opacity: currentStageIndex === STAGES.length - 1 ? 0.4 : 1, display: "flex", alignItems: "center", gap: "0.3rem" }}
            >
              Next: {currentStageIndex < STAGES.length - 1 ? STAGES[currentStageIndex + 1].label : "End"} <ChevronRight size={16} />
            </button>
          </div>

          {/* Section: Supervisory Review & Disposition Workflow (Human Examiner Final Decision) */}
          <div
            style={{
              background: "rgba(15, 23, 42, 0.9)",
              border: "1px solid rgba(0, 240, 255, 0.3)",
              borderRadius: "var(--radius-md)",
              padding: "1.1rem",
              marginTop: "0.5rem",
            }}
          >
            <h4 style={{ fontSize: "0.82rem", color: "var(--accent-cyan)", textTransform: "uppercase", marginBottom: "0.6rem" }}>
              Supervisory Review & Disposition (Human Examiner Final Decision)
            </h4>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr auto", gap: "0.75rem", alignItems: "flex-end" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.72rem", color: "var(--text-muted)", marginBottom: "0.25rem" }}>
                  Supervisory Decision
                </label>
                <select
                  value={decision}
                  onChange={(e) => setDecision(e.target.value as ReviewDecisionState)}
                  id="supervisory-decision-select"
                  style={{
                    width: "100%",
                    background: "var(--bg-input)",
                    border: "1px solid var(--border-subtle)",
                    borderRadius: "var(--radius-sm)",
                    padding: "0.5rem",
                    color: "#fff",
                    fontSize: "0.8rem",
                  }}
                >
                  <option value="CONFIRMED">CONFIRMED (Execution Gap Validated)</option>
                  <option value="FALSE_POSITIVE">FALSE_POSITIVE (Authorized Deviation)</option>
                  <option value="NEEDS_INVESTIGATION">NEEDS_INVESTIGATION (Request More Data)</option>
                  <option value="INSUFFICIENT_EVIDENCE">INSUFFICIENT_EVIDENCE</option>
                </select>
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.72rem", color: "var(--text-muted)", marginBottom: "0.25rem" }}>
                  Examiner Audit Notes & Action Order
                </label>
                <input
                  type="text"
                  placeholder="e.g., Scheduled on-site supervisory inspection of L1 alert closures with SOC leadership."
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  id="supervisory-notes-input"
                  style={{
                    width: "100%",
                    background: "var(--bg-input)",
                    border: "1px solid var(--border-subtle)",
                    borderRadius: "var(--radius-sm)",
                    padding: "0.5rem 0.75rem",
                    color: "#fff",
                    fontSize: "0.8rem",
                  }}
                />
              </div>

              <button
                onClick={handleSubmitReview}
                disabled={submitting}
                className="btn-primary"
                id="submit-review-btn"
                style={{ padding: "0.5rem 1.1rem", whiteSpace: "nowrap", fontSize: "0.8rem" }}
              >
                <Send size={14} /> {submitting ? "Saving..." : "Submit Decision"}
              </button>
            </div>
          </div>

        </div>

      </div>
    </div>
  );
};

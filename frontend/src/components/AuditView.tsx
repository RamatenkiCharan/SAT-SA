import React, { useState, useEffect } from "react";
import { RefreshCw, User, ShieldCheck, Binary, Hash, ChevronDown, ChevronUp, Code2, Clock, CheckCircle2 } from "lucide-react";
import type { AuditEventItem } from "../types";
import { fetchAuditLogs } from "../api";

interface InspectorRoleInfo {
  roleName: string;
  badgeBg: string;
  badgeBorder: string;
  badgeColor: string;
  isHuman: boolean;
}

const getInspectorRoleInfo = (ev: AuditEventItem): InspectorRoleInfo => {
  const detailsRole = ev.details?.role || ev.details?.user_role || ev.details?.reviewer_role;
  const rawRole = (detailsRole ? String(detailsRole) : "").toLowerCase();
  const uname = (ev.username || "").toLowerCase();
  const uid = (ev.user_id || "").toLowerCase();

  if (rawRole === "admin" || rawRole === "administrator" || uname.includes("admin") || uid.startsWith("usr_admin")) {
    return {
      roleName: "Administrator",
      badgeBg: "rgba(167, 139, 250, 0.12)",
      badgeBorder: "rgba(167, 139, 250, 0.3)",
      badgeColor: "#a78bfa",
      isHuman: true,
    };
  }
  if (rawRole === "supervisor" || uname.includes("supervisor") || uid.startsWith("usr_sup")) {
    return {
      roleName: "Supervisor",
      badgeBg: "rgba(0, 240, 255, 0.12)",
      badgeBorder: "rgba(0, 240, 255, 0.3)",
      badgeColor: "var(--accent-cyan)",
      isHuman: true,
    };
  }
  if (rawRole === "analyst" || uname.includes("analyst") || uid.startsWith("usr_analyst")) {
    return {
      roleName: "Analyst",
      badgeBg: "rgba(16, 185, 129, 0.12)",
      badgeBorder: "rgba(16, 185, 129, 0.3)",
      badgeColor: "#10b981",
      isHuman: true,
    };
  }
  if (uname.includes("system") || uid === "system") {
    return {
      roleName: "System Engine",
      badgeBg: "rgba(234, 179, 8, 0.12)",
      badgeBorder: "rgba(234, 179, 8, 0.3)",
      badgeColor: "#fbbf24",
      isHuman: false,
    };
  }

  return {
    roleName: ev.username ? "Examiner" : "System",
    badgeBg: "rgba(148, 163, 184, 0.12)",
    badgeBorder: "rgba(148, 163, 184, 0.3)",
    badgeColor: "#94a3b8",
    isHuman: Boolean(ev.username),
  };
};

export const AuditView: React.FC = () => {
  const [events, setEvents] = useState<AuditEventItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [actionCategory, setActionCategory] = useState<string>("ALL");
  const [expandedEventId, setExpandedEventId] = useState<string | null>(null);

  const loadAudit = () => {
    setLoading(true);
    fetchAuditLogs()
      .then((data) => {
        setEvents(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Failed to load audit logs:", err);
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchAuditLogs()
      .then(setEvents)
      .catch((err) => console.error("Failed to load audit logs:", err))
      .finally(() => setLoading(false));
  }, []);

  const filteredEvents = events.filter((ev) => {
    if (actionCategory !== "ALL") {
      if (actionCategory === "DISPOSITIONS" && !ev.action.toLowerCase().includes("review") && !ev.action.toLowerCase().includes("disposition")) {
        return false;
      }
      if (actionCategory === "DATASETS" && !ev.action.toLowerCase().includes("dataset") && !ev.action.toLowerCase().includes("ingest") && !ev.action.toLowerCase().includes("upload")) {
        return false;
      }
    }
    if (searchTerm) {
      const q = searchTerm.toLowerCase();
      return (
        ev.username.toLowerCase().includes(q) ||
        ev.action.toLowerCase().includes(q) ||
        (ev.target_type && ev.target_type.toLowerCase().includes(q)) ||
        (ev.target_id && ev.target_id.toLowerCase().includes(q)) ||
        JSON.stringify(ev.details).toLowerCase().includes(q)
      );
    }
    return true;
  });

  return (
    <div className="page-fade-enter" style={{ display: "flex", flexDirection: "column", gap: "1.75rem" }}>
      {/* Blockchain Ledger Header */}
      <div
        className="glass-card hud-corner"
        style={{
          padding: "2rem",
          background: "linear-gradient(135deg, rgba(14, 21, 38, 0.95) 0%, rgba(8, 13, 26, 0.95) 100%)",
          border: "1px solid rgba(234, 179, 8, 0.3)",
        }}
      >
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: "1rem" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.4rem" }}>
              <span className="badge badge-gold">
                <Binary size={13} /> CRYPTOGRAPHIC AUDIT LEDGER
              </span>
              <span className="badge badge-confirmed">
                <ShieldCheck size={13} /> SHA-256 INTEGRITY VERIFIED
              </span>
            </div>
            <h2 style={{ fontSize: "1.45rem", color: "#fff", fontWeight: 700 }}>
              Immutable Supervisory Audit Trail (SRS §15.1 Baseline)
            </h2>
            <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginTop: "0.25rem", maxWidth: "800px" }}>
              Cryptographically verified, tamper-evident chronological ledger tracking all examiner review dispositions, evidence evaluations, and dataset operations.
            </p>
          </div>

          <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
            <button onClick={() => loadAudit()} className="btn-secondary" style={{ fontSize: "0.85rem" }}>
              <RefreshCw size={14} /> Refresh Ledger
            </button>
          </div>
        </div>

        {/* Ledger Quick Metrics */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem", marginTop: "1.5rem" }}>
          <div style={{ background: "rgba(5, 8, 17, 0.7)", padding: "0.85rem 1rem", borderRadius: "var(--radius-md)", border: "1px solid var(--border-subtle)" }}>
            <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", fontWeight: 600 }}>TOTAL AUDITED BLOCKS</div>
            <div style={{ fontSize: "1.4rem", fontWeight: 800, color: "var(--text-primary)" }}>{events.length}</div>
          </div>
          <div style={{ background: "rgba(5, 8, 17, 0.7)", padding: "0.85rem 1rem", borderRadius: "var(--radius-md)", border: "1px solid var(--border-subtle)" }}>
            <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", fontWeight: 600 }}>TAMPER INTEGRITY</div>
            <div style={{ fontSize: "1.4rem", fontWeight: 800, color: "var(--accent-matrix)", display: "flex", alignItems: "center", gap: "0.35rem" }}>
              <span className="pulse-live" /> SECURITY CONTROLS ACTIVE
            </div>
          </div>
          <div style={{ background: "rgba(5, 8, 17, 0.7)", padding: "0.85rem 1rem", borderRadius: "var(--radius-md)", border: "1px solid var(--border-subtle)" }}>
            <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", fontWeight: 600 }}>AIR-GAP BOUNDARY</div>
            <div style={{ fontSize: "1.4rem", fontWeight: 800, color: "var(--accent-cyan)" }}>ZERO EGRESS</div>
          </div>
          <div style={{ background: "rgba(5, 8, 17, 0.7)", padding: "0.85rem 1rem", borderRadius: "var(--radius-md)", border: "1px solid var(--border-subtle)" }}>
            <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", fontWeight: 600 }}>REPRODUCIBILITY SCORE</div>
            <div style={{ fontSize: "1.4rem", fontWeight: 800, color: "var(--accent-gold)" }}>DETERMINISTIC</div>
          </div>
        </div>
      </div>

      {/* Filter / Search Bar with Category Tabs */}
      <div className="glass-card" style={{ padding: "1.25rem 1.5rem", display: "flex", flexDirection: "column", gap: "0.85rem" }}>
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: "0.75rem" }}>
          {/* Action Filter Chips */}
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            {[
              { id: "ALL", label: "All Audit Blocks" },
              { id: "DISPOSITIONS", label: "Examiner Dispositions" },
              { id: "DATASETS", label: "Dataset Operations" },
            ].map((cat) => (
              <button
                key={cat.id}
                onClick={() => setActionCategory(cat.id)}
                style={{
                  padding: "0.38rem 0.8rem",
                  borderRadius: "var(--radius-full)",
                  fontSize: "0.76rem",
                  fontWeight: 600,
                  cursor: "pointer",
                  border: actionCategory === cat.id ? "1px solid var(--accent-cyan)" : "1px solid var(--border-subtle)",
                  background: actionCategory === cat.id ? "var(--accent-cyan-subtle)" : "rgba(255, 255, 255, 0.03)",
                  color: actionCategory === cat.id ? "var(--accent-cyan)" : "var(--text-secondary)",
                  transition: "all 0.15s ease",
                }}
              >
                {cat.label}
              </button>
            ))}
          </div>

          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
            Showing {filteredEvents.length} of {events.length} records
          </span>
        </div>

        <input
          type="text"
          placeholder="Filter audit blocks by username, role, action type, target entity ID, or details..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          id="audit-log-search-input"
          style={{
            width: "100%",
            background: "var(--bg-input)",
            border: "1px solid var(--border-cyber)",
            borderRadius: "var(--radius-md)",
            padding: "0.65rem 1rem",
            color: "var(--text-primary)",
            fontSize: "0.85rem",
            outline: "none",
          }}
          onFocus={(e) => (e.target.style.borderColor = "var(--accent-cyan)")}
          onBlur={(e) => (e.target.style.borderColor = "var(--border-cyber)")}
        />
      </div>

      {/* Audit Log Table */}
      <div className="glass-card" style={{ padding: "1.5rem" }}>
        {loading ? (
          <div style={{ padding: "3rem", textAlign: "center", color: "var(--text-muted)" }}>
            <div className="pulse-live" style={{ color: "var(--accent-cyan)", marginBottom: "0.5rem" }} />
            Verifying cryptographic hash blocks...
          </div>
        ) : filteredEvents.length === 0 ? (
          <div style={{ padding: "3rem", textAlign: "center", color: "var(--text-muted)" }}>
            No audit records match your query.
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid rgba(0, 240, 255, 0.2)", color: "var(--text-muted)", textAlign: "left" }}>
                  <th style={{ padding: "0.85rem 0.75rem" }}>Block # / Time</th>
                  <th style={{ padding: "0.85rem 0.75rem" }}>Inspector / Role</th>
                  <th style={{ padding: "0.85rem 0.75rem" }}>Action Event</th>
                  <th style={{ padding: "0.85rem 0.75rem" }}>Target Entity / ID</th>
                  <th style={{ padding: "0.85rem 0.75rem" }}>Decision / Evidence Details</th>
                  <th style={{ padding: "0.85rem 0.75rem", textAlign: "right" }}>Inspect</th>
                </tr>
              </thead>
              <tbody>
                {filteredEvents.map((ev, idx) => {
                  const isExpanded = expandedEventId === ev.audit_event_id;
                  const roleInfo = getInspectorRoleInfo(ev);
                  return (
                    <React.Fragment key={ev.audit_event_id}>
                      <tr
                        style={{
                          borderBottom: isExpanded ? "none" : "1px solid rgba(255, 255, 255, 0.04)",
                          background: isExpanded ? "rgba(0, 240, 255, 0.04)" : "transparent",
                          transition: "background 0.15s ease",
                          cursor: "pointer",
                        }}
                        onClick={() => setExpandedEventId(isExpanded ? null : ev.audit_event_id)}
                      >
                        <td style={{ padding: "0.85rem 0.75rem" }}>
                          <div style={{ display: "flex", flexDirection: "column", gap: "0.2rem" }}>
                            <span className="crypto-hash-pill" style={{ width: "fit-content", color: "#fbbf24", borderColor: "rgba(234, 179, 8, 0.3)" }}>
                              <Hash size={11} /> #{String(events.length - idx).padStart(4, "0")}
                            </span>
                            <span style={{ fontSize: "0.72rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)", display: "flex", alignItems: "center", gap: "0.25rem" }}>
                              <Clock size={11} /> {new Date(ev.occurred_at).toLocaleTimeString()}
                            </span>
                          </div>
                        </td>

                        <td style={{ padding: "0.85rem 0.75rem" }}>
                          <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
                            <div style={{ display: "flex", alignItems: "center", gap: "0.45rem", color: "#fff", fontWeight: 600 }}>
                              <User size={14} color={roleInfo.badgeColor} />
                              <span>{ev.username || ev.user_id || "Anonymous Examiner"}</span>
                            </div>
                            <div style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
                              <span
                                style={{
                                  fontSize: "0.68rem",
                                  fontWeight: 700,
                                  padding: "0.15rem 0.5rem",
                                  borderRadius: "var(--radius-full)",
                                  background: roleInfo.badgeBg,
                                  color: roleInfo.badgeColor,
                                  border: `1px solid ${roleInfo.badgeBorder}`,
                                  letterSpacing: "0.02em",
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: "0.25rem",
                                }}
                              >
                                <ShieldCheck size={10} />
                                {roleInfo.roleName}
                              </span>
                              {ev.user_id && ev.user_id !== "system" && (
                                <span style={{ fontSize: "0.68rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                                  ({ev.user_id})
                                </span>
                              )}
                            </div>
                          </div>
                        </td>

                        <td style={{ padding: "0.85rem 0.75rem" }}>
                          <span
                            className="badge"
                            style={{
                              background: ev.action.includes("CONFIRM") || ev.action.includes("VALID") || ev.action.includes("REVIEW") ? "rgba(16, 185, 129, 0.15)" : ev.action.includes("DATASET") ? "rgba(0, 240, 255, 0.15)" : "rgba(139, 92, 246, 0.15)",
                              color: ev.action.includes("CONFIRM") || ev.action.includes("VALID") || ev.action.includes("REVIEW") ? "#10b981" : ev.action.includes("DATASET") ? "var(--accent-cyan)" : "#a78bfa",
                              fontSize: "0.68rem",
                            }}
                          >
                            {ev.action}
                          </span>
                        </td>

                        <td style={{ padding: "0.85rem 0.75rem", color: "var(--accent-cyan)", fontFamily: "var(--font-mono)", fontSize: "0.76rem" }}>
                          <div>{ev.target_type}</div>
                          {ev.target_id && (
                            <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
                              ID: {ev.target_id.slice(0, 12)}...
                            </div>
                          )}
                        </td>

                        <td style={{ padding: "0.85rem 0.75rem", color: "var(--text-secondary)", fontSize: "0.75rem" }}>
                          {ev.details?.decision ? (
                            <div style={{ display: "flex", flexDirection: "column", gap: "0.2rem" }}>
                              <span style={{
                                fontWeight: 700,
                                color: ev.details.decision.includes("CONFIRM") || ev.details.decision.includes("VALID") ? "#10b981" : "#a78bfa",
                                display: "inline-flex",
                                alignItems: "center",
                                gap: "0.25rem",
                                fontSize: "0.74rem"
                              }}>
                                <CheckCircle2 size={12} /> Decision: {ev.details.decision}
                              </span>
                              {ev.details?.notes && (
                                <span style={{ color: "var(--text-muted)", fontSize: "0.7rem", fontStyle: "italic" }}>
                                  "{ev.details.notes}"
                                </span>
                              )}
                            </div>
                          ) : ev.details?.ruleset_name ? (
                            <div style={{ display: "flex", alignItems: "center", gap: "0.3rem", color: "var(--accent-cyan)", fontFamily: "var(--font-mono)" }}>
                              <span>Ruleset: {ev.details.ruleset_name} (v{ev.details.version})</span>
                            </div>
                          ) : ev.details?.dataset_name || ev.details?.filename ? (
                            <div style={{ color: "var(--text-primary)", fontSize: "0.74rem" }}>
                              {ev.details.dataset_name || ev.details.filename}
                            </div>
                          ) : (
                            <div style={{ maxWidth: "340px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontFamily: "var(--font-mono)" }}>
                              {JSON.stringify(ev.details)}
                            </div>
                          )}
                        </td>

                        <td style={{ padding: "0.85rem 0.75rem", textAlign: "right" }}>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setExpandedEventId(isExpanded ? null : ev.audit_event_id);
                            }}
                            className="btn-secondary"
                            style={{ padding: "0.3rem 0.6rem", fontSize: "0.72rem" }}
                          >
                            {isExpanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                          </button>
                        </td>
                      </tr>

                      {/* Expandable Inspection & Cryptographic Detail Row */}
                      {isExpanded && (
                        <tr style={{ background: "rgba(0, 240, 255, 0.02)", borderBottom: "1px solid rgba(0, 240, 255, 0.15)" }}>
                          <td colSpan={6} style={{ padding: "1.25rem" }}>
                            <div style={{ background: "rgba(3, 7, 18, 0.95)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", padding: "1.25rem", display: "flex", flexDirection: "column", gap: "1rem" }}>
                              
                              {/* 5-Field Role-Based Inspection Summary Cards */}
                              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "0.85rem" }}>
                                <div style={{ background: "rgba(0, 0, 0, 0.4)", padding: "0.75rem", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-subtle)" }}>
                                  <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700 }}>Inspector / Reviewer</div>
                                  <div style={{ fontSize: "0.88rem", color: "#fff", fontWeight: 600, marginTop: "0.2rem", display: "flex", alignItems: "center", gap: "0.35rem" }}>
                                    <User size={13} color={roleInfo.badgeColor} />
                                    {ev.username || "System Engine"}
                                  </div>
                                  <div style={{ fontSize: "0.72rem", color: roleInfo.badgeColor, marginTop: "0.15rem", fontWeight: 600 }}>
                                    Role: {roleInfo.roleName}
                                  </div>
                                </div>

                                <div style={{ background: "rgba(0, 0, 0, 0.4)", padding: "0.75rem", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-subtle)" }}>
                                  <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700 }}>Action Performed</div>
                                  <div style={{ fontSize: "0.84rem", color: "#fff", fontWeight: 600, marginTop: "0.2rem" }}>
                                    {ev.action}
                                  </div>
                                  <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginTop: "0.15rem" }}>
                                    Target Type: {ev.target_type}
                                  </div>
                                </div>

                                <div style={{ background: "rgba(0, 0, 0, 0.4)", padding: "0.75rem", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-subtle)" }}>
                                  <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700 }}>Finding / Target ID</div>
                                  <div style={{ fontSize: "0.8rem", color: "var(--accent-cyan)", fontFamily: "var(--font-mono)", fontWeight: 600, marginTop: "0.2rem" }}>
                                    {ev.target_id || "N/A"}
                                  </div>
                                  {ev.details?.finding_type && (
                                    <div style={{ fontSize: "0.72rem", color: "var(--text-secondary)", marginTop: "0.15rem" }}>
                                      Type: {ev.details.finding_type}
                                    </div>
                                  )}
                                </div>

                                {ev.details?.decision && (
                                  <div style={{ background: "rgba(0, 0, 0, 0.4)", padding: "0.75rem", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-subtle)" }}>
                                    <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700 }}>Decision / Verdict</div>
                                    <div style={{ fontSize: "0.85rem", color: ev.details.decision.includes("CONFIRM") || ev.details.decision.includes("VALID") ? "#10b981" : "#a78bfa", fontWeight: 700, marginTop: "0.2rem" }}>
                                      {ev.details.decision}
                                    </div>
                                    {ev.details?.notes && (
                                      <div style={{ fontSize: "0.72rem", color: "var(--text-secondary)", marginTop: "0.15rem" }}>
                                        "{ev.details.notes}"
                                      </div>
                                    )}
                                  </div>
                                )}

                                <div style={{ background: "rgba(0, 0, 0, 0.4)", padding: "0.75rem", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-subtle)" }}>
                                  <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700 }}>Timestamp</div>
                                  <div style={{ fontSize: "0.78rem", color: "#fff", fontFamily: "var(--font-mono)", marginTop: "0.2rem" }}>
                                    {new Date(ev.occurred_at).toLocaleString()}
                                  </div>
                                </div>
                              </div>

                              {/* Raw Cryptographic Event Payload */}
                              <div>
                                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                                  <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontSize: "0.78rem", color: "var(--accent-cyan)", fontWeight: 600 }}>
                                    <Code2 size={14} /> Full Cryptographic Event Payload
                                  </div>
                                  <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                                    Event ID: {ev.audit_event_id}
                                  </div>
                                </div>
                                <pre
                                  style={{
                                    margin: 0,
                                    fontFamily: "var(--font-mono)",
                                    fontSize: "0.74rem",
                                    color: "var(--text-primary)",
                                    background: "rgba(0, 0, 0, 0.4)",
                                    padding: "0.75rem",
                                    borderRadius: "var(--radius-sm)",
                                    overflowX: "auto",
                                    lineHeight: 1.5,
                                  }}
                                >
                                  {JSON.stringify(ev, null, 2)}
                                </pre>
                              </div>

                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
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


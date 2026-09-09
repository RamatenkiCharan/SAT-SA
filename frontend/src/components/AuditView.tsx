import React, { useState, useEffect } from "react";
import { RefreshCw, User } from "lucide-react";
import type { AuditEventItem } from "../types";
import { fetchAuditLogs } from "../api";

export const AuditView: React.FC = () => {
  const [events, setEvents] = useState<AuditEventItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

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
    loadAudit();
  }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      
      {/* Header Info */}
      <div className="glass-card" style={{ padding: "1.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <h2 style={{ fontSize: "1.25rem", color: "#fff" }}>Immutable Supervisory Audit Trail</h2>
            <p style={{ fontSize: "0.82rem", color: "var(--text-muted)", marginTop: "0.2rem" }}>
              Cryptographically auditable provenance tracking of all supervisory review dispositions, evidence evaluations, and dataset operations (SRS §15.1 Baseline).
            </p>
          </div>
          <button onClick={loadAudit} className="btn-secondary" style={{ fontSize: "0.8rem" }}>
            <RefreshCw size={14} /> Refresh Audit Stream
          </button>
        </div>
      </div>

      {/* Audit Log Table */}
      <div className="glass-card" style={{ padding: "1.5rem" }}>
        {loading ? (
          <div style={{ padding: "2rem", textAlign: "center", color: "var(--text-muted)" }}>
            Loading audit logs...
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border-subtle)", color: "var(--text-muted)", textAlign: "left" }}>
                  <th style={{ padding: "0.75rem" }}>Timestamp</th>
                  <th style={{ padding: "0.75rem" }}>Examiner / User</th>
                  <th style={{ padding: "0.75rem" }}>Action Event</th>
                  <th style={{ padding: "0.75rem" }}>Target Entity</th>
                  <th style={{ padding: "0.75rem" }}>Audit Details</th>
                </tr>
              </thead>
              <tbody>
                {events.map((ev) => (
                  <tr key={ev.audit_event_id} style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.04)" }}>
                    <td style={{ padding: "0.75rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                      {new Date(ev.occurred_at).toLocaleString()}
                    </td>
                    <td style={{ padding: "0.75rem", color: "#fff", fontWeight: 600 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                        <User size={14} color="var(--accent-cyan)" />
                        {ev.username}
                      </div>
                    </td>
                    <td style={{ padding: "0.75rem" }}>
                      <span className="badge badge-purple" style={{ fontSize: "0.68rem" }}>
                        {ev.action}
                      </span>
                    </td>
                    <td style={{ padding: "0.75rem", color: "var(--accent-cyan)", fontFamily: "var(--font-mono)" }}>
                      {ev.target_type}: {ev.target_id ? ev.target_id.slice(0, 8) + "..." : "system"}
                    </td>
                    <td style={{ padding: "0.75rem", color: "var(--text-secondary)", fontSize: "0.75rem" }}>
                      {JSON.stringify(ev.details)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

    </div>
  );
};

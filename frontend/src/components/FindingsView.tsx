import React, { useState } from "react";
import { ArrowUpRight } from "lucide-react";
import type { Finding } from "../types";

interface FindingsViewProps {
  findings: Finding[];
  onSelectFinding: (finding: Finding) => void;
}

export const FindingsView: React.FC<FindingsViewProps> = ({
  findings,
  onSelectFinding,
}) => {
  const [selectedSector, setSelectedSector] = useState<string>("ALL");
  const [selectedType, setSelectedType] = useState<string>("ALL");
  const [selectedMinPriority, setSelectedMinPriority] = useState<number>(0);
  const [searchQuery, setSearchQuery] = useState<string>("");

  const sectors = ["ALL", ...Array.from(new Set(findings.map((f) => f.sector)))];
  const findingTypes = [
    { value: "ALL", label: "All Finding Types" },
    { value: "FAST_CLOSURE", label: "Fast Closure (FR-030)" },
    { value: "ESCALATION_GAP", label: "Escalation Gap (FR-032)" },
    { value: "REPEATED_UNRESOLVED_ALERTS", label: "Repeated Unresolved (FR-033)" },
    { value: "COVERAGE_GAP", label: "Coverage Gap (FR-041)" },
  ];

  const filteredFindings = findings.filter((f) => {
    if (selectedSector !== "ALL" && f.sector.toLowerCase() !== selectedSector.toLowerCase()) {
      return false;
    }
    if (selectedType !== "ALL" && f.finding_type !== selectedType) {
      return false;
    }
    if (f.priority_score < selectedMinPriority) {
      return false;
    }
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const matchText = `${f.title} ${f.cse_name} ${f.sector} ${f.headline}`.toLowerCase();
      if (!matchText.includes(q)) return false;
    }
    return true;
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      
      {/* Header & Filter Controls */}
      <div className="glass-card" style={{ padding: "1.25rem" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1rem" }}>
          <div>
            <h2 style={{ fontSize: "1.25rem", color: "#fff" }}>Supervisory Findings Triage</h2>
            <p style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
              Algorithmic evidence-based detection of operational execution gaps and monitoring negative space.
            </p>
          </div>
          <span className="badge badge-cyan" style={{ fontSize: "0.75rem" }}>
            {filteredFindings.length} of {findings.length} findings displayed
          </span>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr", gap: "0.75rem" }}>
          
          {/* Search */}
          <div style={{ position: "relative" }}>
            <input
              type="text"
              placeholder="Search by entity, sector, or keyword..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                width: "100%",
                background: "var(--bg-input)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-md)",
                padding: "0.55rem 0.85rem",
                color: "#fff",
                fontSize: "0.85rem",
              }}
            />
          </div>

          {/* Sector Filter */}
          <select
            value={selectedSector}
            onChange={(e) => setSelectedSector(e.target.value)}
            style={{
              background: "var(--bg-input)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              padding: "0.55rem 0.85rem",
              color: "#fff",
              fontSize: "0.85rem",
            }}
          >
            {sectors.map((s) => (
              <option key={s} value={s}>
                Sector: {s}
              </option>
            ))}
          </select>

          {/* Type Filter */}
          <select
            value={selectedType}
            onChange={(e) => setSelectedType(e.target.value)}
            style={{
              background: "var(--bg-input)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              padding: "0.55rem 0.85rem",
              color: "#fff",
              fontSize: "0.85rem",
            }}
          >
            {findingTypes.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>

          {/* Priority Filter */}
          <select
            value={selectedMinPriority}
            onChange={(e) => setSelectedMinPriority(parseFloat(e.target.value))}
            style={{
              background: "var(--bg-input)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              padding: "0.55rem 0.85rem",
              color: "#fff",
              fontSize: "0.85rem",
            }}
          >
            <option value={0}>Priority: All</option>
            <option value={0.75}>High Priority (&ge; 0.75)</option>
            <option value={0.5}>Medium+ Priority (&ge; 0.50)</option>
          </select>

        </div>
      </div>

      {/* Findings List */}
      <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        {filteredFindings.map((f) => {
          const comps = f.priority_components;
          return (
            <div
              key={f.finding_id}
              className="glass-card glass-card-interactive"
              style={{
                padding: "1.25rem 1.5rem",
                display: "grid",
                gridTemplateColumns: "3fr 2fr 1fr",
                gap: "1.5rem",
                alignItems: "center",
              }}
            >
              {/* Left Column: Finding Meta & Rationale */}
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.4rem" }}>
                  <span className={`badge badge-${f.priority_label.toLowerCase()}`}>
                    {f.priority_label}
                  </span>
                  <span className="badge badge-purple" style={{ fontSize: "0.68rem" }}>
                    {f.finding_type}
                  </span>
                  {f.review_status ? (
                    <span className="badge badge-confirmed" style={{ fontSize: "0.68rem" }}>
                      ✓ {f.review_status}
                    </span>
                  ) : (
                    <span className="badge" style={{ background: "rgba(100, 116, 139, 0.2)", color: "var(--text-muted)", fontSize: "0.68rem" }}>
                      PENDING EXAMINER REVIEW
                    </span>
                  )}
                </div>

                <h3 style={{ fontSize: "1.05rem", color: "#fff", marginBottom: "0.3rem" }}>
                  {f.title}
                </h3>
                
                <div style={{ fontSize: "0.82rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>
                  {f.headline}
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "1rem", fontSize: "0.75rem", color: "var(--text-muted)" }}>
                  <span>Entity: <strong style={{ color: "#fff" }}>{f.cse_name}</strong></span>
                  <span>Sector: <strong style={{ color: "var(--accent-cyan)" }}>{f.sector}</strong></span>
                  <span>Records: <strong style={{ color: "#fff" }}>{f.evidence_record_count}</strong></span>
                </div>
              </div>

              {/* Middle Column: Decomposed Priority Components Breakdown */}
              <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "0.85rem", borderRadius: "var(--radius-md)", border: "1px solid rgba(255, 255, 255, 0.05)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", marginBottom: "0.35rem" }}>
                  <span style={{ color: "var(--text-muted)" }}>Priority Fusion (§10.5)</span>
                  <span style={{ color: "var(--accent-cyan)", fontFamily: "var(--font-mono)", fontWeight: 700 }}>
                    Score: {f.priority_score.toFixed(3)}
                  </span>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem", fontSize: "0.7rem" }}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "var(--text-secondary)" }}>Signal Strength (30%)</span>
                    <span style={{ color: "#fff" }}>{comps.signal_strength.toFixed(2)}</span>
                  </div>
                  <div className="progress-container">
                    <div className="progress-bar" style={{ width: `${comps.signal_strength * 100}%`, background: "var(--accent-blue)" }}></div>
                  </div>

                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "var(--text-secondary)" }}>Peer Deviation (25%)</span>
                    <span style={{ color: "#fff" }}>{comps.peer_deviation.toFixed(2)}</span>
                  </div>
                  <div className="progress-container">
                    <div className="progress-bar" style={{ width: `${comps.peer_deviation * 100}%`, background: "var(--accent-amber)" }}></div>
                  </div>

                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "var(--text-secondary)" }}>Data Trust (Penalty)</span>
                    <span style={{ color: "#fff" }}>{(1 - comps.data_uncertainty).toFixed(2)}</span>
                  </div>
                  <div className="progress-container">
                    <div className="progress-bar" style={{ width: `${(1 - comps.data_uncertainty) * 100}%`, background: "var(--accent-emerald)" }}></div>
                  </div>
                </div>
              </div>

              {/* Right Column: Drill-Down Action Button */}
              <div style={{ textAlign: "right" }}>
                <button
                  onClick={() => onSelectFinding(f)}
                  className="btn-primary"
                  style={{ width: "100%", justifyContent: "center" }}
                >
                  Inspect Evidence <ArrowUpRight size={16} />
                </button>
              </div>

            </div>
          );
        })}
      </div>

    </div>
  );
};

import React, { useState } from "react";
import { ArrowUpRight, Search } from "lucide-react";
import type { Finding } from "../types";

interface FindingsViewProps {
  findings: Finding[];
  onSelectFinding: (finding: Finding) => void;
  searchQuery?: string;
  onSearchChange?: (q: string) => void;
}

export const FindingsView: React.FC<FindingsViewProps> = ({
  findings,
  onSelectFinding,
  searchQuery: externalSearchQuery,
  onSearchChange: externalOnSearchChange,
}) => {
  const [selectedSector, setSelectedSector] = useState<string>("ALL");
  const [selectedType, setSelectedType] = useState<string>("ALL");
  const [selectedMinPriority, setSelectedMinPriority] = useState<number>(0);
  const [internalSearchQuery, setInternalSearchQuery] = useState<string>("");

  const activeSearchQuery = externalSearchQuery !== undefined ? externalSearchQuery : internalSearchQuery;
  const handleSearchChange = (q: string) => {
    if (externalOnSearchChange) {
      externalOnSearchChange(q);
    } else {
      setInternalSearchQuery(q);
    }
  };

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
    if (activeSearchQuery) {
      const q = activeSearchQuery.toLowerCase();
      const matchText = `${f.title} ${f.cse_name} ${f.sector} ${f.headline} ${f.finding_type}`.toLowerCase();
      if (!matchText.includes(q)) return false;
    }
    return true;
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      
      {/* Header & Filter Controls */}
      <div className="glass-card" style={{ padding: "1.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "1rem", marginBottom: "1.25rem" }}>
          <div>
            <h2 style={{ fontSize: "1.25rem", color: "#fff", fontWeight: 700 }}>Supervisory Findings Triage</h2>
            <p style={{ fontSize: "0.82rem", color: "#64748b", marginTop: "0.2rem" }}>
              Algorithmic evidence-based detection of operational execution gaps and monitoring negative space.
            </p>
          </div>
          <span className="badge badge-cyan" style={{ fontSize: "0.75rem" }}>
            {filteredFindings.length} of {findings.length} findings displayed
          </span>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "0.85rem" }}>
          
          {/* Search */}
          <div style={{ position: "relative" }}>
            <Search size={15} color="var(--accent-cyan)" style={{ position: "absolute", left: "10px", top: "50%", transform: "translateY(-50%)" }} />
            <input
              type="text"
              placeholder="Search entity, sector, or keyword..."
              value={activeSearchQuery}
              onChange={(e) => handleSearchChange(e.target.value)}
              id="findings-search-input"
              style={{
                width: "100%",
                background: "var(--bg-input)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-md)",
                padding: "0.55rem 0.85rem 0.55rem 2rem",
                color: "#fff",
                fontSize: "0.85rem",
                outline: "none",
              }}
              onFocus={(e) => (e.target.style.borderColor = "var(--border-active)")}
              onBlur={(e) => (e.target.style.borderColor = "var(--border-subtle)")}
            />
          </div>

          {/* Sector Filter */}
          <select
            value={selectedSector}
            onChange={(e) => setSelectedSector(e.target.value)}
            id="findings-sector-filter"
            style={{
              background: "var(--bg-input)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              padding: "0.55rem 0.85rem",
              color: "#fff",
              fontSize: "0.85rem",
              outline: "none",
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
            id="findings-type-filter"
            style={{
              background: "var(--bg-input)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              padding: "0.55rem 0.85rem",
              color: "#fff",
              fontSize: "0.85rem",
              outline: "none",
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
            id="findings-priority-filter"
            style={{
              background: "var(--bg-input)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              padding: "0.55rem 0.85rem",
              color: "#fff",
              fontSize: "0.85rem",
              outline: "none",
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
        {filteredFindings.length === 0 ? (
          <div className="glass-card" style={{ padding: "3rem", textAlign: "center", color: "#64748b" }}>
            No findings match your current filters. Try resetting search criteria.
          </div>
        ) : (
          filteredFindings.map((f) => {
            const comps = f.priority_components;
            return (
              <div
                key={f.finding_id}
                className="glass-card glass-card-interactive"
                style={{
                  padding: "1.35rem 1.5rem",
                  display: "grid",
                  gridTemplateColumns: "3fr 2fr 1fr",
                  gap: "1.5rem",
                  alignItems: "center",
                }}
              >
                {/* Left Column: Finding Meta & Rationale */}
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem", flexWrap: "wrap" }}>
                    <span className={`badge badge-${f.priority_label.toLowerCase()}`}>
                      {f.priority_label}
                    </span>
                    <span className="badge badge-purple" style={{ fontSize: "0.68rem" }}>
                      {f.finding_type}
                    </span>
                    {f.evidence_state && (
                      <span
                        className={`badge badge-${
                          f.evidence_state === "SUPPORTED"
                            ? "emerald"
                            : f.evidence_state === "WEAKLY_SUPPORTED"
                            ? "amber"
                            : "rose"
                        }`}
                        style={{ fontSize: "0.68rem" }}
                        title={`Evidentiary inference state: ${f.evidence_state}`}
                      >
                        {f.evidence_state.replace("_", " ")}
                      </span>
                    )}
                    {f.review_status ? (
                      <span className="badge badge-confirmed" style={{ fontSize: "0.68rem" }}>
                        ✓ {f.review_status}
                      </span>
                    ) : (
                      <span className="badge" style={{ background: "rgba(100, 116, 139, 0.2)", color: "#94a3b8", fontSize: "0.68rem" }}>
                        PENDING EXAMINER REVIEW
                      </span>
                    )}
                  </div>

                  <h3 style={{ fontSize: "1.05rem", color: "#fff", marginBottom: "0.35rem", fontWeight: 700 }}>
                    {f.title}
                  </h3>
                  
                  <div style={{ fontSize: "0.83rem", color: "#94a3b8", marginBottom: "0.6rem", lineHeight: 1.45 }}>
                    {f.headline}
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: "1.15rem", fontSize: "0.76rem", color: "#64748b", flexWrap: "wrap" }}>
                    <span>Entity: <strong style={{ color: "#fff" }}>{f.cse_name}</strong></span>
                    <span>Sector: <strong style={{ color: "var(--accent-cyan)" }}>{f.sector}</strong></span>
                    <span>Records: <strong style={{ color: "#fff" }}>{f.evidence_record_count}</strong></span>
                  </div>
                </div>

                {/* Middle Column: Decomposed Priority Components Breakdown */}
                <div style={{ background: "rgba(15, 23, 42, 0.65)", padding: "0.95rem", borderRadius: "var(--radius-md)", border: "1px solid rgba(255, 255, 255, 0.06)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.76rem", marginBottom: "0.45rem" }}>
                    <span style={{ color: "#64748b", fontWeight: 600 }}>Priority Fusion (§10.5)</span>
                    <span style={{ color: "var(--accent-cyan)", fontFamily: "var(--font-mono)", fontWeight: 800 }}>
                      Score: {f.priority_score.toFixed(3)}
                    </span>
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem", fontSize: "0.7rem" }}>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ color: "#94a3b8" }}>Signal Strength (30%)</span>
                      <span style={{ color: "#fff", fontWeight: 600 }}>{comps.signal_strength.toFixed(2)}</span>
                    </div>
                    <div className="progress-container">
                      <div className="progress-bar" style={{ width: `${comps.signal_strength * 100}%`, background: "var(--accent-blue)" }}></div>
                    </div>

                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ color: "#94a3b8" }}>Peer Deviation (25%)</span>
                      <span style={{ color: "#fff", fontWeight: 600 }}>{comps.peer_deviation.toFixed(2)}</span>
                    </div>
                    <div className="progress-container">
                      <div className="progress-bar" style={{ width: `${comps.peer_deviation * 100}%`, background: "var(--accent-amber)" }}></div>
                    </div>

                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ color: "#94a3b8" }}>Data Trust (Penalty)</span>
                      <span style={{ color: "#fff", fontWeight: 600 }}>{(1 - comps.data_uncertainty).toFixed(2)}</span>
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
                    id={`inspect-evidence-btn-${f.finding_id.slice(0, 8)}`}
                    style={{ width: "100%", justifyContent: "center", fontSize: "0.82rem" }}
                  >
                    Inspect Evidence <ArrowUpRight size={16} />
                  </button>
                </div>

              </div>
            );
          })
        )}
      </div>

    </div>
  );
};


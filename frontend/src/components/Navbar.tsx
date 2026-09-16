import React from "react";
import { Database, Zap, Search } from "lucide-react";
import type { DatasetItem } from "../types";

interface NavbarProps {
  activeVersionId: string | null;
  datasets: DatasetItem[];
  onLoadDemo: (type: "critical_infrastructure" | "held_out_test") => void;
  activeTabLabel: string;
  searchQuery?: string;
  onSearchChange?: (q: string) => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeVersionId,
  datasets,
  onLoadDemo,
  activeTabLabel,
  searchQuery,
  onSearchChange,
}) => {
  const activeDataset = datasets.find(
    (d) =>
      d.versions?.some((v) => v.dataset_version_id === activeVersionId) ||
      d.dataset_id === activeVersionId
  );

  return (
    <header
      style={{
        borderBottom: "1px solid var(--border-subtle)",
        background: "rgba(5, 8, 20, 0.94)",
        backdropFilter: "blur(18px)",
        WebkitBackdropFilter: "blur(18px)",
        position: "sticky",
        top: 0,
        zIndex: 40,
        padding: "0.75rem 1.75rem",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: "1rem",
        }}
      >
        {/* Left: Active Section & Air-Gapped Indicator */}
        <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
          <div>
            <h1 style={{ fontSize: "1.15rem", fontWeight: 700, color: "#fff", margin: 0, letterSpacing: "-0.01em" }}>
              {activeTabLabel}
            </h1>
          </div>

          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.45rem",
              padding: "0.22rem 0.65rem",
              borderRadius: "var(--radius-full)",
              background: "var(--accent-emerald-subtle)",
              border: "1px solid rgba(16, 185, 129, 0.35)",
              fontSize: "0.72rem",
              color: "#34d399",
              fontWeight: 700,
              letterSpacing: "0.04em",
            }}
          >
            <span className="pulse-live" />
            AIR-GAPPED OFFLINE
          </div>
        </div>

        {/* Center: Quick Search Bar (Optional filter helper) */}
        {onSearchChange !== undefined && (
          <div style={{ flex: "1 1 240px", maxWidth: "340px", position: "relative" }}>
            <Search
              size={14}
              color="var(--accent-cyan)"
              style={{ position: "absolute", left: "10px", top: "50%", transform: "translateY(-50%)" }}
            />
            <input
              type="text"
              placeholder="Search findings, CSEs, sectors..."
              value={searchQuery || ""}
              onChange={(e) => onSearchChange(e.target.value)}
              id="global-header-search"
              style={{
                width: "100%",
                background: "var(--bg-input)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-md)",
                padding: "0.45rem 0.75rem 0.45rem 2rem",
                color: "#fff",
                fontSize: "0.8rem",
                outline: "none",
                transition: "border-color 0.2s ease",
              }}
              onFocus={(e) => (e.target.style.borderColor = "var(--border-active)")}
              onBlur={(e) => (e.target.style.borderColor = "var(--border-subtle)")}
            />
          </div>
        )}

        {/* Right Utility Bar: Active Dataset & Load Demo */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.85rem" }}>
          {/* Active Dataset Indicator */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
              background: "rgba(15, 23, 42, 0.7)",
              border: "1px solid var(--border-subtle)",
              padding: "0.38rem 0.8rem",
              borderRadius: "var(--radius-sm)",
              fontSize: "0.75rem",
              color: "#94a3b8",
            }}
            title={activeDataset?.name || "Default Benchmark Bundle"}
          >
            <Database size={14} color="var(--accent-cyan)" />
            <span style={{ maxWidth: "180px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "#f8fafc", fontWeight: 500 }}>
              {activeDataset ? activeDataset.name : "National Power Grid Benchmark"}
            </span>
            <code
              className="font-mono"
              style={{
                fontSize: "0.7rem",
                color: "var(--accent-cyan)",
                background: "rgba(0, 0, 0, 0.35)",
                padding: "0.1rem 0.4rem",
                borderRadius: "3px",
                border: "1px solid rgba(0, 216, 246, 0.2)",
              }}
            >
              {activeVersionId ? activeVersionId.slice(0, 8) : "NPDC-01"}
            </code>
          </div>

          {/* Load Demo Pack Action */}
          <button
            onClick={() => onLoadDemo("critical_infrastructure")}
            className="btn-secondary"
            style={{ fontSize: "0.78rem", padding: "0.42rem 0.9rem" }}
            title="Reload Default National Critical Infrastructure Evidence Pack"
            id="reload-demo-header-btn"
          >
            <Zap size={14} color="var(--accent-cyan)" /> Load Demo Pack
          </button>
        </div>
      </div>
    </header>
  );
};


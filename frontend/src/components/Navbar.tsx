import React from "react";
import { Shield, Database, Activity, FileText, CheckCircle2, Lock } from "lucide-react";
import type { DatasetItem } from "../types";

interface NavbarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  activeVersionId: string | null;
  datasets: DatasetItem[];
  onLoadDemo: (type: "critical_infrastructure" | "held_out_test") => void;
  loadingDemo?: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  setActiveTab,
  onLoadDemo,
  loadingDemo,
}) => {
  const navItems = [
    { id: "overview", label: "Executive Overview", icon: Activity },
    { id: "findings", label: "Supervisory Findings", icon: Shield },
    { id: "benchmarks", label: "Peer Benchmarks", icon: Database },
    { id: "negativespace", label: "Negative Space Map", icon: FileText },
    { id: "validation", label: "Yield & Validation", icon: CheckCircle2 },
    { id: "datasets", label: "Datasets", icon: Database },
    { id: "audit", label: "Audit Log", icon: Lock },
  ];

  return (
    <header style={{ borderBottom: "1px solid var(--border-subtle)", background: "rgba(10, 14, 23, 0.9)", backdropFilter: "blur(12px)", position: "sticky", top: 0, zIndex: 100 }}>
      <div style={{ maxWidth: "1400px", margin: "0 auto", padding: "0.75rem 1.5rem", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        
        {/* Brand & Identity */}
        <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
          <div style={{ width: "42px", height: "42px", borderRadius: "10px", background: "linear-gradient(135deg, #00f0ff 0%, #3b82f6 100%)", display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "0 0 15px rgba(0, 240, 255, 0.4)" }}>
            <Shield size={24} color="#000" strokeWidth={2.5} />
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
              <span style={{ fontSize: "1.25rem", fontWeight: 800, letterSpacing: "-0.03em", color: "#fff" }}>
                SAT<span style={{ color: "var(--accent-cyan)" }}>-SA</span>
              </span>
              <span className="badge badge-cyan" style={{ fontSize: "0.68rem" }}>
                SUPERVISORY ANALYTICS
              </span>
              <span className="badge" style={{ background: "rgba(16, 185, 129, 0.15)", color: "#10b981", border: "1px solid rgba(16, 185, 129, 0.3)" }}>
                <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#10b981", display: "inline-block", marginRight: "3px" }} className="pulse-live"></span>
                AIR-GAPPED OFFLINE
              </span>
            </div>
            <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", margin: 0 }}>
              Supervisory Analytics Tool for SOC Assessment • NCIIPC Examiner
            </p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                style={{
                  background: isActive ? "rgba(0, 240, 255, 0.1)" : "transparent",
                  color: isActive ? "var(--accent-cyan)" : "var(--text-secondary)",
                  border: isActive ? "1px solid rgba(0, 240, 255, 0.3)" : "1px solid transparent",
                  borderRadius: "var(--radius-md)",
                  padding: "0.5rem 0.85rem",
                  fontSize: "0.85rem",
                  fontWeight: isActive ? 600 : 500,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.4rem",
                  transition: "all 0.15s ease",
                }}
              >
                <Icon size={16} />
                {item.label}
              </button>
            );
          })}
        </nav>

        {/* Quick Demo Switcher */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <button
            onClick={() => onLoadDemo("critical_infrastructure")}
            disabled={loadingDemo}
            className="btn-secondary"
            style={{ fontSize: "0.78rem", padding: "0.4rem 0.8rem", opacity: loadingDemo ? 0.7 : 1 }}
            title="Reload Default Critical Infrastructure Multi-CSE Benchmark"
          >
            {loadingDemo ? "⚡ Loading..." : "⚡ Load Demo Pack"}
          </button>
        </div>

      </div>
    </header>
  );
};

import React from "react";
import {
  Shield,
  Activity,
  ShieldAlert,
  BarChart3,
  EyeOff,
  CheckCircle2,
  Database,
  FileText,
  HelpCircle,
  ChevronLeft,
  ChevronRight,
  LogOut,
} from "lucide-react";

export type TabId =
  | "overview"
  | "findings"
  | "benchmarks"
  | "negativespace"
  | "validation"
  | "datasets"
  | "audit"
  | "help";

interface SidebarProps {
  activeTab: TabId;
  setActiveTab: (tab: TabId) => void;
  isCollapsed: boolean;
  setIsCollapsed: (collapsed: boolean) => void;
  onExitToLanding: () => void;
  findingsCount: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  setActiveTab,
  isCollapsed,
  setIsCollapsed,
  onExitToLanding,
  findingsCount,
}) => {
  const navItems = [
    { id: "overview" as TabId, label: "Executive Overview", icon: Activity },
    { id: "findings" as TabId, label: "Supervisory Findings", icon: ShieldAlert, badge: findingsCount },
    { id: "benchmarks" as TabId, label: "Peer Benchmarks", icon: BarChart3 },
    { id: "negativespace" as TabId, label: "Negative Space", icon: EyeOff },
    { id: "validation" as TabId, label: "Yield & Validation", icon: CheckCircle2 },
    { id: "datasets" as TabId, label: "Datasets", icon: Database },
    { id: "audit" as TabId, label: "Audit Logs", icon: FileText },
    { id: "help" as TabId, label: "Help & Reference", icon: HelpCircle },
  ];

  return (
    <aside
      className={`sidebar ${isCollapsed ? "collapsed" : "expanded"}`}
      aria-label="Supervisory Navigation"
    >
      {/* Brand & Identity */}
      <div
        style={{
          padding: isCollapsed ? "1.25rem 0.5rem" : "1.25rem 1.25rem",
          display: "flex",
          alignItems: "center",
          gap: "0.75rem",
          borderBottom: "1px solid var(--border-subtle)",
          justifyContent: isCollapsed ? "center" : "flex-start",
        }}
      >
        <button
          onClick={onExitToLanding}
          title="Return to Landing Page"
          style={{
            width: "36px",
            height: "36px",
            borderRadius: "var(--radius-sm)",
            background: "linear-gradient(135deg, #00d8f6 0%, #0284c7 100%)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
            cursor: "pointer",
            border: "none",
            boxShadow: "0 0 15px rgba(0, 216, 246, 0.3)",
            transition: "transform 0.18s ease",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.transform = "scale(1.05)")}
          onMouseLeave={(e) => (e.currentTarget.style.transform = "scale(1)")}
        >
          <Shield size={20} color="#050814" strokeWidth={2.6} />
        </button>
        {!isCollapsed && (
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: "1.1rem", fontWeight: 800, color: "#fff", letterSpacing: "-0.02em" }}>
              SAT<span style={{ color: "var(--accent-cyan)" }}>-SA</span>
            </div>
            <div style={{ fontSize: "0.68rem", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.06em", fontWeight: 600 }}>
              Supervisory Suite
            </div>
          </div>
        )}
      </div>

      {/* Main Navigation Items */}
      <nav
        style={{
          flex: 1,
          padding: "1rem 0.5rem",
          display: "flex",
          flexDirection: "column",
          gap: "0.35rem",
          overflowY: "auto",
        }}
      >
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              title={isCollapsed ? item.label : undefined}
              id={`nav-${item.id}`}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.75rem",
                width: "100%",
                padding: isCollapsed ? "0.65rem 0" : "0.65rem 0.85rem",
                justifyContent: isCollapsed ? "center" : "flex-start",
                borderRadius: "var(--radius-md)",
                background: isActive ? "rgba(0, 216, 246, 0.12)" : "transparent",
                color: isActive ? "var(--accent-cyan)" : "#94a3b8",
                border: isActive ? "1px solid rgba(0, 216, 246, 0.35)" : "1px solid transparent",
                boxShadow: isActive ? "0 0 16px rgba(0, 216, 246, 0.12)" : "none",
                cursor: "pointer",
                fontSize: "0.85rem",
                fontWeight: isActive ? 700 : 500,
                transition: "all 0.18s ease",
                position: "relative",
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  e.currentTarget.style.background = "rgba(255, 255, 255, 0.04)";
                  e.currentTarget.style.color = "#f8fafc";
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  e.currentTarget.style.background = "transparent";
                  e.currentTarget.style.color = "#94a3b8";
                }
              }}
            >
              <Icon size={18} style={{ flexShrink: 0, color: isActive ? "var(--accent-cyan)" : "currentColor" }} />
              {!isCollapsed && (
                <span style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", flex: 1, textAlign: "left" }}>
                  {item.label}
                </span>
              )}
              {!isCollapsed && item.badge !== undefined && item.badge > 0 && (
                <span
                  style={{
                    fontSize: "0.7rem",
                    fontWeight: 700,
                    background: "rgba(239, 68, 68, 0.2)",
                    color: "#fca5a5",
                    border: "1px solid var(--border-danger)",
                    padding: "0.1rem 0.45rem",
                    borderRadius: "var(--radius-full)",
                  }}
                >
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Footer / Toggle & Exit */}
      <div
        style={{
          padding: "0.75rem 0.5rem",
          borderTop: "1px solid var(--border-subtle)",
          display: "flex",
          flexDirection: "column",
          gap: "0.35rem",
        }}
      >
        <button
          onClick={onExitToLanding}
          title={isCollapsed ? "Landing Page" : undefined}
          id="nav-exit-landing"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.75rem",
            width: "100%",
            padding: isCollapsed ? "0.6rem 0" : "0.6rem 0.85rem",
            justifyContent: isCollapsed ? "center" : "flex-start",
            borderRadius: "var(--radius-md)",
            background: "transparent",
            color: "#64748b",
            border: "none",
            cursor: "pointer",
            fontSize: "0.82rem",
            transition: "all 0.15s ease",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.color = "#f8fafc";
            e.currentTarget.style.background = "rgba(255, 255, 255, 0.04)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = "#64748b";
            e.currentTarget.style.background = "transparent";
          }}
        >
          <LogOut size={16} style={{ flexShrink: 0 }} />
          {!isCollapsed && <span>Landing Page</span>}
        </button>

        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          title={isCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
          id="toggle-sidebar-btn"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.75rem",
            width: "100%",
            padding: isCollapsed ? "0.6rem 0" : "0.6rem 0.85rem",
            justifyContent: isCollapsed ? "center" : "flex-start",
            borderRadius: "var(--radius-md)",
            background: "rgba(255, 255, 255, 0.03)",
            color: "#94a3b8",
            border: "1px solid var(--border-subtle)",
            cursor: "pointer",
            fontSize: "0.82rem",
            transition: "all 0.15s ease",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = "var(--border-card)";
            e.currentTarget.style.color = "#f8fafc";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = "var(--border-subtle)";
            e.currentTarget.style.color = "#94a3b8";
          }}
        >
          {isCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          {!isCollapsed && <span>Collapse Sidebar</span>}
        </button>
      </div>
    </aside>
  );
};


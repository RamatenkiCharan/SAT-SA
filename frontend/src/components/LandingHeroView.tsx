import React from "react";
import { Shield, ArrowRight, Activity, Database, CheckCircle2, Lock, FileSearch } from "lucide-react";
import { TypewriterText } from "./TypewriterText";

interface LandingHeroViewProps {
  onStartMonitoring: () => void;
  onLoadDemo: (type: "critical_infrastructure" | "held_out_test") => void;
}

export const LandingHeroView: React.FC<LandingHeroViewProps> = ({
  onStartMonitoring,
  onLoadDemo,
}) => {

  return (
    <div
      className="page-fade-enter"
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "calc(100vh - 120px)",
        padding: "3.5rem 1.5rem",
        textAlign: "center",
      }}
    >
      <div style={{ maxWidth: "920px", margin: "0 auto", display: "flex", flexDirection: "column", alignItems: "center" }}>
        
        {/* Identity & Supervisory Spec Badge */}
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "0.6rem",
            padding: "0.45rem 1.15rem",
            borderRadius: "var(--radius-full)",
            background: "rgba(0, 216, 246, 0.08)",
            border: "1px solid rgba(0, 216, 246, 0.3)",
            boxShadow: "0 0 20px rgba(0, 216, 246, 0.12)",
            marginBottom: "2.25rem",
          }}
        >
          <Shield size={16} color="var(--accent-cyan)" />
          <span style={{ fontSize: "0.82rem", fontWeight: 700, color: "var(--accent-cyan)", letterSpacing: "0.05em" }}>
            EVIDENCE-BASED SOC SUPERVISORY INTELLIGENCE
          </span>
        </div>

        {/* Central Dominant Hero Statement */}
        <h1
          style={{
            fontSize: "clamp(2.5rem, 5.8vw, 4.4rem)",
            fontWeight: 800,
            lineHeight: 1.12,
            letterSpacing: "-0.035em",
            color: "#f8fafc",
            marginBottom: "1.5rem",
            minHeight: "2.3em",
          }}
        >
          Turn SOC Evidence Into{" "}
          <span
            style={{
              background: "linear-gradient(135deg, #00d8f6 0%, #38bdf8 45%, #10b981 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              filter: "drop-shadow(0 2px 16px rgba(0, 216, 246, 0.3))",
            }}
          >
            Supervisory Assurance
          </span>
        </h1>

        {/* Supporting Description with Cinematic Typewriter Reveal */}
        <p
          style={{
            fontSize: "clamp(1.05rem, 2vw, 1.25rem)",
            color: "#94a3b8",
            lineHeight: 1.65,
            maxWidth: "760px",
            minHeight: "3.5em",
            marginBottom: "2.75rem",
          }}
        >
          <TypewriterText
            text="Analyze operational evidence, reconstruct workflows, benchmark performance, and expose hidden supervisory gaps."
            speed={28}
            initialDelay={300}
          />
        </p>


        {/* Primary CTA: Start Monitoring */}
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            justifyContent: "center",
            gap: "1.15rem",
            marginBottom: "3.75rem",
          }}
        >
          <button
            onClick={onStartMonitoring}
            className="btn-primary"
            style={{
              fontSize: "1.05rem",
              padding: "0.95rem 2.25rem",
              borderRadius: "var(--radius-md)",
            }}
            id="start-monitoring-btn"
          >
            <Activity size={20} /> Start Monitoring <ArrowRight size={20} />
          </button>

          <button
            onClick={() => {
              onLoadDemo("critical_infrastructure");
              onStartMonitoring();
            }}
            className="btn-secondary"
            style={{
              fontSize: "0.95rem",
              padding: "0.95rem 1.75rem",
              borderRadius: "var(--radius-md)",
            }}
            id="load-demo-landing-btn"
          >
            <Database size={18} color="var(--accent-cyan)" /> Load National Infrastructure Demo
          </button>
        </div>

        {/* 3 Core Value Pillars (Evidence -> Analysis -> Insight) */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
            gap: "1.5rem",
            width: "100%",
            textAlign: "left",
          }}
        >
          <div className="glass-card hud-corner" style={{ padding: "1.5rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.65rem", marginBottom: "0.65rem" }}>
              <div
                style={{
                  width: "32px",
                  height: "32px",
                  borderRadius: "var(--radius-sm)",
                  background: "var(--accent-cyan-subtle)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <FileSearch size={18} color="var(--accent-cyan)" />
              </div>
              <h3 style={{ fontSize: "1rem", color: "#fff" }}>Execution Gap Detection</h3>
            </div>
            <p style={{ fontSize: "0.84rem", color: "#94a3b8", lineHeight: 1.5 }}>
              Detect Goodhart's Law metric gaming: superficial fast closures and critical unescalated incidents on core assets.
            </p>
          </div>

          <div className="glass-card hud-corner" style={{ padding: "1.5rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.65rem", marginBottom: "0.65rem" }}>
              <div
                style={{
                  width: "32px",
                  height: "32px",
                  borderRadius: "var(--radius-sm)",
                  background: "var(--accent-emerald-subtle)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <CheckCircle2 size={18} color="var(--accent-emerald)" />
              </div>
              <h3 style={{ fontSize: "1rem", color: "#fff" }}>Data Trust & Gating</h3>
            </div>
            <p style={{ fontSize: "0.84rem", color: "#94a3b8", lineHeight: 1.5 }}>
              4-component data quality scoring distinguishes true monitoring blind spots from telemetry ingestion outages.
            </p>
          </div>

          <div className="glass-card hud-corner" style={{ padding: "1.5rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.65rem", marginBottom: "0.65rem" }}>
              <div
                style={{
                  width: "32px",
                  height: "32px",
                  borderRadius: "var(--radius-sm)",
                  background: "var(--accent-purple-subtle)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Lock size={18} color="var(--accent-purple)" />
              </div>
              <h3 style={{ fontSize: "1rem", color: "#fff" }}>Air-Gapped & Deterministic</h3>
            </div>
            <p style={{ fontSize: "0.84rem", color: "#94a3b8", lineHeight: 1.5 }}>
              Zero network egress, 100% offline verification, non-generative explainability, and immutable audit logs.
            </p>
          </div>
        </div>

      </div>
    </div>
  );
};


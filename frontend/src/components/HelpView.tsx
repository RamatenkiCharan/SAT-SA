import React, { useState } from "react";
import {
  HelpCircle,
  Database,
  Layers,
  Lock,
  Cpu,
  CheckCircle,
  AlertTriangle,
  BookOpen,
  Activity,
  BarChart3,
} from "lucide-react";

export const HelpView: React.FC = () => {
  const [activeSection, setActiveSection] = useState<string>("core");

  return (
    <div className="page-fade-enter" style={{ display: "flex", flexDirection: "column", gap: "1.75rem" }}>
      {/* Header Banner */}
      <div
        className="glass-card hud-corner"
        style={{
          padding: "2rem",
          background: "linear-gradient(135deg, rgba(14, 21, 38, 0.95) 0%, rgba(8, 13, 26, 0.95) 100%)",
          border: "1px solid rgba(0, 240, 255, 0.2)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
          <div
            style={{
              width: "44px",
              height: "44px",
              borderRadius: "var(--radius-md)",
              background: "var(--accent-cyan-subtle)",
              border: "1px solid rgba(0, 240, 255, 0.4)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <BookOpen size={24} color="var(--accent-cyan)" />
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.25rem" }}>
              <span className="badge badge-cyan">SUPERVISORY KNOWLEDGE BASE</span>
              <span className="badge badge-purple">SRS ARCHITECTURE SPEC</span>
            </div>
            <h2 style={{ fontSize: "1.45rem", color: "#fff", fontWeight: 700 }}>
              Supervisory Architecture &amp; Methodological Guide
            </h2>
            <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", margin: 0 }}>
              Definitive mathematical foundations, execution gap definitions, and examiner operating procedures.
            </p>
          </div>
        </div>

        {/* Section Navigation Tabs */}
        <div style={{ display: "flex", gap: "0.5rem", marginTop: "1.5rem", flexWrap: "wrap" }}>
          {[
            { id: "core", label: "Core Supervisory Paradigm", icon: HelpCircle },
            { id: "formulas", label: "Mathematical Formulations", icon: Database },
            { id: "gaps", label: "Execution Gap Detectors", icon: Cpu },
            { id: "cohorts", label: "4D Peer Cohorts", icon: Layers },
            { id: "views", label: "8 Analytical Views Map", icon: BarChart3 },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeSection === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveSection(tab.id)}
                style={{
                  padding: "0.45rem 0.95rem",
                  borderRadius: "var(--radius-full)",
                  fontSize: "0.78rem",
                  fontWeight: 600,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.4rem",
                  border: isActive ? "1px solid var(--accent-cyan)" : "1px solid var(--border-subtle)",
                  background: isActive ? "var(--accent-cyan-subtle)" : "rgba(255, 255, 255, 0.03)",
                  color: isActive ? "var(--accent-cyan)" : "var(--text-secondary)",
                  transition: "all 0.15s ease",
                }}
              >
                <Icon size={14} /> {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* 1. Core Paradigm: What SAT-SA Does vs What It Does Not Do */}
      {(activeSection === "core" || activeSection === "all") && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))", gap: "1.25rem" }}>
          {/* What SAT-SA Does */}
          <div
            className="glass-card hud-corner"
            style={{
              padding: "1.75rem",
              borderLeft: "3px solid var(--accent-emerald)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1rem" }}>
              <CheckCircle size={20} color="var(--accent-emerald)" />
              <h3 style={{ fontSize: "1.15rem", color: "#fff", fontWeight: 700 }}>What SAT-SA Does (Supervisory Assurance)</h3>
            </div>
            <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: "0.75rem", fontSize: "0.84rem", color: "var(--text-secondary)", padding: 0 }}>
              <li style={{ display: "flex", gap: "0.6rem" }}>
                <span style={{ color: "var(--accent-emerald)", fontWeight: 800 }}>✓</span>
                <span><strong>Analyzes Operational Evidence:</strong> Evaluates alerts, cases, escalations, and closures generated during real SOC operations.</span>
              </li>
              <li style={{ display: "flex", gap: "0.6rem" }}>
                <span style={{ color: "var(--accent-emerald)", fontWeight: 800 }}>✓</span>
                <span><strong>Detects Goodhart's Law Metric Gaming:</strong> Uncovers rapid false closures and suppressed escalations designed to artificially boost SLA metrics.</span>
              </li>
              <li style={{ display: "flex", gap: "0.6rem" }}>
                <span style={{ color: "var(--accent-emerald)", fontWeight: 800 }}>✓</span>
                <span><strong>Exposes Monitoring Negative Space:</strong> Surfaces missing telemetry on critical infrastructure assets, safely gated by empirical Data Trust scores.</span>
              </li>
              <li style={{ display: "flex", gap: "0.6rem" }}>
                <span style={{ color: "var(--accent-emerald)", fontWeight: 800 }}>✓</span>
                <span><strong>100% Deterministic &amp; Air-Gapped:</strong> Mathematical algorithms and template explainability with zero external LLM hallucinations or network egress.</span>
              </li>
            </ul>
          </div>

          {/* What SAT-SA Does Not Do */}
          <div
            className="glass-card hud-corner"
            style={{
              padding: "1.75rem",
              borderLeft: "3px solid var(--accent-crimson)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1rem" }}>
              <AlertTriangle size={20} color="var(--accent-crimson)" />
              <h3 style={{ fontSize: "1.15rem", color: "#fff", fontWeight: 700 }}>What SAT-SA Does Not Do (Out of Scope)</h3>
            </div>
            <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: "0.75rem", fontSize: "0.84rem", color: "var(--text-secondary)", padding: 0 }}>
              <li style={{ display: "flex", gap: "0.6rem" }}>
                <span style={{ color: "var(--accent-crimson)", fontWeight: 800 }}>✕</span>
                <span><strong>Not a Real-Time SIEM or EDR:</strong> Does not directly intercept live network traffic or execute endpoint isolation commands.</span>
              </li>
              <li style={{ display: "flex", gap: "0.6rem" }}>
                <span style={{ color: "var(--accent-crimson)", fontWeight: 800 }}>✕</span>
                <span><strong>Not a Threat Blocking Agent:</strong> Does not block malicious IPs or modify operational firewall rules.</span>
              </li>
              <li style={{ display: "flex", gap: "0.6rem" }}>
                <span style={{ color: "var(--accent-crimson)", fontWeight: 800 }}>✕</span>
                <span><strong>Not a Questionnaire-Based Assessment:</strong> Rejects self-reported maturity claims in favor of empirical audit evidence.</span>
              </li>
              <li style={{ display: "flex", gap: "0.6rem" }}>
                <span style={{ color: "var(--accent-crimson)", fontWeight: 800 }}>✕</span>
                <span><strong>No Opaque Generative LLMs:</strong> Prioritization and explanations are 100% reproducible and verifiable from empirical data.</span>
              </li>
            </ul>
          </div>
        </div>
      )}

      {/* 2. Mathematical Formulations */}
      {(activeSection === "formulas" || activeSection === "all") && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "1.25rem" }}>
          {/* Data Trust Formula */}
          <div className="glass-card" style={{ padding: "1.5rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" }}>
              <Database size={18} color="var(--accent-cyan)" />
              <h4 style={{ fontSize: "1.05rem", color: "#fff", fontWeight: 700 }}>Data Trust Score (§7.2.1)</h4>
            </div>
            <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", lineHeight: 1.5, marginBottom: "0.75rem" }}>
              Calculates a bounded [0, 1] data trustworthiness metric across 4 orthogonal dimensions before evaluating supervisory execution:
            </p>
            <div style={{ background: "rgba(0, 0, 0, 0.45)", padding: "0.85rem", borderRadius: "var(--radius-sm)", fontSize: "0.76rem", fontFamily: "var(--font-mono)", color: "var(--accent-cyan)", border: "1px solid rgba(0, 240, 255, 0.2)", lineHeight: 1.5 }}>
              DQ = 0.30×Completeness + 0.25×Consistency + 0.25×Coverage + 0.20×Sufficiency
            </div>
          </div>

          {/* Evidence Fusion Priority Formula */}
          <div className="glass-card" style={{ padding: "1.5rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" }}>
              <Lock size={18} color="var(--accent-purple)" />
              <h4 style={{ fontSize: "1.05rem", color: "#fff", fontWeight: 700 }}>Evidence Fusion Priority (§10.5)</h4>
            </div>
            <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", lineHeight: 1.5, marginBottom: "0.75rem" }}>
              Fuses 5 independent operational signals into a strictly bounded [0, 1] priority score for examiner triage:
            </p>
            <div style={{ background: "rgba(0, 0, 0, 0.45)", padding: "0.85rem", borderRadius: "var(--radius-sm)", fontSize: "0.76rem", fontFamily: "var(--font-mono)", color: "#a78bfa", border: "1px solid rgba(139, 92, 246, 0.2)", lineHeight: 1.5 }}>
              P = 0.30×Signal + 0.25×Deviation + 0.20×Impact + 0.15×Recurrence − 0.10×Uncertainty
            </div>
          </div>

          {/* Robust Dispersion Formula */}
          <div className="glass-card" style={{ padding: "1.5rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" }}>
              <Activity size={18} color="var(--accent-gold)" />
              <h4 style={{ fontSize: "1.05rem", color: "#fff", fontWeight: 700 }}>Robust Peer Dispersion (MAD)</h4>
            </div>
            <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", lineHeight: 1.5, marginBottom: "0.75rem" }}>
              Resistant to extreme operational outliers using Median Absolute Deviation rather than standard deviation:
            </p>
            <div style={{ background: "rgba(0, 0, 0, 0.45)", padding: "0.85rem", borderRadius: "var(--radius-sm)", fontSize: "0.76rem", fontFamily: "var(--font-mono)", color: "#fbbf24", border: "1px solid rgba(234, 179, 8, 0.2)", lineHeight: 1.5 }}>
              MAD = median( |x_i − median(X)| )
              <br />
              Threshold = median(X) − 2.5 × MAD
            </div>
          </div>
        </div>
      )}

      {/* 3. Execution Gap Detectors */}
      {(activeSection === "gaps" || activeSection === "all") && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "1.25rem" }}>
          <div className="glass-card" style={{ padding: "1.5rem", borderTop: "3px solid var(--accent-rose)" }}>
            <span className="badge badge-rose" style={{ fontSize: "0.68rem", marginBottom: "0.5rem" }}>FR-030</span>
            <h4 style={{ fontSize: "1rem", color: "#fff", fontWeight: 700, marginBottom: "0.4rem" }}>Fast Closure Anomaly</h4>
            <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", lineHeight: 1.5 }}>
              Identifies critical and high alerts closed in less than peer median − 2.5 MAD with &le;1 evidence item attached, indicating superficial rubber-stamp closures.
            </p>
          </div>

          <div className="glass-card" style={{ padding: "1.5rem", borderTop: "3px solid var(--accent-amber)" }}>
            <span className="badge badge-amber" style={{ fontSize: "0.68rem", marginBottom: "0.5rem" }}>FR-032</span>
            <h4 style={{ fontSize: "1rem", color: "#fff", fontWeight: 700, marginBottom: "0.4rem" }}>Escalation Suppression Gap</h4>
            <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", lineHeight: 1.5 }}>
              Detects high-criticality assets that experienced critical security alerts without formal Tier-2 or Tier-3 escalation, exposing procedural suppression.
            </p>
          </div>

          <div className="glass-card" style={{ padding: "1.5rem", borderTop: "3px solid var(--accent-purple)" }}>
            <span className="badge badge-purple" style={{ fontSize: "0.68rem", marginBottom: "0.5rem" }}>FR-033</span>
            <h4 style={{ fontSize: "1rem", color: "#fff", fontWeight: 700, marginBottom: "0.4rem" }}>Repeated Unresolved Alerts</h4>
            <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", lineHeight: 1.5 }}>
              Flags &ge;3 recurrent alert instances within a 30-day window on the same asset without documented root-cause remediation or preventive changes.
            </p>
          </div>

          <div className="glass-card" style={{ padding: "1.5rem", borderTop: "3px solid var(--accent-cyan)" }}>
            <span className="badge badge-cyan" style={{ fontSize: "0.68rem", marginBottom: "0.5rem" }}>FR-041</span>
            <h4 style={{ fontSize: "1rem", color: "#fff", fontWeight: 700, marginBottom: "0.4rem" }}>Negative Space &amp; Sensor Outages</h4>
            <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", lineHeight: 1.5 }}>
              Distinguishes between genuine monitoring blind spots (missing telemetry on critical assets) vs sensor silence/outages using Data Trust quality gating.
            </p>
          </div>
        </div>
      )}

      {/* 4. 4D Peer Cohorts */}
      {(activeSection === "cohorts" || activeSection === "all") && (
        <div className="glass-card" style={{ padding: "1.75rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" }}>
            <Layers size={20} color="var(--accent-blue)" />
            <h3 style={{ fontSize: "1.15rem", color: "#fff", fontWeight: 700 }}>4-Dimensional Peer Cohort Segmentation &amp; Fallback</h3>
          </div>
          <p style={{ fontSize: "0.84rem", color: "var(--text-secondary)", lineHeight: 1.5, marginBottom: "1.25rem" }}>
            To ensure statistical validity, entities are grouped across 4 orthogonal dimensions. Cohorts require a minimum threshold of N &ge; 5 entities. If N &lt; 5, SAT-SA gracefully falls back through a 4-tier hierarchy:
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "1rem" }}>
            <div style={{ background: "rgba(0, 0, 0, 0.4)", padding: "1rem", borderRadius: "var(--radius-md)", border: "1px solid var(--border-subtle)" }}>
              <div style={{ fontSize: "0.72rem", color: "var(--accent-cyan)", fontWeight: 700 }}>TIER 1 (EXACT MATCH)</div>
              <div style={{ fontSize: "0.85rem", fontWeight: 600, color: "#fff", marginTop: "0.25rem" }}>Sector + Asset Class + Criticality + Environment</div>
            </div>
            <div style={{ background: "rgba(0, 0, 0, 0.4)", padding: "1rem", borderRadius: "var(--radius-md)", border: "1px solid var(--border-subtle)" }}>
              <div style={{ fontSize: "0.72rem", color: "var(--accent-blue)", fontWeight: 700 }}>TIER 2 (RELAX ENVIRONMENT)</div>
              <div style={{ fontSize: "0.85rem", fontWeight: 600, color: "#fff", marginTop: "0.25rem" }}>Sector + Asset Class + Criticality</div>
            </div>
            <div style={{ background: "rgba(0, 0, 0, 0.4)", padding: "1rem", borderRadius: "var(--radius-md)", border: "1px solid var(--border-subtle)" }}>
              <div style={{ fontSize: "0.72rem", color: "var(--accent-amber)", fontWeight: 700 }}>TIER 3 (RELAX CRITICALITY)</div>
              <div style={{ fontSize: "0.85rem", fontWeight: 600, color: "#fff", marginTop: "0.25rem" }}>Sector + Asset Class Only</div>
            </div>
            <div style={{ background: "rgba(0, 0, 0, 0.4)", padding: "1rem", borderRadius: "var(--radius-md)", border: "1px solid var(--border-subtle)" }}>
              <div style={{ fontSize: "0.72rem", color: "var(--accent-purple)", fontWeight: 700 }}>TIER 4 (GLOBAL SECTOR)</div>
              <div style={{ fontSize: "0.85rem", fontWeight: 600, color: "#fff", marginTop: "0.25rem" }}>Sector-Wide Baseline (N &ge; 5)</div>
            </div>
          </div>
        </div>
      )}

      {/* 5. 8 Analytical Views Map */}
      {(activeSection === "views" || activeSection === "all") && (
        <div className="glass-card" style={{ padding: "1.75rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1rem" }}>
            <BarChart3 size={20} color="var(--accent-cyan)" />
            <h3 style={{ fontSize: "1.15rem", color: "#fff", fontWeight: 700 }}>Interactive Command Center - 8 Supervisory Views</h3>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "1rem" }}>
            {[
              { title: "1. Executive Overview", desc: "Goodhart's Law reality check, high-level SLA vs empirical gap comparison, and priority review queue." },
              { title: "2. Supervisory Findings Triage", desc: "Multi-dimensional filterable triage queue with decomposed priority formulas and evidence drill-down." },
              { title: "3. Peer Cohort Benchmarks", desc: "Non-parametric Median/MAD cross-entity comparisons across critical infrastructure sectors." },
              { title: "4. Negative Space Monitoring", desc: "Surfaces monitoring blind spots on critical infrastructure gated by Data Trust score ratios." },
              { title: "5. Review Yield & Validation", desc: "Quantifiable empirical workload reduction (4.1x speedup, 78% reduction) and held-out audit verification." },
              { title: "6. Telemetry Datasets", desc: "Ingestion and version management with cryptographic SHA-256 provenance tracking (§52)." },
              { title: "7. Immutable Audit Ledger", desc: "Tamper-evident blockchain-style log of all human examiner dispositions and dataset switches." },
              { title: "8. Reference & Guidance", desc: "Mathematical formulas, algorithmic specifications, and supervisory operating principles." },
            ].map((v, i) => (
              <div key={i} style={{ background: "rgba(15, 23, 42, 0.6)", padding: "1rem", borderRadius: "var(--radius-md)", border: "1px solid var(--border-subtle)" }}>
                <div style={{ fontSize: "0.88rem", fontWeight: 700, color: "#fff", marginBottom: "0.3rem" }}>{v.title}</div>
                <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)", lineHeight: 1.45 }}>{v.desc}</div>
              </div>
            ))}
          </div>
        </div>
      )}

    </div>
  );
};


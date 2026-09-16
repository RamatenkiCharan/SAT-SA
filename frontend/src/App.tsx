import { useState, useEffect } from "react";
import { LandingHeroView } from "./components/LandingHeroView";
import { Sidebar, type TabId } from "./components/Sidebar";
import { Navbar } from "./components/Navbar";
import { OverviewView } from "./components/OverviewView";
import { FindingsView } from "./components/FindingsView";
import { FindingDetailModal } from "./components/FindingDetailModal";
import { PeerBenchmarkView } from "./components/PeerBenchmarkView";
import { NegativeSpaceView } from "./components/NegativeSpaceView";
import { ValidationView } from "./components/ValidationView";
import { DatasetManagerView } from "./components/DatasetManagerView";
import { AuditView } from "./components/AuditView";
import { HelpView } from "./components/HelpView";
import { ParticleBackground } from "./components/ParticleBackground";
import type { DatasetItem, Finding } from "./types";
import { fetchDatasets, fetchFindings, loadDemoDataset } from "./api";

const TAB_TITLES: Record<TabId, string> = {
  overview: "Executive Overview",
  findings: "Supervisory Findings Triage",
  benchmarks: "Peer Cohort Benchmarking",
  negativespace: "Negative Space Monitoring Map",
  validation: "Supervisory Review Yield & Validation",
  datasets: "Operational Telemetry Datasets",
  audit: "Immutable Supervisory Audit Ledger",
  help: "Architecture & Operational Guidance",
};

export function App() {
  const [currentScreen, setCurrentScreen] = useState<"landing" | "command_center">("landing");
  const [activeTab, setActiveTab] = useState<TabId>("overview");
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState<boolean>(false);
  const [datasets, setDatasets] = useState<DatasetItem[]>([]);
  const [activeVersionId, setActiveVersionId] = useState<string | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [selectedFinding, setSelectedFinding] = useState<Finding | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>("");

  const refreshData = async () => {
    setLoading(true);
    try {
      const dsData = await fetchDatasets();
      setDatasets(dsData.datasets || []);
      const verId = dsData.active_version_id;
      setActiveVersionId(verId);

      const fData = await fetchFindings({ dataset_version_id: verId || undefined });
      setFindings(fData.findings || []);
    } catch (err) {
      console.error("Failed to load SAT-SA data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshData();
  }, []);

  const handleStartMonitoring = () => {
    setCurrentScreen("command_center");
    setActiveTab("overview");
  };

  const handleLoadDemo = async (type: "critical_infrastructure" | "held_out_test") => {
    try {
      await loadDemoDataset(type);
      await refreshData();
    } catch (err) {
      alert("Failed to load demo pack: " + String(err));
    }
  };

  const handleGlobalSearchChange = (q: string) => {
    setSearchQuery(q);
    if (q && activeTab !== "findings" && activeTab !== "overview") {
      setActiveTab("findings");
    }
  };

  return (
    <div className="app-container">
      {/* 3D Antigravity Atmospheric Particle Layer (Active on Landing & Executive Overview) */}
      <ParticleBackground active={currentScreen === "landing" || activeTab === "overview"} />



      {/* =================================================================== */}
      {/* PAGE 1: FOCUSED HERO LANDING PAGE                                   */}
      {/* =================================================================== */}
      {currentScreen === "landing" ? (
        <div style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: "100vh", position: "relative", zIndex: 1 }}>
          <main style={{ flex: 1 }}>
            <LandingHeroView
              onStartMonitoring={handleStartMonitoring}
              onLoadDemo={handleLoadDemo}
            />
          </main>
          <footer
            style={{
              borderTop: "1px solid var(--border-subtle)",
              background: "rgba(6, 9, 19, 0.8)",
              padding: "1rem",
              textAlign: "center",
              fontSize: "0.76rem",
              color: "var(--text-muted)",
            }}
          >
            SAT-SA • Supervisory Analytics Tool for SOC Assessment • NCIIPC Air-Gapped Examiner Edition
          </footer>
        </div>
      ) : (
        /* =================================================================== */
        /* PAGE 2: COMMAND CENTER WORKSPACE                                   */
        /* =================================================================== */
        <div className="command-center-layout page-fade-enter">
          {/* Collapsible Enterprise Sidebar */}
          <Sidebar
            activeTab={activeTab}
            setActiveTab={setActiveTab}
            isCollapsed={isSidebarCollapsed}
            setIsCollapsed={setIsSidebarCollapsed}
            onExitToLanding={() => setCurrentScreen("landing")}
            findingsCount={findings.length}
          />

          {/* Main Working Area */}
          <div className="main-workspace">
            {/* Top Header Bar */}
            <Navbar
              activeVersionId={activeVersionId}
              datasets={datasets}
              onLoadDemo={handleLoadDemo}
              activeTabLabel={TAB_TITLES[activeTab] || "Command Center"}
              searchQuery={searchQuery}
              onSearchChange={handleGlobalSearchChange}
            />

            {/* Dynamic View Content */}
            <div
              style={{
                flex: 1,
                padding: "2rem 1.75rem",
                maxWidth: "1440px",
                width: "100%",
                margin: "0 auto",
              }}
            >
              {loading && findings.length === 0 ? (
                <div style={{ textAlign: "center", padding: "6rem 2rem", color: "var(--text-muted)" }}>
                  <div
                    style={{
                      fontSize: "1.2rem",
                      fontWeight: 700,
                      color: "var(--accent-cyan)",
                      marginBottom: "0.5rem",
                    }}
                  >
                    Reconstructing Supervisory Evidence Graphs...
                  </div>
                  <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                    Computing non-parametric peer baselines and 4-component data quality scores.
                  </p>
                </div>
              ) : (
                <>
                  {activeTab === "overview" && (
                    <OverviewView
                      findings={findings}
                      onSelectFinding={setSelectedFinding}
                      onNavigate={(tab) => setActiveTab(tab as TabId)}
                    />
                  )}

                  {activeTab === "findings" && (
                    <FindingsView
                      findings={findings}
                      onSelectFinding={setSelectedFinding}
                      searchQuery={searchQuery}
                      onSearchChange={setSearchQuery}
                    />
                  )}

                  {activeTab === "benchmarks" && (
                    <PeerBenchmarkView activeVersionId={activeVersionId} />
                  )}

                  {activeTab === "negativespace" && (
                    <NegativeSpaceView
                      findings={findings}
                      onSelectFinding={setSelectedFinding}
                    />
                  )}

                  {activeTab === "validation" && <ValidationView />}

                  {activeTab === "datasets" && (
                    <DatasetManagerView
                      datasets={datasets}
                      activeVersionId={activeVersionId}
                      onRefresh={refreshData}
                    />
                  )}

                  {activeTab === "audit" && <AuditView />}

                  {activeTab === "help" && <HelpView />}
                </>
              )}
            </div>

            {/* Footer */}
            <footer
              style={{
                borderTop: "1px solid var(--border-subtle)",
                background: "rgba(6, 9, 19, 0.8)",
                padding: "1rem",
                textAlign: "center",
                fontSize: "0.76rem",
                color: "var(--text-muted)",
              }}
            >
              SAT-SA • Evidence-Based Supervisory Analytics Engine • Air-Gapped NCIIPC Examiner
            </footer>
          </div>
        </div>
      )}

      {/* Deep-Dive Evidence Drill-Down Modal */}
      {selectedFinding && (
        <FindingDetailModal
          finding={selectedFinding}
          onClose={() => setSelectedFinding(null)}
          onReviewSubmitted={refreshData}
        />
      )}
    </div>
  );
}

export default App;

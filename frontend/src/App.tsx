import { useState, useEffect } from "react";
import { Navbar } from "./components/Navbar";
import { OverviewView } from "./components/OverviewView";
import { FindingsView } from "./components/FindingsView";
import { FindingDetailModal } from "./components/FindingDetailModal";
import { PeerBenchmarkView } from "./components/PeerBenchmarkView";
import { NegativeSpaceView } from "./components/NegativeSpaceView";
import { ValidationView } from "./components/ValidationView";
import { DatasetManagerView } from "./components/DatasetManagerView";
import { AuditView } from "./components/AuditView";
import type { DatasetItem, Finding } from "./types";
import { fetchDatasets, fetchFindings, loadDemoDataset, ensureAuthToken } from "./api";

export function App() {
  const [activeTab, setActiveTab] = useState<string>("overview");
  const [datasets, setDatasets] = useState<DatasetItem[]>([]);
  const [activeVersionId, setActiveVersionId] = useState<string | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [selectedFinding, setSelectedFinding] = useState<Finding | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const refreshData = async () => {
    setLoading(true);
    try {
      await ensureAuthToken();
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
    ensureAuthToken().then(() => refreshData());
  }, []);

  const [loadingDemo, setLoadingDemo] = useState<boolean>(false);

  const handleLoadDemo = async (type: "critical_infrastructure" | "held_out_test") => {
    setLoadingDemo(true);
    try {
      await loadDemoDataset(type);
      await refreshData();
    } catch (err) {
      alert("Failed to load demo pack: " + String(err));
    } finally {
      setLoadingDemo(false);
    }
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      {/* Top Navigation Bar */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        activeVersionId={activeVersionId}
        datasets={datasets}
        onLoadDemo={handleLoadDemo}
        loadingDemo={loadingDemo}
      />

      {/* Main Content Area */}
      <main style={{ flex: 1, maxWidth: "1400px", width: "100%", margin: "0 auto", padding: "2rem 1.5rem" }}>
        {loading && findings.length === 0 ? (
          <div style={{ textAlign: "center", padding: "4rem", color: "var(--text-muted)" }}>
            <div style={{ fontSize: "1.2rem", color: "var(--accent-cyan)", marginBottom: "0.5rem" }}>
              Initializing SAT-SA Supervisory Intelligence Engine...
            </div>
            <p style={{ fontSize: "0.85rem" }}>Loading canonical evidence graphs and computing peer baselines.</p>
          </div>
        ) : (
          <>
            {activeTab === "overview" && (
              <OverviewView
                findings={findings}
                onSelectFinding={setSelectedFinding}
                onNavigate={setActiveTab}
              />
            )}

            {activeTab === "findings" && (
              <FindingsView
                findings={findings}
                onSelectFinding={setSelectedFinding}
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
          </>
        )}
      </main>

      {/* Deep-Dive Evidence Drill-Down Modal */}
      {selectedFinding && (
        <FindingDetailModal
          finding={selectedFinding}
          onClose={() => setSelectedFinding(null)}
          onReviewSubmitted={refreshData}
        />
      )}

      {/* Footer */}
      <footer style={{ borderTop: "1px solid var(--border-subtle)", padding: "1.25rem", textAlign: "center", fontSize: "0.75rem", color: "var(--text-muted)" }}>
        SAT-SA (Supervisory Analytics Tool for SOC Assessment) • Air-Gapped NCIIPC Examiner Edition
      </footer>
    </div>
  );
}

export default App;

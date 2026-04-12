import { Suspense, lazy, useMemo, useState } from "react";

import DashboardSkeleton from "./components/DashboardSkeleton";
import Sidebar from "./components/Sidebar";
import { useDashboardData } from "./hooks/useDashboardData";
import { useTheme } from "./hooks/useTheme";

const DASHBOARD_THEME_KEY = "dashboard-theme";

const OverviewPage = lazy(() => import("./pages/OverviewPage"));
const HeatmapPage = lazy(() => import("./pages/HeatmapPage"));
const QueuesPage = lazy(() => import("./pages/QueuesPage"));
const AlertsPage = lazy(() => import("./pages/AlertsPage"));
const KpisPage = lazy(() => import("./pages/KpisPage"));

function PageRenderer({ page, zones, queues, interventions, kpis }) {
  switch (page) {
    case "heatmap":
      return <HeatmapPage zones={zones} queues={queues} />;
    case "queues":
      return <QueuesPage queues={queues} />;
    case "alerts":
      return <AlertsPage interventions={interventions} />;
    case "kpis":
      return <KpisPage kpis={kpis} />;
    default:
      return (
        <OverviewPage
          zones={zones}
          queues={queues}
          interventions={interventions}
        />
      );
  }
}

export default function App() {
  const [activePage, setActivePage] = useState("overview");
  const { theme, toggleTheme } = useTheme(DASHBOARD_THEME_KEY);
  const {
    zones,
    queues,
    interventions,
    kpis,
    simStatus,
    connected,
    wsConnected,
    loading,
    lastError,
    refreshData,
  } = useDashboardData();

  const renderedPage = useMemo(() => (
    <PageRenderer
      page={activePage}
      zones={zones}
      queues={queues}
      interventions={interventions}
      kpis={kpis}
    />
  ), [activePage, interventions, kpis, queues, zones]);

  return (
    <div className="app-layout" id="ops-dashboard">
      <a href="#dashboard-main" className="skip-link">
        Skip to main content
      </a>

      <Sidebar
        activePage={activePage}
        onNavigate={setActivePage}
        simStatus={simStatus}
        onRefresh={refreshData}
      />

      <main
        className="main-content"
        id="dashboard-main"
        tabIndex={-1}
        aria-busy={loading}
      >
        <div
          style={{
            position: "fixed",
            top: "12px",
            right: connected ? "160px" : "16px",
            zIndex: 1000,
          }}
        >
          <button
            className="btn btn-ghost"
            style={{ fontSize: "0.75rem" }}
            onClick={toggleTheme}
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
          >
            <i className="bi bi-circle-half" aria-hidden="true" />{" "}
            {theme === "dark" ? "Light" : "Dark"}
          </button>
        </div>

        {lastError && !loading && !wsConnected && (
          <div className="sim-controls" role="alert" style={{ marginBottom: "12px" }}>
            <span style={{ color: "var(--status-orange)", fontSize: "0.85rem" }}>
              <i
                className="bi bi-exclamation-circle-fill"
                style={{ marginRight: "6px" }}
                aria-hidden="true"
              />
              {lastError}
            </span>
            <button
              className="btn btn-ghost"
              onClick={refreshData}
              style={{ marginLeft: "10px" }}
            >
              Retry
            </button>
          </div>
        )}

        {!connected && !loading && (
          <div
            className="sim-controls"
            style={{ borderColor: "rgba(239, 68, 68, 0.3)" }}
            role="alert"
          >
            <span style={{ color: "var(--status-red)", fontSize: "0.85rem" }}>
              <i
                className="bi bi-exclamation-triangle-fill"
                style={{ marginRight: "6px" }}
                aria-hidden="true"
              />
              Cannot connect to backend - ensure the API is running and auth config is valid
            </span>
          </div>
        )}

        {connected && (
          <div
            className="connection-badge"
            style={{ position: "fixed", top: "12px", right: "16px", zIndex: 999 }}
            role="status"
            aria-live="polite"
          >
            <span className={`conn-indicator ${wsConnected ? "ws" : "poll"}`}>
              <i
                className={wsConnected ? "bi bi-broadcast" : "bi bi-arrow-repeat"}
                style={{ marginRight: "6px" }}
                aria-hidden="true"
              />
              {wsConnected ? "WebSocket" : "Backoff Polling"}
            </span>
          </div>
        )}

        {loading ? (
          <DashboardSkeleton />
        ) : (
          <Suspense fallback={<DashboardSkeleton />}>{renderedPage}</Suspense>
        )}
      </main>
    </div>
  );
}

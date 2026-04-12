import { Suspense, lazy, useEffect, useMemo, useState } from "react";

import NotificationToast from "./components/NotificationToast";
import { useFanData } from "./hooks/useFanData";
import { useTheme } from "./hooks/useTheme";

const FAN_THEME_KEY = "fan-theme";

const HomePage = lazy(() => import("./pages/HomePage"));
const QueuesPage = lazy(() => import("./pages/QueuesPage"));
const AlertsPage = lazy(() => import("./pages/AlertsPage"));

function FanSkeleton() {
  return (
    <div role="status" aria-live="polite" aria-label="Loading fan app data">
      <div className="phase-banner skeleton-card" style={{ height: "92px" }} />
      <div className="smart-card skeleton-card" style={{ height: "160px" }} />
      <div className="smart-card skeleton-card" style={{ height: "160px" }} />
    </div>
  );
}

function PageRenderer({ page, bestGate, bestConc, exitGuide, queues, simStatus, notifications }) {
  switch (page) {
    case "queues":
      return <QueuesPage queues={queues} />;
    case "alerts":
      return <AlertsPage notifications={notifications} />;
    default:
      return (
        <HomePage
          bestGate={bestGate}
          bestConc={bestConc}
          exitGuide={exitGuide}
          queues={queues}
          simStatus={simStatus}
        />
      );
  }
}

export default function App() {
  const [activePage, setActivePage] = useState("home");
  const [notification, setNotification] = useState(null);
  const { theme, toggleTheme } = useTheme(FAN_THEME_KEY);
  const {
    bestGate,
    bestConc,
    exitGuide,
    queues,
    simStatus,
    notifications,
    connected,
    loading,
    lastError,
    refreshData,
  } = useFanData();

  useEffect(() => {
    if (simStatus?.phase === "halftime" && bestConc?.best_concession) {
      const timer = setTimeout(() => {
        setNotification({
          title: "Skip the wait!",
          body: `${bestConc.best_concession.replace(/_/g, " ").toUpperCase()} has only ${(bestConc.wait_minutes || 0).toFixed(0)} min wait`,
          variant: "warning",
        });
      }, 3000);
      return () => clearTimeout(timer);
    }

    return undefined;
  }, [bestConc, simStatus?.phase]);

  const renderedPage = useMemo(() => (
    <PageRenderer
      page={activePage}
      bestGate={bestGate}
      bestConc={bestConc}
      exitGuide={exitGuide}
      queues={queues}
      simStatus={simStatus}
      notifications={notifications}
    />
  ), [activePage, bestGate, bestConc, exitGuide, notifications, queues, simStatus]);

  return (
    <div className="fan-app" id="fan-assistant">
      <a href="#fan-main" className="skip-link">
        Skip to main content
      </a>

      <NotificationToast
        notification={notification}
        onClose={() => setNotification(null)}
      />

      <div className="fan-top-actions">
        <button
          className="theme-toggle"
          onClick={toggleTheme}
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
        >
          <i className="bi bi-circle-half" aria-hidden="true" /> {theme === "dark" ? "Light" : "Dark"}
        </button>
      </div>

      <header className="fan-header">
        <div className="fan-brand">
          <div className="fan-brand-icon">
            <i className="bi bi-building" aria-hidden="true" />
          </div>
          <div>
            <h1>Stadium OS</h1>
            <div className="fan-brand-sub">Your Personal Copilot</div>
          </div>
        </div>
        {connected && (
          <div className="fan-live-badge" role="status" aria-live="polite">
            <span className="live-dot" />
            LIVE
          </div>
        )}
      </header>

      {lastError && !loading && (
        <div className="error-banner" role="alert">
          <span>
            <i className="bi bi-exclamation-circle-fill" aria-hidden="true" /> {lastError}
          </span>
          <button className="retry-btn" onClick={refreshData}>
            Retry
          </button>
        </div>
      )}

      <main id="fan-main" tabIndex={-1} aria-busy={loading}>
        {loading ? (
          <FanSkeleton />
        ) : (
          <Suspense fallback={<FanSkeleton />}>{renderedPage}</Suspense>
        )}
      </main>

      <nav
        className="bottom-nav"
        id="fan-bottom-nav"
        aria-label="Fan app navigation"
      >
        <button
          className={`nav-tab ${activePage === "home" ? "active" : ""}`}
          onClick={() => setActivePage("home")}
          aria-current={activePage === "home" ? "page" : undefined}
        >
          <span className="nav-tab-icon">
            <i className="bi bi-house-door" aria-hidden="true" />
          </span>
          Home
        </button>
        <button
          className={`nav-tab ${activePage === "queues" ? "active" : ""}`}
          onClick={() => setActivePage("queues")}
          aria-current={activePage === "queues" ? "page" : undefined}
        >
          <span className="nav-tab-icon">
            <i className="bi bi-clock-history" aria-hidden="true" />
          </span>
          Queues
        </button>
        <button
          className={`nav-tab ${activePage === "alerts" ? "active" : ""}`}
          onClick={() => setActivePage("alerts")}
          aria-current={activePage === "alerts" ? "page" : undefined}
        >
          <span className="nav-tab-icon">
            <i className="bi bi-bell" aria-hidden="true" />
          </span>
          Alerts
        </button>
      </nav>
    </div>
  );
}

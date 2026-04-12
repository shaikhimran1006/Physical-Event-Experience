import SimulationWidget from "./SimulationWidget";

const PAGES = [
  { id: "overview", label: "Command Center", icon: "bi bi-speedometer2" },
  { id: "heatmap", label: "Stadium Map", icon: "bi bi-map" },
  { id: "queues", label: "Queue Monitor", icon: "bi bi-clock-history" },
  { id: "alerts", label: "Interventions", icon: "bi bi-exclamation-triangle" },
  { id: "kpis", label: "KPI Dashboard", icon: "bi bi-bar-chart-line" },
];

export default function Sidebar({
  activePage,
  onNavigate,
  simStatus,
  onRefresh,
}) {
  return (
    <nav className="sidebar" id="sidebar-nav" aria-label="Primary dashboard navigation">
      <div className="sidebar-brand">
        <h1>Stadium OS</h1>
        <span>Operations Command Center</span>
      </div>

      <div className="sidebar-nav">
        {PAGES.map((page) => (
          <button
            key={page.id}
            className={`nav-item ${activePage === page.id ? "active" : ""}`}
            onClick={() => onNavigate(page.id)}
            aria-pressed={activePage === page.id}
          >
            <span className="nav-icon">
              <i className={page.icon} aria-hidden="true" />
            </span>
            {page.label}
          </button>
        ))}
      </div>

      <div style={{ padding: "0 16px", marginTop: "auto" }}>
        <SimulationWidget simStatus={simStatus} onRefresh={onRefresh} />
      </div>
    </nav>
  );
}

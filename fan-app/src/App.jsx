import { useState, useEffect, useCallback } from "react";
import "./index.css";

const runtimeConfig = window.__APP_CONFIG__ || {};
const API_URL = (
  runtimeConfig.API_URL ||
  import.meta.env.VITE_API_URL ||
  "http://localhost:8000"
).replace(/\/+$/, "");
const VENUE_ID = "stadium_01";
const POLL_INTERVAL = 3000;

// ── Data Hook ───────────────────────────────────────────────────────
function useFanData() {
  const [bestGate, setBestGate] = useState(null);
  const [bestConc, setBestConc] = useState(null);
  const [exitGuide, setExitGuide] = useState(null);
  const [queues, setQueues] = useState({});
  const [simStatus, setSimStatus] = useState({ phase: "idle", progress: 0 });
  const [connected, setConnected] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [gRes, cRes, eRes, qRes, sRes] = await Promise.all([
        fetch(`${API_URL}/fan/${VENUE_ID}/best-gate`),
        fetch(`${API_URL}/fan/${VENUE_ID}/best-concession`),
        fetch(`${API_URL}/fan/${VENUE_ID}/exit-guidance`),
        fetch(`${API_URL}/state/${VENUE_ID}/queues`),
        fetch(`${API_URL}/simulation/status`),
      ]);
      if (gRes.ok) setBestGate(await gRes.json());
      if (cRes.ok) setBestConc(await cRes.json());
      if (eRes.ok) setExitGuide(await eRes.json());
      if (qRes.ok) setQueues(await qRes.json());
      if (sRes.ok) setSimStatus(await sRes.json());
      setConnected(true);
    } catch {
      setConnected(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchData]);

  return { bestGate, bestConc, exitGuide, queues, simStatus, connected };
}

// ── Phase Info ──────────────────────────────────────────────────────
const PHASE_MAP = {
  pre_game: {
    icon: "bi bi-door-open",
    label: "Pre-Game",
    desc: "Gates are open — find your fastest entry",
  },
  in_game: {
    icon: "bi bi-trophy",
    label: "Game On",
    desc: "Enjoy the action! Check concessions during breaks",
  },
  in_game_2: {
    icon: "bi bi-trophy-fill",
    label: "Second Half",
    desc: "Game on — plan your exit strategy",
  },
  halftime: {
    icon: "bi bi-cup-hot",
    label: "Halftime",
    desc: "Beat the rush — we found short queues for you",
  },
  post_game: {
    icon: "bi bi-box-arrow-right",
    label: "Game Over",
    desc: "Follow your personalized exit route",
  },
  idle: {
    icon: "bi bi-pause-circle",
    label: "Standby",
    desc: "Waiting for game events...",
  },
  completed: {
    icon: "bi bi-check-circle",
    label: "Complete",
    desc: "Simulation finished",
  },
  starting: {
    icon: "bi bi-play-circle",
    label: "Starting",
    desc: "Initializing...",
  },
  stopped: {
    icon: "bi bi-stop-circle",
    label: "Stopped",
    desc: "Simulation stopped",
  },
};

function getWaitColor(minutes) {
  if (minutes <= 3) return "green";
  if (minutes <= 7) return "yellow";
  if (minutes <= 12) return "orange";
  return "red";
}

// ── Notification Toast ──────────────────────────────────────────────
function NotificationToast({ notification, onClose }) {
  useEffect(() => {
    if (!notification) return undefined;
    const timer = setTimeout(onClose, 6000);
    return () => clearTimeout(timer);
  }, [notification, onClose]);

  if (!notification) return null;

  return (
    <div
      className={`notification-toast ${notification.variant || ""}`}
      role="status"
      aria-live="assertive"
      aria-atomic="true"
    >
      <button
        className="toast-close"
        onClick={onClose}
        aria-label="Dismiss notification"
      >
        <i className="bi bi-x-lg" aria-hidden="true" />
      </button>
      <div className="toast-title">{notification.title}</div>
      <div className="toast-body">{notification.body}</div>
    </div>
  );
}

// ── Best Gate Card ──────────────────────────────────────────────────
function BestGateCard({ data }) {
  if (!data || !data.best_gate) return null;

  const gates = data.all_gates || {};
  const bestId = data.best_gate;
  const bestWait = data.wait_minutes || 0;

  const sortedGates = Object.entries(gates).sort(
    (a, b) => (a[1].avgWaitMinutes || 0) - (b[1].avgWaitMinutes || 0),
  );

  // Calculate savings vs worst gate
  const worstWait =
    sortedGates.length > 0
      ? sortedGates[sortedGates.length - 1][1].avgWaitMinutes || 0
      : 0;
  const savings = Math.max(0, worstWait - bestWait);

  return (
    <div className="smart-card gate-card" id="best-gate-card">
      <span className="card-tag best">
        <i className="bi bi-award" aria-hidden="true" /> Best Choice
      </span>
      <div className="smart-card-header">
        <div>
          <div className="smart-card-title">
            {bestId.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
          </div>
          <div className="smart-card-subtitle">Fastest entry right now</div>
        </div>
        <div className={`wait-badge ${getWaitColor(bestWait)}`}>
          <div className="wait-value">{bestWait.toFixed(0)}</div>
          <div className="wait-unit">min wait</div>
        </div>
      </div>

      {savings > 1 && (
        <div className="savings-chip">
          <i
            className="bi bi-lightning-charge-fill"
            style={{ marginRight: "4px" }}
            aria-hidden="true"
          />
          Save {savings.toFixed(0)} min vs busiest gate
        </div>
      )}

      <div className="options-row" style={{ marginTop: "12px" }}>
        {sortedGates.map(([gateId, gateData]) => {
          const wait = gateData.avgWaitMinutes || 0;
          const isBest = gateId === bestId;
          return (
            <div key={gateId} className={`option-pill ${isBest ? "best" : ""}`}>
              <div className="pill-name">
                {gateId
                  .replace(/_/g, " ")
                  .replace(/\b\w/g, (c) => c.toUpperCase())}
              </div>
              <div className={`pill-wait ${getWaitColor(wait)}`}>
                {wait.toFixed(1)} min
              </div>
              <div className="pill-detail">
                {gateData.currentQueueLength || 0} in line
              </div>
              {isBest && (
                <div
                  className="pill-detail"
                  style={{ color: "var(--status-green)" }}
                >
                  <i
                    className="bi bi-star-fill"
                    style={{ marginRight: "4px" }}
                    aria-hidden="true"
                  />
                  Recommended
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Best Concession Card ────────────────────────────────────────────
function BestConcessionCard({ data }) {
  if (!data || !data.best_concession) return null;

  const concessions = data.all_concessions || {};
  const bestId = data.best_concession;
  const bestWait = data.wait_minutes || 0;

  const sorted = Object.entries(concessions).sort(
    (a, b) => (a[1].avgWaitMinutes || 0) - (b[1].avgWaitMinutes || 0),
  );

  const worstWait =
    sorted.length > 0 ? sorted[sorted.length - 1][1].avgWaitMinutes || 0 : 0;
  const savePct =
    worstWait > 0 ? Math.round(((worstWait - bestWait) / worstWait) * 100) : 0;

  return (
    <div className="smart-card conc-card" id="best-concession-card">
      <span className="card-tag best">
        <i className="bi bi-cup-hot" aria-hidden="true" /> Shortest Queue
      </span>
      <div className="smart-card-header">
        <div>
          <div className="smart-card-title">
            {bestId.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
          </div>
          <div className="smart-card-subtitle">Skip the line — order here</div>
        </div>
        <div className={`wait-badge ${getWaitColor(bestWait)}`}>
          <div className="wait-value">{bestWait.toFixed(0)}</div>
          <div className="wait-unit">min wait</div>
        </div>
      </div>

      {savePct > 10 && (
        <div className="savings-chip">
          <i
            className="bi bi-lightning-charge-fill"
            style={{ marginRight: "4px" }}
            aria-hidden="true"
          />
          {savePct}% less wait than busiest stand
        </div>
      )}

      <div className="options-row" style={{ marginTop: "12px" }}>
        {sorted.map(([id, d]) => {
          const wait = d.avgWaitMinutes || 0;
          return (
            <div
              key={id}
              className={`option-pill ${id === bestId ? "best" : ""}`}
            >
              <div className="pill-name">
                {id.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
              </div>
              <div className={`pill-wait ${getWaitColor(wait)}`}>
                {wait.toFixed(1)} min
              </div>
              <div className="pill-detail">
                {d.currentQueueLength || 0} in line
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Best Restroom Card ──────────────────────────────────────────────
function BestRestroomCard({ queues }) {
  const restrooms = Object.entries(queues)
    .filter(([, v]) => v.point_type === "restroom")
    .sort((a, b) => (a[1].avgWaitMinutes || 0) - (b[1].avgWaitMinutes || 0));

  if (restrooms.length === 0) return null;

  const [bestId, bestData] = restrooms[0];
  const bestWait = bestData.avgWaitMinutes || 0;

  return (
    <div className="smart-card rest-card" id="best-restroom-card">
      <span className="card-tag info">
        <i className="bi bi-signpost-split" aria-hidden="true" /> Restroom
      </span>
      <div className="smart-card-header">
        <div>
          <div className="smart-card-title">
            {bestId.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
          </div>
          <div className="smart-card-subtitle">Nearest short queue</div>
        </div>
        <div className={`wait-badge ${getWaitColor(bestWait)}`}>
          <div className="wait-value">{bestWait.toFixed(0)}</div>
          <div className="wait-unit">min wait</div>
        </div>
      </div>
      <div className="options-row" style={{ marginTop: "12px" }}>
        {restrooms.map(([id, d]) => {
          const wait = d.avgWaitMinutes || 0;
          return (
            <div
              key={id}
              className={`option-pill ${id === bestId ? "best" : ""}`}
            >
              <div className="pill-name">
                {id.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
              </div>
              <div className={`pill-wait ${getWaitColor(wait)}`}>
                {wait.toFixed(1)} min
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Exit Guidance Card ──────────────────────────────────────────────
function ExitGuidanceCard({ data }) {
  if (!data) return null;

  const allExits = data.all_exits || {};
  const bestExit = data.best_exit;

  return (
    <div className="smart-card exit-card" id="exit-guidance-card">
      <span className="card-tag best">
        <i className="bi bi-box-arrow-right" aria-hidden="true" /> Recommended
        Exit
      </span>
      <div className="smart-card-header">
        <div>
          <div className="smart-card-title">{data.message}</div>
          <div className="smart-card-subtitle">
            Based on real-time congestion data
          </div>
        </div>
      </div>

      <div className="exit-map">
        {Object.entries(allExits).map(([exitId, exitData]) => {
          const score = exitData.congestionScore || 0;
          const status = exitData.status || "green";
          const isRec = exitId === bestExit;
          return (
            <div
              key={exitId}
              className={`exit-option ${isRec ? "recommended" : ""}`}
            >
              <div className="exit-name">
                {exitId
                  .replace(/_/g, " ")
                  .replace(/\b\w/g, (c) => c.toUpperCase())}
                {isRec && (
                  <i
                    className="bi bi-star-fill"
                    style={{ marginLeft: "4px" }}
                    aria-hidden="true"
                  />
                )}
              </div>
              <div
                className="exit-congestion"
                style={{ color: `var(--status-${status})` }}
              >
                {(score * 100).toFixed(0)}%
              </div>
              <div className={`exit-status ${status}`}>
                {status === "green"
                  ? "CLEAR"
                  : status === "yellow"
                    ? "BUSY"
                    : status === "orange"
                      ? "CROWDED"
                      : "AVOID"}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Page: Home (Smart Suggestions) ──────────────────────────────────
function HomePage({ bestGate, bestConc, exitGuide, queues, simStatus }) {
  const phase = PHASE_MAP[simStatus.phase] || PHASE_MAP.idle;
  const showGate =
    ["pre_game", "starting"].includes(simStatus.phase) ||
    simStatus.phase === "idle";
  const showConc = ["halftime", "in_game", "in_game_2"].includes(
    simStatus.phase,
  );
  const showExit = ["post_game"].includes(simStatus.phase);
  const showAll = simStatus.phase === "idle" || simStatus.phase === "completed";

  return (
    <div>
      <div className="phase-banner">
        <span className="phase-icon">
          <i className={phase.icon} aria-hidden="true" />
        </span>
        <div className="phase-info">
          <h2>{phase.label}</h2>
          <p>{phase.desc}</p>
        </div>
      </div>

      {(showGate || showAll) && (
        <>
          <div className="section-header">
            <span className="section-title">
              <i
                className="bi bi-door-open"
                style={{ marginRight: "6px" }}
                aria-hidden="true"
              />
              Best Gate
            </span>
            <span className="section-badge">Live</span>
          </div>
          <BestGateCard data={bestGate} />
        </>
      )}

      {(showConc || showAll) && (
        <>
          <div className="section-header">
            <span className="section-title">
              <i
                className="bi bi-cup-hot"
                style={{ marginRight: "6px" }}
                aria-hidden="true"
              />
              Food & Drinks
            </span>
            <span className="section-badge">Updated now</span>
          </div>
          <BestConcessionCard data={bestConc} />
          <BestRestroomCard queues={queues} />
        </>
      )}

      {(showExit || showAll) && (
        <>
          <div className="section-header">
            <span className="section-title">
              <i
                className="bi bi-box-arrow-right"
                style={{ marginRight: "6px" }}
                aria-hidden="true"
              />
              Exit Guide
            </span>
            <span className="section-badge">Real-time</span>
          </div>
          <ExitGuidanceCard data={exitGuide} />
        </>
      )}

      {!bestGate && !bestConc && !exitGuide && (
        <div className="empty-state">
          <div className="empty-state-emoji">
            <i className="bi bi-building" aria-hidden="true" />
          </div>
          <h3>Welcome to Stadium OS</h3>
          <p>
            Your personal stadium copilot — start the simulation from the ops
            dashboard to see live suggestions
          </p>
        </div>
      )}
    </div>
  );
}

// ── Page: All Queues ────────────────────────────────────────────────
function QueuesPage({ queues }) {
  const gates = Object.entries(queues).filter(
    ([, v]) => v.point_type === "gate",
  );
  const concs = Object.entries(queues).filter(
    ([, v]) => v.point_type === "concession",
  );
  const rests = Object.entries(queues).filter(
    ([, v]) => v.point_type === "restroom",
  );

  const renderSection = (title, items) => {
    if (items.length === 0) return null;
    const sorted = items.sort(
      (a, b) => (a[1].avgWaitMinutes || 0) - (b[1].avgWaitMinutes || 0),
    );
    return (
      <>
        <div className="section-header">
          <span className="section-title">{title}</span>
        </div>
        {sorted.map(([id, d]) => {
          const wait = d.avgWaitMinutes || 0;
          return (
            <div
              key={id}
              className="smart-card"
              style={{ padding: "14px 18px", marginBottom: "8px" }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <div>
                  <div style={{ fontWeight: 700, fontSize: "0.9rem" }}>
                    {id
                      .replace(/_/g, " ")
                      .replace(/\b\w/g, (c) => c.toUpperCase())}
                  </div>
                  <div
                    style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}
                  >
                    {d.currentQueueLength || 0} in line
                  </div>
                </div>
                <div
                  className={`wait-badge ${getWaitColor(wait)}`}
                  style={{ minWidth: "50px" }}
                >
                  <div className="wait-value" style={{ fontSize: "1.3rem" }}>
                    {wait.toFixed(1)}
                  </div>
                  <div className="wait-unit">min</div>
                </div>
              </div>
            </div>
          );
        })}
      </>
    );
  };

  return (
    <div>
      {renderSection("Gates", gates)}
      {renderSection("Concessions", concs)}
      {renderSection("Restrooms", rests)}
      {Object.keys(queues).length === 0 && (
        <div className="empty-state">
          <div className="empty-state-emoji">
            <i className="bi bi-hourglass-split" aria-hidden="true" />
          </div>
          <h3>No Queue Data</h3>
          <p>Start the simulation to see live queue information</p>
        </div>
      )}
    </div>
  );
}

// ── Page: Alerts ────────────────────────────────────────────────────
function AlertsPage() {
  const [notifs, setNotifs] = useState([]);

  useEffect(() => {
    const fetchNotifs = async () => {
      try {
        const res = await fetch(`${API_URL}/interventions/${VENUE_ID}`);
        if (res.ok) {
          const data = await res.json();
          setNotifs(data.slice(0, 20));
        }
      } catch {}
    };
    fetchNotifs();
    const interval = setInterval(fetchNotifs, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div>
      <div className="section-header">
        <span className="section-title">
          <i
            className="bi bi-bell"
            style={{ marginRight: "6px" }}
            aria-hidden="true"
          />
          Notifications
        </span>
        <span className="section-badge">{notifs.length} total</span>
      </div>
      {notifs.map((n, i) => (
        <div
          key={n.intervention_id || i}
          className="smart-card"
          style={{ padding: "14px 18px", marginBottom: "8px" }}
        >
          <div
            style={{
              fontSize: "0.7rem",
              color: "var(--text-muted)",
              marginBottom: "4px",
            }}
          >
            {n.created_at ? new Date(n.created_at).toLocaleTimeString() : ""} ·{" "}
            {(n.severity || "").toUpperCase()}
          </div>
          <div style={{ fontSize: "0.85rem", fontWeight: 600 }}>
            {n.notification?.title ||
              n.type?.replace(/_/g, " ").toUpperCase() ||
              "Alert"}
          </div>
          <div
            style={{
              fontSize: "0.8rem",
              color: "var(--text-secondary)",
              marginTop: "2px",
            }}
          >
            {n.notification?.body || n.recommendation || ""}
          </div>
        </div>
      ))}
      {notifs.length === 0 && (
        <div className="empty-state">
          <div className="empty-state-emoji">
            <i className="bi bi-bell-slash" aria-hidden="true" />
          </div>
          <h3>No Notifications Yet</h3>
          <p>You&apos;ll be alerted about shorter queues and better routes</p>
        </div>
      )}
    </div>
  );
}

// ── App Root ────────────────────────────────────────────────────────
export default function App() {
  const [activePage, setActivePage] = useState("home");
  const [notification, setNotification] = useState(null);
  const { bestGate, bestConc, exitGuide, queues, simStatus, connected } =
    useFanData();

  // Simulate receiving a notification during halftime
  useEffect(() => {
    if (simStatus.phase === "halftime" && bestConc?.best_concession) {
      const timer = setTimeout(() => {
        setNotification({
          title: "Skip the wait!",
          body: `${bestConc.best_concession.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())} has only ${(bestConc.wait_minutes || 0).toFixed(0)} min wait`,
          variant: "warning",
        });
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [simStatus.phase, bestConc]);

  const renderPage = () => {
    switch (activePage) {
      case "queues":
        return <QueuesPage queues={queues} />;
      case "alerts":
        return <AlertsPage />;
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
  };

  return (
    <div className="fan-app" id="fan-assistant">
      <a href="#fan-main" className="skip-link">
        Skip to main content
      </a>
      <NotificationToast
        notification={notification}
        onClose={() => setNotification(null)}
      />

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

      <main id="fan-main" tabIndex={-1}>
        {renderPage()}
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

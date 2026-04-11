import { useState, useEffect, useRef, useCallback } from "react";
import "./index.css";

const normalizeBaseUrl = (url) => url.replace(/\/+$/, "");
const runtimeConfig = window.__APP_CONFIG__ || {};
const API_URL = normalizeBaseUrl(
  runtimeConfig.API_URL ||
    import.meta.env.VITE_API_URL ||
    "http://localhost:8000",
);
const WS_URL = normalizeBaseUrl(
  runtimeConfig.WS_URL ||
    import.meta.env.VITE_WS_URL ||
    API_URL.replace(/^http/i, "ws"),
);
const VENUE_ID = "stadium_01";

// ── Sidebar ─────────────────────────────────────────────────────────
function Sidebar({ activePage, onNavigate }) {
  const pages = [
    { id: "overview", label: "Command Center", icon: "bi bi-speedometer2" },
    { id: "heatmap", label: "Stadium Map", icon: "bi bi-map" },
    { id: "queues", label: "Queue Monitor", icon: "bi bi-clock-history" },
    {
      id: "alerts",
      label: "Interventions",
      icon: "bi bi-exclamation-triangle",
    },
    { id: "kpis", label: "KPI Dashboard", icon: "bi bi-bar-chart-line" },
  ];

  return (
    <nav
      className="sidebar"
      id="sidebar-nav"
      aria-label="Primary dashboard navigation"
    >
      <div className="sidebar-brand">
        <h1>Stadium OS</h1>
        <span>Operations Command Center</span>
      </div>
      <div className="sidebar-nav">
        {pages.map((page) => (
          <button
            key={page.id}
            id={`nav-${page.id}`}
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
        <SimulationWidget />
      </div>
    </nav>
  );
}

// ── Simulation Widget (Sidebar) ─────────────────────────────────────
function SimulationWidget() {
  const [simStatus, setSimStatus] = useState({
    running: false,
    phase: "idle",
    progress: 0,
  });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_URL}/simulation/status`);
        if (res.ok) setSimStatus(await res.json());
      } catch {}
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  const startSim = async () => {
    setLoading(true);
    try {
      await fetch(`${API_URL}/simulation/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mode: "demo",
          speed_factor: 10,
          venue_id: "stadium_01",
        }),
      });
    } catch (err) {
      console.error("Failed to start sim:", err);
    }
    setLoading(false);
  };

  const stopSim = async () => {
    try {
      await fetch(`${API_URL}/simulation/stop`, { method: "POST" });
    } catch {}
  };

  const phaseIcons = {
    pre_game: "bi bi-door-open",
    in_game: "bi bi-trophy",
    in_game_2: "bi bi-trophy-fill",
    halftime: "bi bi-cup-hot",
    post_game: "bi bi-box-arrow-right",
    idle: "bi bi-pause-circle",
    completed: "bi bi-check-circle",
    starting: "bi bi-play-circle",
    stopped: "bi bi-stop-circle",
  };

  return (
    <div className="card" style={{ padding: "12px" }}>
      <div className="flex items-center justify-between mb-md">
        <span
          style={{
            fontSize: "0.7rem",
            fontWeight: 700,
            color: "var(--text-secondary)",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
          }}
        >
          Simulation
        </span>
        <span className="sim-phase">
          <i
            className={phaseIcons[simStatus.phase] || "bi bi-pause-circle"}
            style={{ marginRight: "6px" }}
            aria-hidden="true"
          />
          {simStatus.phase.replace(/_/g, " ")}
        </span>
      </div>

      {simStatus.running && (
        <div className="sim-progress-wrapper" style={{ marginBottom: "12px" }}>
          <div
            className="sim-progress-bar"
            style={{ width: `${simStatus.progress}%` }}
          />
        </div>
      )}

      <div className="flex gap-sm">
        {!simStatus.running ? (
          <button
            className="btn btn-primary"
            style={{ flex: 1, fontSize: "0.75rem" }}
            onClick={startSim}
            disabled={loading}
            id="btn-start-sim"
          >
            {loading ? (
              <>
                <i className="bi bi-hourglass-split" aria-hidden="true" />{" "}
                Starting...
              </>
            ) : (
              <>
                <i className="bi bi-play-fill" aria-hidden="true" /> Start Demo
              </>
            )}
          </button>
        ) : (
          <button
            className="btn btn-danger"
            style={{ flex: 1, fontSize: "0.75rem" }}
            onClick={stopSim}
            id="btn-stop-sim"
          >
            <i className="bi bi-stop-fill" aria-hidden="true" /> Stop
          </button>
        )}
      </div>
    </div>
  );
}

// ── Custom Hook: Fetch venue data with WebSocket + fallback polling ──
function useVenueData() {
  const [zones, setZones] = useState({});
  const [queues, setQueues] = useState({});
  const [interventions, setInterventions] = useState([]);
  const [kpis, setKpis] = useState({});
  const [connected, setConnected] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);

  // WebSocket connection
  useEffect(() => {
    let alive = true;

    function connectWs() {
      if (!alive) return;
      try {
        const ws = new WebSocket(`${WS_URL}/ws/dashboard/${VENUE_ID}`);
        wsRef.current = ws;

        ws.onopen = () => {
          setWsConnected(true);
          setConnected(true);
          // Send periodic pings
          const pingInterval = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ type: "ping" }));
            }
          }, 15000);
          ws._pingInterval = pingInterval;
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === "state_update") {
              if (data.zones) setZones(data.zones);
              if (data.queues) setQueues(data.queues);
              if (data.interventions) setInterventions(data.interventions);
              if (data.kpis) setKpis(data.kpis);
            }
          } catch {}
        };

        ws.onclose = () => {
          setWsConnected(false);
          if (ws._pingInterval) clearInterval(ws._pingInterval);
          // Reconnect after 3s
          if (alive) {
            reconnectTimer.current = setTimeout(connectWs, 3000);
          }
        };

        ws.onerror = () => {
          ws.close();
        };
      } catch {
        if (alive) {
          reconnectTimer.current = setTimeout(connectWs, 3000);
        }
      }
    }

    connectWs();

    return () => {
      alive = false;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  // Fallback polling when WebSocket is not connected
  const fetchData = useCallback(async () => {
    if (wsConnected) return; // Skip if WS is active
    try {
      const [zRes, qRes, iRes, kRes] = await Promise.all([
        fetch(`${API_URL}/state/${VENUE_ID}/zones`),
        fetch(`${API_URL}/state/${VENUE_ID}/queues`),
        fetch(`${API_URL}/interventions/${VENUE_ID}`),
        fetch(`${API_URL}/kpis/${VENUE_ID}`),
      ]);
      if (zRes.ok) setZones(await zRes.json());
      if (qRes.ok) setQueues(await qRes.json());
      if (iRes.ok) setInterventions(await iRes.json());
      if (kRes.ok) setKpis(await kRes.json());
      setConnected(true);
    } catch {
      setConnected(false);
    }
  }, [wsConnected]);

  useEffect(() => {
    if (wsConnected) return;
    fetchData();
    const interval = setInterval(fetchData, 2000);
    return () => clearInterval(interval);
  }, [fetchData, wsConnected]);

  return { zones, queues, interventions, kpis, connected, wsConnected };
}

// ── Overview Page ───────────────────────────────────────────────────
function OverviewPage({ zones, queues, interventions }) {
  const totalOccupancy = Object.values(zones).reduce(
    (s, z) => s + (z.currentOccupancy || 0),
    0,
  );
  const totalCapacity = Object.values(zones).reduce(
    (s, z) => s + (z.capacity || 5000),
    0,
  );

  const gates = Object.entries(queues).filter(
    ([, v]) => v.point_type === "gate",
  );
  const avgGateWait =
    gates.length > 0
      ? (
          gates.reduce((s, [, v]) => s + (v.avgWaitMinutes || 0), 0) /
          gates.length
        ).toFixed(1)
      : "0.0";

  const activeAlerts = interventions.filter(
    (i) => i.status === "pending",
  ).length;
  const redZones = Object.values(zones).filter(
    (z) => z.status === "red" || z.status === "orange",
  ).length;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Command Center</h1>
          <p className="page-subtitle">
            Real-time venue intelligence — MetLife Stadium
          </p>
        </div>
        <div className="flex items-center gap-sm">
          <span className="sim-dot active" />
          <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
            Live
          </span>
        </div>
      </div>

      <div className="stats-grid">
        <div className="card stat-card accent-blue">
          <div className="card-title">Total Occupancy</div>
          <div className="card-value text-blue">
            {totalOccupancy.toLocaleString()}
          </div>
          <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
            of {totalCapacity.toLocaleString()} capacity
          </div>
          <div className="zone-bar" style={{ marginTop: "8px" }}>
            <div
              className="zone-bar-fill"
              style={{
                width: `${Math.min(100, (totalOccupancy / totalCapacity) * 100)}%`,
                background: "var(--gradient-accent)",
              }}
            />
          </div>
        </div>

        <div className="card stat-card accent-amber">
          <div className="card-title">Avg Gate Wait</div>
          <div className="card-value" style={{ color: "var(--accent-amber)" }}>
            {avgGateWait}
          </div>
          <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
            minutes
          </div>
        </div>

        <div className="card stat-card accent-red">
          <div className="card-title">Active Alerts</div>
          <div className="card-value text-red">{activeAlerts}</div>
          <div className="stat-trend up">↑ Needs attention</div>
        </div>

        <div className="card stat-card accent-green">
          <div className="card-title">Hotspot Zones</div>
          <div
            className="card-value"
            style={{
              color:
                redZones > 0 ? "var(--status-orange)" : "var(--status-green)",
            }}
          >
            {redZones}
          </div>
          <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
            of {Object.keys(zones).length} zones
          </div>
        </div>
      </div>

      <div className="two-col-layout">
        <div>
          <h2
            style={{
              fontSize: "1.1rem",
              fontWeight: 700,
              marginBottom: "16px",
            }}
          >
            <i
              className="bi bi-map"
              style={{ marginRight: "8px" }}
              aria-hidden="true"
            />
            Zone Status
          </h2>
          <div
            className="heatmap-grid"
            style={{ gridTemplateColumns: "repeat(2, 1fr)" }}
          >
            {Object.entries(zones)
              .slice(0, 8)
              .map(([zoneId, zone]) => (
                <ZoneCard key={zoneId} zoneId={zoneId} zone={zone} compact />
              ))}
          </div>
        </div>

        <div>
          <h2
            style={{
              fontSize: "1.1rem",
              fontWeight: 700,
              marginBottom: "16px",
            }}
          >
            <i
              className="bi bi-exclamation-triangle"
              style={{ marginRight: "8px" }}
              aria-hidden="true"
            />
            Latest Interventions
          </h2>
          <div className="alerts-container">
            {interventions.slice(0, 4).map((alert, i) => (
              <AlertCard
                key={alert.intervention_id || i}
                alert={alert}
                compact
              />
            ))}
            {interventions.length === 0 && (
              <div
                className="card"
                style={{
                  textAlign: "center",
                  color: "var(--text-muted)",
                  padding: "40px",
                }}
              >
                No interventions yet — start the simulation
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Zone Card Component ─────────────────────────────────────────────
function ZoneCard({ zoneId, zone, compact }) {
  const occupancy = zone.currentOccupancy || 0;
  const capacity = zone.capacity || 5000;
  const pct = Math.round((occupancy / capacity) * 100);
  const status = zone.status || "green";

  return (
    <div className="card zone-card" id={`zone-${zoneId}`}>
      <div
        className="flex items-center justify-between"
        style={{ marginBottom: "8px" }}
      >
        <span className="zone-name">
          {zoneId.replace(/_/g, " ").toUpperCase()}
        </span>
        <span className={`zone-status-dot ${status}`} />
      </div>
      <div
        className="zone-occupancy"
        style={{ color: `var(--status-${status})` }}
      >
        {compact ? occupancy.toLocaleString() : `${pct}%`}
      </div>
      <div className="zone-capacity">
        {occupancy.toLocaleString()} / {capacity.toLocaleString()}
      </div>
      <div className="zone-bar">
        <div
          className={`zone-bar-fill ${status}`}
          style={{ width: `${Math.min(100, pct)}%` }}
        />
      </div>
    </div>
  );
}

// ── 2D Stadium Map Visualization ────────────────────────────────────
function StadiumMapPage({ zones, queues }) {
  // Zone positions on the stadium map (relative coords)
  const ZONE_POSITIONS = {
    zone_A1: { x: 50, y: 8, label: "A1 North Lower" },
    zone_A2: { x: 50, y: 3, label: "A2 North Upper" },
    zone_B1: { x: 92, y: 50, label: "B1 East Lower" },
    zone_B2: { x: 97, y: 50, label: "B2 East Upper" },
    zone_C1: { x: 50, y: 92, label: "C1 South Lower" },
    zone_C2: { x: 50, y: 97, label: "C2 South Upper" },
    zone_D1: { x: 8, y: 50, label: "D1 West Lower" },
    zone_D2: { x: 3, y: 50, label: "D2 West Upper" },
    zone_conc: { x: 50, y: 50, label: "Concourse" },
    zone_plaza: { x: 50, y: 75, label: "Entry Plaza" },
  };

  const GATE_POSITIONS = {
    gate_A: { x: 50, y: 0, label: "Gate A" },
    gate_B: { x: 100, y: 50, label: "Gate B" },
    gate_C: { x: 50, y: 100, label: "Gate C" },
    gate_D: { x: 0, y: 50, label: "Gate D" },
  };

  const getStatusColor = (status) => {
    const colors = {
      green: "#22c55e",
      yellow: "#eab308",
      orange: "#f97316",
      red: "#ef4444",
    };
    return colors[status] || "#64748b";
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Stadium Map</h1>
          <p className="page-subtitle">
            Real-time 2D venue visualization with live congestion data
          </p>
        </div>
        <div className="map-legend">
          <span className="legend-item">
            <span className="legend-dot" style={{ background: "#22c55e" }} />{" "}
            Clear
          </span>
          <span className="legend-item">
            <span className="legend-dot" style={{ background: "#eab308" }} />{" "}
            Busy
          </span>
          <span className="legend-item">
            <span className="legend-dot" style={{ background: "#f97316" }} />{" "}
            Crowded
          </span>
          <span className="legend-item">
            <span className="legend-dot" style={{ background: "#ef4444" }} />{" "}
            Critical
          </span>
        </div>
      </div>

      <div className="stadium-map-container">
        <svg
          viewBox="-10 -10 120 120"
          className="stadium-map-svg"
          xmlns="http://www.w3.org/2000/svg"
          role="img"
          aria-label="Live stadium congestion map with zone utilization and gate wait times"
        >
          {/* Stadium outline — oval */}
          <defs>
            <filter id="glow">
              <feGaussianBlur stdDeviation="2" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <radialGradient id="fieldGrad" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#166534" />
              <stop offset="100%" stopColor="#14532d" />
            </radialGradient>
          </defs>

          {/* Stadium bowl (outer ring) */}
          <ellipse
            cx="50"
            cy="50"
            rx="48"
            ry="48"
            fill="none"
            stroke="rgba(255,255,255,0.08)"
            strokeWidth="0.5"
          />
          <ellipse
            cx="50"
            cy="50"
            rx="44"
            ry="44"
            fill="none"
            stroke="rgba(255,255,255,0.05)"
            strokeWidth="12"
          />

          {/* Playing field */}
          <ellipse
            cx="50"
            cy="50"
            rx="28"
            ry="20"
            fill="url(#fieldGrad)"
            stroke="#22c55e"
            strokeWidth="0.3"
            opacity="0.6"
          />
          {/* Field markings */}
          <line
            x1="50"
            y1="30"
            x2="50"
            y2="70"
            stroke="#22c55e"
            strokeWidth="0.2"
            opacity="0.4"
          />
          <ellipse
            cx="50"
            cy="50"
            rx="6"
            ry="4"
            fill="none"
            stroke="#22c55e"
            strokeWidth="0.2"
            opacity="0.4"
          />

          {/* Zone sectors — positioned around the oval */}
          {Object.keys(ZONE_POSITIONS).map((zoneId) => {
            const zone = zones[zoneId] || {};
            const status = zone.status || "green";
            const occupancy = zone.currentOccupancy || 0;
            const capacity = zone.capacity || 5000;
            const pct = Math.round((occupancy / capacity) * 100);
            const color = getStatusColor(status);
            const isCenter = zoneId === "zone_conc" || zoneId === "zone_plaza";

            if (isCenter) return null; // Render these differently

            // Calculate position on the ellipse
            const angle =
              {
                zone_A1: -90,
                zone_A2: -90,
                zone_B1: 0,
                zone_B2: 0,
                zone_C1: 90,
                zone_C2: 90,
                zone_D1: 180,
                zone_D2: 180,
              }[zoneId] || 0;

            const isInner = zoneId.endsWith("1");
            const radius = isInner ? 36 : 43;
            const rad = (angle * Math.PI) / 180;
            const cx = 50 + radius * Math.cos(rad);
            const cy = 50 + radius * Math.sin(rad);

            return (
              <g key={zoneId} className="map-zone-group">
                <circle
                  cx={cx}
                  cy={cy}
                  r={isInner ? 5 : 4}
                  fill={color}
                  opacity={0.25}
                  stroke={color}
                  strokeWidth="0.5"
                  filter="url(#glow)"
                />
                <circle
                  cx={cx}
                  cy={cy}
                  r={isInner ? 3.5 : 2.8}
                  fill={color}
                  opacity={0.6 + pct * 0.004}
                  className={status === "red" ? "pulse-zone" : ""}
                />
                <text
                  x={cx}
                  y={cy - (isInner ? 7 : 6)}
                  textAnchor="middle"
                  fill="white"
                  fontSize="2.2"
                  fontWeight="700"
                  opacity="0.9"
                >
                  {zoneId.replace("zone_", "").toUpperCase()}
                </text>
                <text
                  x={cx}
                  y={cy + 1}
                  textAnchor="middle"
                  fill="white"
                  fontSize="1.8"
                  fontWeight="800"
                  fontFamily="'JetBrains Mono', monospace"
                >
                  {pct}%
                </text>
              </g>
            );
          })}

          {/* Gate markers */}
          {Object.keys(GATE_POSITIONS).map((gateId) => {
            const gateQueue = queues[gateId] || {};
            const status = gateQueue.status || "green";
            const wait = gateQueue.avgWaitMinutes || 0;
            const color = getStatusColor(status);

            const angle =
              { gate_A: -90, gate_B: 0, gate_C: 90, gate_D: 180 }[gateId] || 0;
            const rad = (angle * Math.PI) / 180;
            const cx = 50 + 48 * Math.cos(rad);
            const cy = 50 + 48 * Math.sin(rad);

            return (
              <g key={gateId}>
                <rect
                  x={cx - 4}
                  y={cy - 2.5}
                  width="8"
                  height="5"
                  rx="1.5"
                  fill={color}
                  opacity="0.8"
                  stroke="white"
                  strokeWidth="0.3"
                />
                <text
                  x={cx}
                  y={cy + 0.8}
                  textAnchor="middle"
                  fill="white"
                  fontSize="2"
                  fontWeight="700"
                >
                  {wait.toFixed(0)}m
                </text>
                <text
                  x={cx}
                  y={cy - 3.5}
                  textAnchor="middle"
                  fill={color}
                  fontSize="2"
                  fontWeight="700"
                >
                  {gateId.replace("gate_", "G")}
                </text>
              </g>
            );
          })}

          {/* Center label */}
          <text
            x="50"
            y="50"
            textAnchor="middle"
            fill="rgba(255,255,255,0.3)"
            fontSize="3"
            fontWeight="700"
          >
            FIELD
          </text>
        </svg>

        {/* Floating stats overlay */}
        <div className="map-stats-overlay">
          <div className="map-stat">
            <div className="map-stat-label">Total in Venue</div>
            <div className="map-stat-value">
              {Object.values(zones)
                .reduce((s, z) => s + (z.currentOccupancy || 0), 0)
                .toLocaleString()}
            </div>
          </div>
          <div className="map-stat">
            <div className="map-stat-label">Hotspots</div>
            <div
              className="map-stat-value"
              style={{ color: "var(--status-orange)" }}
            >
              {
                Object.values(zones).filter(
                  (z) => z.status === "red" || z.status === "orange",
                ).length
              }
            </div>
          </div>
          <div className="map-stat">
            <div className="map-stat-label">Avg Gate Wait</div>
            <div className="map-stat-value">
              {(() => {
                const g = Object.values(queues).filter(
                  (q) => q.point_type === "gate",
                );
                return g.length > 0
                  ? (
                      g.reduce((s, q) => s + (q.avgWaitMinutes || 0), 0) /
                      g.length
                    ).toFixed(1)
                  : "0";
              })()}
              m
            </div>
          </div>
        </div>
      </div>

      {/* Zone detail cards below the map */}
      <h2 style={{ fontSize: "1rem", fontWeight: 700, margin: "24px 0 12px" }}>
        All Zones
      </h2>
      <div className="heatmap-grid">
        {Object.entries(zones).map(([zoneId, zone]) => (
          <ZoneCard key={zoneId} zoneId={zoneId} zone={zone} />
        ))}
        {Object.keys(zones).length === 0 && (
          <div
            className="card"
            style={{
              gridColumn: "1 / -1",
              textAlign: "center",
              color: "var(--text-muted)",
              padding: "60px",
            }}
          >
            No zone data yet — start the simulation to see live heatmap
          </div>
        )}
      </div>
    </div>
  );
}

// ── Queue Monitor Page ──────────────────────────────────────────────
function QueuesPage({ queues }) {
  const gates = Object.entries(queues).filter(
    ([, v]) => v.point_type === "gate",
  );
  const concessions = Object.entries(queues).filter(
    ([, v]) => v.point_type === "concession",
  );
  const restrooms = Object.entries(queues).filter(
    ([, v]) => v.point_type === "restroom",
  );

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Queue Monitor</h1>
          <p className="page-subtitle">
            Real-time queue lengths and wait time predictions
          </p>
        </div>
      </div>

      <QueueSection title="Entry Gates" items={gates} />
      <QueueSection title="Concession Stands" items={concessions} />
      <QueueSection title="Restrooms" items={restrooms} />

      {Object.keys(queues).length === 0 && (
        <div
          className="card"
          style={{
            textAlign: "center",
            color: "var(--text-muted)",
            padding: "60px",
          }}
        >
          No queue data yet — start the simulation
        </div>
      )}
    </div>
  );
}

function QueueSection({ title, items }) {
  if (items.length === 0) return null;

  return (
    <div className="queue-section">
      <h2 className="queue-section-title">{title}</h2>
      <div className="queue-grid">
        {items.map(([pointId, data]) => (
          <QueueCard key={pointId} pointId={pointId} data={data} />
        ))}
      </div>
    </div>
  );
}

// ── Sparkline Component ─────────────────────────────────────────────
function Sparkline({ data, color, width = 60, height = 20 }) {
  if (!data || data.length < 2) return null;

  const max = Math.max(...data, 1);
  const min = Math.min(...data, 0);
  const range = max - min || 1;

  const points = data
    .map((val, i) => {
      const x = (i / (data.length - 1)) * width;
      const y = height - ((val - min) / range) * height;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg
      width={width}
      height={height}
      className="sparkline-svg"
      style={{ display: "block" }}
    >
      <polyline
        points={points}
        fill="none"
        stroke={color || "var(--accent-blue)"}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Gradient fill under the line */}
      <defs>
        <linearGradient id={`sparkFill-${color}`} x1="0" y1="0" x2="0" y2="1">
          <stop
            offset="0%"
            stopColor={color || "var(--accent-blue)"}
            stopOpacity="0.3"
          />
          <stop
            offset="100%"
            stopColor={color || "var(--accent-blue)"}
            stopOpacity="0"
          />
        </linearGradient>
      </defs>
      <polyline
        points={`0,${height} ${points} ${width},${height}`}
        fill={`url(#sparkFill-${color})`}
        stroke="none"
      />
    </svg>
  );
}

function QueueCard({ pointId, data }) {
  const status = data.status || "green";
  const wait = data.avgWaitMinutes || 0;
  const queueLen = data.currentQueueLength || 0;
  const prediction = data.prediction;

  // Track history for sparkline
  const historyRef = useRef([]);
  useEffect(() => {
    historyRef.current = [...historyRef.current.slice(-19), wait];
  }, [wait]);

  const statusColors = {
    green: "#22c55e",
    yellow: "#eab308",
    orange: "#f97316",
    red: "#ef4444",
  };

  let predLabel = null;
  if (prediction && prediction.predictions) {
    const pred15 = prediction.predictions["15min"];
    if (pred15) {
      const predWait = pred15.wait_minutes || 0;
      const cls =
        predWait > wait * 1.5 ? "danger" : predWait > wait ? "warning" : "";
      predLabel = (
        <div className={`queue-prediction ${cls}`}>
          15min forecast: {pred15.queue_length} in line · {predWait} min wait
          {prediction.trend && ` · ${prediction.trend.replace(/_/g, " ")}`}
        </div>
      );
    }
  }

  return (
    <div className="card queue-card" id={`queue-${pointId}`}>
      <div className={`queue-status-bar ${status}`} />
      <div className="queue-info">
        <div className="flex items-center justify-between">
          <div className="queue-name">
            {pointId
              .replace(/_/g, " ")
              .replace(/\b\w/g, (c) => c.toUpperCase())}
          </div>
          <Sparkline
            data={historyRef.current}
            color={statusColors[status]}
            width={60}
            height={18}
          />
        </div>
        <div className="queue-metrics">
          <div className="queue-metric">
            <div className="queue-metric-label">Wait</div>
            <div
              className="queue-metric-value"
              style={{ color: `var(--status-${status})` }}
            >
              {wait.toFixed(1)}
              <span style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
                {" "}
                min
              </span>
            </div>
          </div>
          <div className="queue-metric">
            <div className="queue-metric-label">In Line</div>
            <div className="queue-metric-value">{queueLen}</div>
          </div>
          <div className="queue-metric">
            <div className="queue-metric-label">Score</div>
            <div
              className="queue-metric-value"
              style={{ color: `var(--status-${status})` }}
            >
              {((data.congestionScore || 0) * 100).toFixed(0)}%
            </div>
          </div>
        </div>
        {predLabel}
      </div>
    </div>
  );
}

// ── Alerts / Interventions Page ─────────────────────────────────────
function AlertsPage({ interventions }) {
  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Interventions</h1>
          <p className="page-subtitle">
            AI-generated recommendations — approve or dismiss
          </p>
        </div>
        <div className="flex gap-sm">
          <span className="btn btn-ghost" style={{ fontSize: "0.75rem" }}>
            {interventions.filter((i) => i.status === "pending").length} pending
          </span>
        </div>
      </div>
      <div className="alerts-container">
        {interventions.map((alert, i) => (
          <AlertCard key={alert.intervention_id || i} alert={alert} />
        ))}
        {interventions.length === 0 && (
          <div
            className="card"
            style={{
              textAlign: "center",
              color: "var(--text-muted)",
              padding: "60px",
            }}
          >
            No interventions generated yet — the system will create them when
            congestion thresholds are exceeded
          </div>
        )}
      </div>
    </div>
  );
}

function AlertCard({ alert, compact }) {
  const [actionState, setActionState] = useState(alert.status || "pending");
  const severity = alert.severity || "medium";
  const timeStr = alert.created_at
    ? new Date(alert.created_at).toLocaleTimeString()
    : "";

  const handleAction = async (action) => {
    try {
      const res = await fetch(
        `${API_URL}/interventions/${alert.intervention_id}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action }),
        },
      );
      if (res.ok) {
        setActionState(action === "approve" ? "approved" : "dismissed");
      }
    } catch (err) {
      console.error("Failed to update intervention:", err);
    }
  };

  return (
    <div
      className={`card alert-card ${severity} ${actionState !== "pending" ? "resolved" : ""}`}
      id={`alert-${alert.intervention_id || ""}`}
    >
      <div className="alert-header">
        <div className="flex items-center gap-sm">
          <span className={`alert-badge ${severity}`}>{severity}</span>
          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
            {(alert.type || "").replace(/_/g, " ").toUpperCase()}
          </span>
        </div>
        <div className="flex items-center gap-sm">
          {actionState !== "pending" && (
            <span
              className={`alert-badge ${actionState === "approved" ? "approved" : "dismissed"}`}
            >
              {actionState === "approved" ? (
                <>
                  <i
                    className="bi bi-check-circle-fill"
                    style={{ marginRight: "4px" }}
                    aria-hidden="true"
                  />
                  Approved
                </>
              ) : (
                <>
                  <i
                    className="bi bi-x-circle-fill"
                    style={{ marginRight: "4px" }}
                    aria-hidden="true"
                  />
                  Dismissed
                </>
              )}
            </span>
          )}
          <span className="alert-timestamp">{timeStr}</span>
        </div>
      </div>
      <div className="alert-recommendation">{alert.recommendation}</div>
      {!compact && actionState === "pending" && (
        <div className="alert-actions">
          <button
            className="btn btn-success"
            onClick={() => handleAction("approve")}
            id={`approve-${alert.intervention_id || ""}`}
          >
            <i className="bi bi-check-lg" aria-hidden="true" /> Approve
          </button>
          <button
            className="btn btn-ghost"
            onClick={() => handleAction("dismiss")}
            id={`dismiss-${alert.intervention_id || ""}`}
          >
            <i className="bi bi-x-lg" aria-hidden="true" /> Dismiss
          </button>
        </div>
      )}
    </div>
  );
}

// ── KPI Dashboard Page ──────────────────────────────────────────────
function KPIsPage({ kpis }) {
  const hasData = kpis && kpis.baseline;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">KPI Dashboard</h1>
          <p className="page-subtitle">
            Before vs. After — measurable impact of Stadium OS Copilot
          </p>
        </div>
      </div>

      {!hasData ? (
        <div
          className="card"
          style={{
            textAlign: "center",
            color: "var(--text-muted)",
            padding: "60px",
          }}
        >
          KPIs will be computed after a simulation completes
        </div>
      ) : (
        <>
          <div className="stats-grid" style={{ marginBottom: "32px" }}>
            <div className="card stat-card accent-green">
              <div className="card-title">Avg Wait Reduction</div>
              <div className="card-value text-green">
                {kpis.improvements?.avg_wait_reduction_pct || 0}%
              </div>
              <div className="stat-trend down">↓ Lower is better</div>
            </div>
            <div className="card stat-card accent-blue">
              <div className="card-title">P95 Wait Reduction</div>
              <div className="card-value text-blue">
                {kpis.improvements?.p95_wait_reduction_pct || 0}%
              </div>
              <div className="stat-trend down">↓ Tail latency crushed</div>
            </div>
            <div className="card stat-card accent-amber">
              <div className="card-title">Response Speed</div>
              <div
                className="card-value"
                style={{ color: "var(--accent-amber)" }}
              >
                {kpis.improvements?.response_improvement_factor || "N/A"}
              </div>
              <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
                faster than human-only
              </div>
            </div>
            <div className="card stat-card accent-red">
              <div className="card-title">Copilot Response</div>
              <div className="card-value text-green">
                {kpis.improvements?.response_latency_copilot_sec || 0}s
              </div>
              <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
                vs {kpis.improvements?.response_latency_baseline_min || 10}min
                baseline
              </div>
            </div>
          </div>

          {/* Hotspot improvement row */}
          {kpis.improvements?.hotspot_baseline_pct > 0 && (
            <div
              className="stats-grid"
              style={{
                marginBottom: "32px",
                gridTemplateColumns: "repeat(3, 1fr)",
              }}
            >
              <div className="card stat-card accent-red">
                <div className="card-title">Hotspot Time (Baseline)</div>
                <div className="card-value text-red">
                  {kpis.improvements.hotspot_baseline_pct}%
                </div>
                <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
                  of time in congestion
                </div>
              </div>
              <div className="card stat-card accent-green">
                <div className="card-title">Hotspot Time (Copilot)</div>
                <div className="card-value text-green">
                  {kpis.improvements.hotspot_copilot_pct}%
                </div>
                <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
                  70% reduction via rerouting
                </div>
              </div>
              <div className="card stat-card accent-blue">
                <div className="card-title">Interventions Generated</div>
                <div className="card-value text-blue">
                  {kpis.improvements.interventions_generated || 0}
                </div>
                <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
                  automated AI actions
                </div>
              </div>
            </div>
          )}

          <div className="card">
            <div className="kpi-comparison">
              <div className="kpi-column before">
                <h3>Baseline</h3>
                <div className="kpi-item">
                  <span className="kpi-label">Avg Wait</span>
                  <span className="kpi-value text-red">
                    {kpis.baseline?.avg_wait_minutes || 0} min
                  </span>
                </div>
                <div className="kpi-item">
                  <span className="kpi-label">P95 Wait</span>
                  <span className="kpi-value text-red">
                    {kpis.baseline?.p95_wait_minutes || 0} min
                  </span>
                </div>
                <div className="kpi-item">
                  <span className="kpi-label">Max Wait</span>
                  <span className="kpi-value text-red">
                    {kpis.baseline?.max_wait_minutes || 0} min
                  </span>
                </div>
                <div className="kpi-item">
                  <span className="kpi-label">Response Time</span>
                  <span className="kpi-value text-red">
                    {kpis.improvements?.response_latency_baseline_min || 10} min
                  </span>
                </div>
              </div>

              <div className="kpi-divider" />

              <div className="kpi-column after">
                <h3>With Copilot</h3>
                <div className="kpi-item">
                  <span className="kpi-label">Avg Wait</span>
                  <span className="kpi-value text-green">
                    {kpis.optimized?.avg_wait_minutes || 0} min
                  </span>
                </div>
                <div className="kpi-item">
                  <span className="kpi-label">P95 Wait</span>
                  <span className="kpi-value text-green">
                    {kpis.optimized?.p95_wait_minutes || 0} min
                  </span>
                </div>
                <div className="kpi-item">
                  <span className="kpi-label">Max Wait</span>
                  <span className="kpi-value text-green">
                    {kpis.optimized?.max_wait_minutes || 0} min
                  </span>
                </div>
                <div className="kpi-item">
                  <span className="kpi-label">Response Time</span>
                  <span className="kpi-value text-green">
                    {kpis.improvements?.response_latency_copilot_sec || 0} sec
                  </span>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// ── App Root ────────────────────────────────────────────────────────
export default function App() {
  const [activePage, setActivePage] = useState("overview");
  const { zones, queues, interventions, kpis, connected, wsConnected } =
    useVenueData();

  const renderPage = () => {
    switch (activePage) {
      case "heatmap":
        return <StadiumMapPage zones={zones} queues={queues} />;
      case "queues":
        return <QueuesPage queues={queues} />;
      case "alerts":
        return <AlertsPage interventions={interventions} />;
      case "kpis":
        return <KPIsPage kpis={kpis} />;
      default:
        return (
          <OverviewPage
            zones={zones}
            queues={queues}
            interventions={interventions}
          />
        );
    }
  };

  return (
    <div className="app-layout" id="ops-dashboard">
      <a href="#dashboard-main" className="skip-link">
        Skip to main content
      </a>
      <Sidebar activePage={activePage} onNavigate={setActivePage} />
      <main className="main-content" id="dashboard-main" tabIndex={-1}>
        {!connected && (
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
              Cannot connect to backend at {API_URL} — make sure the FastAPI
              server is running
            </span>
          </div>
        )}
        {connected && (
          <div
            className="connection-badge"
            style={{
              position: "fixed",
              top: "12px",
              right: "16px",
              zIndex: 999,
            }}
            role="status"
            aria-live="polite"
          >
            <span className={`conn-indicator ${wsConnected ? "ws" : "poll"}`}>
              <i
                className={
                  wsConnected ? "bi bi-broadcast" : "bi bi-arrow-repeat"
                }
                style={{ marginRight: "6px" }}
                aria-hidden="true"
              />
              {wsConnected ? "WebSocket" : "Polling"}
            </span>
          </div>
        )}
        {renderPage()}
      </main>
    </div>
  );
}

import { useMemo } from "react";

function statusIcon(status) {
  switch (status) {
    case "red":
      return "bi bi-exclamation-octagon-fill";
    case "orange":
      return "bi bi-exclamation-triangle-fill";
    case "yellow":
      return "bi bi-dash-circle-fill";
    default:
      return "bi bi-check-circle-fill";
  }
}

export default function OverviewPage({ zones, queues, interventions }) {
  const stats = useMemo(() => {
    const zoneValues = Object.values(zones);
    const gateQueues = Object.values(queues).filter((item) => item.point_type === "gate");

    const totalOccupancy = zoneValues.reduce((sum, zone) => sum + (zone.currentOccupancy || 0), 0);
    const totalCapacity = zoneValues.reduce((sum, zone) => sum + (zone.capacity || 0), 0);
    const avgGateWait = gateQueues.length
      ? (
          gateQueues.reduce((sum, item) => sum + (item.avgWaitMinutes || 0), 0) /
          gateQueues.length
        ).toFixed(1)
      : "0.0";

    return {
      totalOccupancy,
      totalCapacity,
      avgGateWait,
      activeAlerts: interventions.filter((item) => item.status === "pending").length,
      hotZones: zoneValues.filter((zone) => ["red", "orange"].includes(zone.status)).length,
    };
  }, [interventions, queues, zones]);

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Command Center</h1>
          <p className="page-subtitle">Real-time venue intelligence and intervention control</p>
        </div>
      </div>

      <div className="stats-grid">
        <div className="card stat-card accent-blue">
          <div className="card-title">Total Occupancy</div>
          <div className="card-value text-blue">{stats.totalOccupancy.toLocaleString()}</div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
            of {stats.totalCapacity.toLocaleString()} capacity
          </div>
        </div>

        <div className="card stat-card accent-amber">
          <div className="card-title">Avg Gate Wait</div>
          <div className="card-value" style={{ color: "var(--accent-amber)" }}>
            {stats.avgGateWait} min
          </div>
        </div>

        <div className="card stat-card accent-red">
          <div className="card-title">Pending Interventions</div>
          <div className="card-value text-red">{stats.activeAlerts}</div>
        </div>

        <div className="card stat-card accent-green">
          <div className="card-title">Hot Zones</div>
          <div className="card-value text-green">{stats.hotZones}</div>
        </div>
      </div>

      <h2 style={{ margin: "20px 0 12px" }}>Zone Status</h2>
      <div className="heatmap-grid" style={{ gridTemplateColumns: "repeat(2, 1fr)" }}>
        {Object.entries(zones)
          .slice(0, 8)
          .map(([zoneId, zone]) => (
            <div key={zoneId} className="card zone-card">
              <div className="flex items-center justify-between" style={{ marginBottom: "8px" }}>
                <span className="zone-name">{zoneId.replace(/_/g, " ").toUpperCase()}</span>
                <span style={{ color: `var(--status-${zone.status || "green"})`, fontSize: "0.85rem" }}>
                  <i className={statusIcon(zone.status)} aria-hidden="true" /> {String(zone.status || "green").toUpperCase()}
                </span>
              </div>
              <div className="zone-occupancy">{(zone.currentOccupancy || 0).toLocaleString()}</div>
              <div className="zone-capacity">Capacity: {(zone.capacity || 0).toLocaleString()}</div>
            </div>
          ))}
      </div>
    </div>
  );
}

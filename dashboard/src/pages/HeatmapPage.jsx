export default function HeatmapPage({ zones, queues }) {
  const gateQueues = Object.entries(queues).filter(
    ([, queue]) => queue.point_type === "gate",
  );

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Stadium Map</h1>
          <p className="page-subtitle">
            Live congestion scoreboard with non-color status labels
          </p>
        </div>
      </div>

      <div className="card" style={{ marginBottom: "16px" }}>
        <h2 style={{ marginBottom: "12px" }}>Zone Congestion</h2>
        <div className="queue-grid">
          {Object.entries(zones).map(([zoneId, zone]) => (
            <div key={zoneId} className="queue-card card">
              <div className="queue-name">
                {zoneId.replace(/_/g, " ").toUpperCase()}
              </div>
              <div className="queue-metrics">
                <div className="queue-metric">
                  <div className="queue-metric-label">Status</div>
                  <div className="queue-metric-value">
                    {String(zone.status || "green").toUpperCase()}
                  </div>
                </div>
                <div className="queue-metric">
                  <div className="queue-metric-label">Occupancy</div>
                  <div className="queue-metric-value">
                    {(zone.currentOccupancy || 0).toLocaleString()}
                  </div>
                </div>
                <div className="queue-metric">
                  <div className="queue-metric-label">Capacity %</div>
                  <div className="queue-metric-value">
                    {zone.capacity
                      ? Math.round(
                          ((zone.currentOccupancy || 0) / zone.capacity) * 100,
                        )
                      : 0}
                    %
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <h2 style={{ marginBottom: "12px" }}>Gate Queue Snapshot</h2>
        {gateQueues.length === 0 ? (
          <p style={{ color: "var(--text-muted)" }}>
            No gate queue data available.
          </p>
        ) : (
          gateQueues.map(([gateId, queue]) => (
            <div
              key={gateId}
              className="flex items-center justify-between"
              style={{ marginBottom: "8px" }}
            >
              <span>{gateId.replace(/_/g, " ").toUpperCase()}</span>
              <span>
                {queue.avgWaitMinutes || 0} min wait |{" "}
                {(queue.currentQueueLength || 0).toLocaleString()} in line
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

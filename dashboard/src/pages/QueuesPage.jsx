import { memo } from "react";

function QueueSection({ title, items }) {
  if (items.length === 0) {
    return null;
  }

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

const QueueCard = memo(function QueueCard({ pointId, data }) {
  return (
    <div className="card queue-card">
      <div className={`queue-status-bar ${data.status || "green"}`} />
      <div className="queue-info">
        <div className="queue-name">{pointId.replace(/_/g, " ").toUpperCase()}</div>
        <div className="queue-metrics">
          <div className="queue-metric">
            <div className="queue-metric-label">Wait</div>
            <div className="queue-metric-value">{(data.avgWaitMinutes || 0).toFixed(1)} min</div>
          </div>
          <div className="queue-metric">
            <div className="queue-metric-label">In Line</div>
            <div className="queue-metric-value">{data.currentQueueLength || 0}</div>
          </div>
          <div className="queue-metric">
            <div className="queue-metric-label">Status</div>
            <div className="queue-metric-value">{String(data.status || "green").toUpperCase()}</div>
          </div>
        </div>
      </div>
    </div>
  );
});

export default function QueuesPage({ queues }) {
  const gates = Object.entries(queues).filter(([, queue]) => queue.point_type === "gate");
  const concessions = Object.entries(queues).filter(([, queue]) => queue.point_type === "concession");
  const restrooms = Object.entries(queues).filter(([, queue]) => queue.point_type === "restroom");

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Queue Monitor</h1>
          <p className="page-subtitle">Real-time queue lengths and wait predictions</p>
        </div>
      </div>

      <QueueSection title="Entry Gates" items={gates} />
      <QueueSection title="Concession Stands" items={concessions} />
      <QueueSection title="Restrooms" items={restrooms} />

      {Object.keys(queues).length === 0 && (
        <div className="card" style={{ textAlign: "center", color: "var(--text-muted)", padding: "60px" }}>
          No queue data yet - start the simulation
        </div>
      )}
    </div>
  );
}

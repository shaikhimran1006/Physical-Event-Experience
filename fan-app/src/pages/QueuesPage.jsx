function waitClass(waitMinutes) {
  if (waitMinutes <= 3) return "green";
  if (waitMinutes <= 7) return "yellow";
  if (waitMinutes <= 12) return "orange";
  return "red";
}

function QueueSection({ title, items }) {
  if (items.length === 0) {
    return null;
  }

  const sorted = [...items].sort(
    (a, b) => (a[1].avgWaitMinutes || 0) - (b[1].avgWaitMinutes || 0),
  );

  return (
    <>
      <div className="section-header">
        <span className="section-title">{title}</span>
      </div>
      {sorted.map(([id, data]) => {
        const wait = data.avgWaitMinutes || 0;
        return (
          <div key={id} className="smart-card" style={{ padding: "14px 18px", marginBottom: "8px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <div style={{ fontWeight: 700, fontSize: "0.9rem" }}>
                  {id.replace(/_/g, " ").toUpperCase()}
                </div>
                <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
                  {data.currentQueueLength || 0} in line
                </div>
              </div>
              <div className={`wait-badge ${waitClass(wait)}`} style={{ minWidth: "50px" }}>
                <div className="wait-value" style={{ fontSize: "1.3rem" }}>{wait.toFixed(1)}</div>
                <div className="wait-unit">min</div>
              </div>
            </div>
          </div>
        );
      })}
    </>
  );
}

export default function QueuesPage({ queues }) {
  const gates = Object.entries(queues).filter(([, value]) => value.point_type === "gate");
  const concessions = Object.entries(queues).filter(([, value]) => value.point_type === "concession");
  const restrooms = Object.entries(queues).filter(([, value]) => value.point_type === "restroom");

  return (
    <div>
      <QueueSection title="Gates" items={gates} />
      <QueueSection title="Concessions" items={concessions} />
      <QueueSection title="Restrooms" items={restrooms} />

      {Object.keys(queues).length === 0 && (
        <div className="empty-state">
          <div className="empty-state-emoji">
            <i className="bi bi-hourglass-split" aria-hidden="true" />
          </div>
          <h3>No Queue Data</h3>
          <p>Start simulation to display live queue information.</p>
        </div>
      )}
    </div>
  );
}

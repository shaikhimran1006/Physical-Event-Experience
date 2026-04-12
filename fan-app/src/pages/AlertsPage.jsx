export default function AlertsPage({ notifications }) {
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
        <span className="section-badge">{notifications.length} total</span>
      </div>

      {notifications.map((notification) => (
        <div
          key={notification.intervention_id}
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
            {notification.created_at
              ? new Date(notification.created_at).toLocaleTimeString()
              : ""}
          </div>
          <div style={{ fontSize: "0.85rem", fontWeight: 600 }}>
            {notification.notification?.title ||
              notification.type?.replace(/_/g, " ").toUpperCase() ||
              "Alert"}
          </div>
          <div
            style={{
              fontSize: "0.8rem",
              color: "var(--text-secondary)",
              marginTop: "2px",
            }}
          >
            {notification.notification?.body ||
              notification.recommendation ||
              ""}
          </div>
        </div>
      ))}

      {notifications.length === 0 && (
        <div className="empty-state">
          <div className="empty-state-emoji">
            <i className="bi bi-bell-slash" aria-hidden="true" />
          </div>
          <h3>No Notifications Yet</h3>
          <p>You will be alerted when better routes or queues are available.</p>
        </div>
      )}
    </div>
  );
}

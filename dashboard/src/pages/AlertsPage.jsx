import { useState } from "react";

import { requestJson } from "../services/apiClient";

function AlertCard({ alert }) {
  const [state, setState] = useState(alert.status || "pending");

  const handleAction = async (action) => {
    const result = await requestJson(
      `/interventions/${alert.intervention_id}`,
      {
        method: "PUT",
        auth: true,
        body: { action },
      },
    );

    if (result.ok) {
      setState(action === "approve" ? "approved" : "dismissed");
    }
  };

  return (
    <div
      className={`card alert-card ${alert.severity || "medium"} ${state !== "pending" ? "resolved" : ""}`}
    >
      <div className="alert-header">
        <div className="flex items-center gap-sm">
          <span className={`alert-badge ${alert.severity || "medium"}`}>
            {alert.severity || "medium"}
          </span>
          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
            {(alert.type || "alert").replace(/_/g, " ").toUpperCase()}
          </span>
        </div>
        <span className="alert-timestamp">
          {alert.created_at
            ? new Date(alert.created_at).toLocaleTimeString()
            : ""}
        </span>
      </div>

      <div className="alert-recommendation">
        {alert.recommendation || "No recommendation text"}
      </div>

      {state === "pending" && (
        <div className="alert-actions">
          <button
            className="btn btn-success"
            onClick={() => handleAction("approve")}
          >
            Approve
          </button>
          <button
            className="btn btn-ghost"
            onClick={() => handleAction("dismiss")}
          >
            Dismiss
          </button>
        </div>
      )}
    </div>
  );
}

export default function AlertsPage({ interventions }) {
  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Interventions</h1>
          <p className="page-subtitle">AI-generated operational actions</p>
        </div>
      </div>

      <div className="alerts-container">
        {interventions.map((item) => (
          <AlertCard key={item.intervention_id} alert={item} />
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
            No interventions generated yet
          </div>
        )}
      </div>
    </div>
  );
}

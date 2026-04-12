import { useState } from "react";

import { requestJson } from "../services/apiClient";
import { VENUE_ID } from "../services/runtimeConfig";

const PHASE_ICONS = {
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

export default function SimulationWidget({ simStatus, onRefresh }) {
  const [busy, setBusy] = useState(false);

  const startSimulation = async () => {
    setBusy(true);
    await requestJson("/simulation/start", {
      method: "POST",
      auth: true,
      body: { mode: "demo", speed_factor: 10, venue_id: VENUE_ID },
    });
    await onRefresh();
    setBusy(false);
  };

  const stopSimulation = async () => {
    setBusy(true);
    await requestJson("/simulation/stop", {
      method: "POST",
      auth: true,
    });
    await onRefresh();
    setBusy(false);
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
        <span className="sim-phase" aria-live="polite">
          <i
            className={PHASE_ICONS[simStatus?.phase] || "bi bi-pause-circle"}
            style={{ marginRight: "6px" }}
            aria-hidden="true"
          />
          {String(simStatus?.phase || "idle").replace(/_/g, " ")}
        </span>
      </div>

      {simStatus?.running && (
        <div className="sim-progress-wrapper" style={{ marginBottom: "12px" }}>
          <div
            className="sim-progress-bar"
            style={{ width: `${simStatus?.progress || 0}%` }}
          />
        </div>
      )}

      {!simStatus?.running ? (
        <button
          className="btn btn-primary"
          style={{ width: "100%", fontSize: "0.75rem" }}
          onClick={startSimulation}
          disabled={busy}
          aria-label="Start simulation"
        >
          <i className="bi bi-play-fill" aria-hidden="true" />
          {busy ? " Starting..." : " Start Demo"}
        </button>
      ) : (
        <button
          className="btn btn-danger"
          style={{ width: "100%", fontSize: "0.75rem" }}
          onClick={stopSimulation}
          disabled={busy}
          aria-label="Stop simulation"
        >
          <i className="bi bi-stop-fill" aria-hidden="true" /> Stop
        </button>
      )}
    </div>
  );
}

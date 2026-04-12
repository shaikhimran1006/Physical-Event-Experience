const PHASE_MAP = {
  pre_game: {
    icon: "bi bi-door-open",
    label: "Pre-Game",
    desc: "Gates are open - find your fastest entry",
  },
  in_game: {
    icon: "bi bi-trophy",
    label: "Game On",
    desc: "Enjoy the action and monitor queue updates",
  },
  in_game_2: {
    icon: "bi bi-trophy-fill",
    label: "Second Half",
    desc: "Prepare an exit route before crowds spike",
  },
  halftime: {
    icon: "bi bi-cup-hot",
    label: "Halftime",
    desc: "Great time for concessions and restrooms",
  },
  post_game: {
    icon: "bi bi-box-arrow-right",
    label: "Game Over",
    desc: "Follow low-congestion exit guidance",
  },
  idle: {
    icon: "bi bi-pause-circle",
    label: "Standby",
    desc: "Waiting for live event updates",
  },
};

function waitClass(waitMinutes) {
  if (waitMinutes <= 3) return "green";
  if (waitMinutes <= 7) return "yellow";
  if (waitMinutes <= 12) return "orange";
  return "red";
}

function GateCard({ bestGate }) {
  if (!bestGate?.best_gate) {
    return null;
  }

  const bestName = bestGate.best_gate.replace(/_/g, " ").toUpperCase();
  const wait = bestGate.wait_minutes || 0;

  return (
    <div className="smart-card gate-card" id="best-gate-card">
      <span className="card-tag best">
        <i className="bi bi-award" aria-hidden="true" /> Best Choice
      </span>
      <div className="smart-card-header">
        <div>
          <div className="smart-card-title">{bestName}</div>
          <div className="smart-card-subtitle">Fastest entry right now</div>
        </div>
        <div className={`wait-badge ${waitClass(wait)}`}>
          <div className="wait-value">{wait.toFixed(0)}</div>
          <div className="wait-unit">min wait</div>
        </div>
      </div>
    </div>
  );
}

function ConcessionCard({ bestConc }) {
  if (!bestConc?.best_concession) {
    return null;
  }

  const name = bestConc.best_concession.replace(/_/g, " ").toUpperCase();
  const wait = bestConc.wait_minutes || 0;

  return (
    <div className="smart-card conc-card" id="best-concession-card">
      <span className="card-tag best">
        <i className="bi bi-cup-hot" aria-hidden="true" /> Shortest Queue
      </span>
      <div className="smart-card-header">
        <div>
          <div className="smart-card-title">{name}</div>
          <div className="smart-card-subtitle">Best concession pick</div>
        </div>
        <div className={`wait-badge ${waitClass(wait)}`}>
          <div className="wait-value">{wait.toFixed(0)}</div>
          <div className="wait-unit">min wait</div>
        </div>
      </div>
    </div>
  );
}

function ExitCard({ exitGuide }) {
  if (!exitGuide) {
    return null;
  }

  return (
    <div className="smart-card exit-card" id="exit-guidance-card">
      <span className="card-tag best">
        <i className="bi bi-box-arrow-right" aria-hidden="true" /> Recommended
        Exit
      </span>
      <div className="smart-card-header">
        <div>
          <div className="smart-card-title">{exitGuide.message}</div>
          <div className="smart-card-subtitle">
            Based on live congestion score
          </div>
        </div>
      </div>
    </div>
  );
}

export default function HomePage({ bestGate, bestConc, exitGuide, simStatus }) {
  const phase = PHASE_MAP[simStatus?.phase] || PHASE_MAP.idle;

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
      <GateCard bestGate={bestGate} />

      <div className="section-header">
        <span className="section-title">
          <i
            className="bi bi-cup-hot"
            style={{ marginRight: "6px" }}
            aria-hidden="true"
          />
          Food & Drinks
        </span>
      </div>
      <ConcessionCard bestConc={bestConc} />

      <div className="section-header">
        <span className="section-title">
          <i
            className="bi bi-box-arrow-right"
            style={{ marginRight: "6px" }}
            aria-hidden="true"
          />
          Exit Guide
        </span>
      </div>
      <ExitCard exitGuide={exitGuide} />

      {!bestGate && !bestConc && !exitGuide && (
        <div className="empty-state">
          <div className="empty-state-emoji">
            <i className="bi bi-building" aria-hidden="true" />
          </div>
          <h3>Welcome to Stadium OS</h3>
          <p>
            Start simulation from the operations dashboard to see live
            recommendations.
          </p>
        </div>
      )}
    </div>
  );
}

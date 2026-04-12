export default function KpisPage({ kpis }) {
  const hasData = Boolean(kpis?.baseline);

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">KPI Dashboard</h1>
          <p className="page-subtitle">
            Baseline vs optimized operational performance
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
          KPIs will appear after simulation completes
        </div>
      ) : (
        <div className="stats-grid">
          <div className="card stat-card accent-green">
            <div className="card-title">Avg Wait Reduction</div>
            <div className="card-value text-green">
              {kpis.improvements?.avg_wait_reduction_pct || 0}%
            </div>
          </div>
          <div className="card stat-card accent-blue">
            <div className="card-title">P95 Wait Reduction</div>
            <div className="card-value text-blue">
              {kpis.improvements?.p95_wait_reduction_pct || 0}%
            </div>
          </div>
          <div className="card stat-card accent-amber">
            <div className="card-title">Response Speedup</div>
            <div
              className="card-value"
              style={{ color: "var(--accent-amber)" }}
            >
              {kpis.improvements?.response_improvement_factor || "N/A"}
            </div>
          </div>
          <div className="card stat-card accent-red">
            <div className="card-title">Copilot Response</div>
            <div className="card-value text-green">
              {kpis.improvements?.response_latency_copilot_sec || 0}s
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

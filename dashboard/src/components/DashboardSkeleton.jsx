export default function DashboardSkeleton() {
  return (
    <div role="status" aria-live="polite" aria-label="Loading dashboard data">
      <div className="stats-grid" style={{ marginTop: "4px" }}>
        {[0, 1, 2, 3].map((item) => (
          <div key={item} className="card skeleton-card" />
        ))}
      </div>
      <div className="card skeleton-card" style={{ height: "280px" }} />
      <div className="card skeleton-card" style={{ height: "220px", marginTop: "16px" }} />
    </div>
  );
}

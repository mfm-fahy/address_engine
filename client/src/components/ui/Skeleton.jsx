export function SkeletonCard({ lines = 3, height }) {
  return (
    <div className="skeleton-card" style={height ? { height } : undefined}>
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="skeleton-line" style={{ width: `${70 + Math.random() * 30}%` }} />
      ))}
    </div>
  )
}

export function SkeletonTable({ rows = 5, cols = 4 }) {
  return (
    <div className="skeleton-table">
      <div className="skeleton-row skeleton-header">
        {Array.from({ length: cols }).map((_, i) => (
          <div key={i} className="skeleton-cell" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="skeleton-row">
          {Array.from({ length: cols }).map((_, c) => (
            <div key={c} className="skeleton-cell" style={{ width: `${50 + Math.random() * 50}%` }} />
          ))}
        </div>
      ))}
    </div>
  )
}

export function SkeletonGrid({ count = 6 }) {
  return (
    <div className="skeleton-grid">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="skeleton-card-lg">
          <div className="skeleton-line" style={{ width: '40%' }} />
          <div className="skeleton-line" style={{ width: '60%' }} />
          <div className="skeleton-line" style={{ width: '30%' }} />
        </div>
      ))}
    </div>
  )
}

export function SkeletonStats({ count = 4 }) {
  return (
    <div className="skeleton-stats">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="skeleton-stat">
          <div className="skeleton-line" style={{ width: '50%' }} />
          <div className="skeleton-line skeleton-value-line" style={{ width: '70%' }} />
          <div className="skeleton-line" style={{ width: '40%' }} />
        </div>
      ))}
    </div>
  )
}

export function SkeletonChart() {
  return (
    <div className="skeleton-chart">
      <div className="skeleton-line" style={{ width: '30%', marginBottom: 16 }} />
      <div className="skeleton-chart-area" />
      <div className="skeleton-axes">
        <div className="skeleton-line" style={{ width: '80%' }} />
        <div className="skeleton-line" style={{ width: '60%' }} />
      </div>
    </div>
  )
}

export function SkeletonDetail() {
  return (
    <div className="skeleton-detail">
      <div className="skeleton-line" style={{ width: '20%', marginBottom: 8 }} />
      <div className="skeleton-line" style={{ width: '50%', marginBottom: 24 }} />
      <div className="skeleton-detail-grid">
        <div className="skeleton-card-lg">
          <div className="skeleton-line" style={{ width: '40%' }} />
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="skeleton-line" style={{ width: `${50 + Math.random() * 40}%` }} />
          ))}
        </div>
        <div className="skeleton-card-lg">
          <div className="skeleton-line" style={{ width: '40%' }} />
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="skeleton-line" style={{ width: `${50 + Math.random() * 40}%` }} />
          ))}
        </div>
      </div>
    </div>
  )
}

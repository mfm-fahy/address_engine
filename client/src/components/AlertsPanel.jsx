import { AlertTriangle, MessageCircle } from 'lucide-react'

export default function AlertsPanel({ alerts }) {
  if (!alerts || alerts.length === 0) return null

  return (
    <div className="alerts-panel" style={{ border: '1px solid rgba(239, 68, 68, 0.3)' }}>
      <h3 style={{ color: 'var(--danger)' }}>
        <AlertTriangle size={14} style={{ marginRight: 6 }} />
        Alerts ({alerts.length})
      </h3>
      {alerts.slice(0, 10).map((a, i) => (
        <div key={i} className={`alert-item ${a.severity}`}>
          {a.type === 'negative_comment' ? (
            <MessageCircle size={16} className="alert-icon" style={{ color: 'var(--danger)' }} />
          ) : (
            <AlertTriangle size={16} className="alert-icon" style={{ color: a.severity === 'warning' ? 'var(--warning)' : 'var(--danger)' }} />
          )}
          <div>
            <div className="alert-text">{a.message}</div>
            <div className="alert-time">{new Date(a.created_at).toLocaleString()}</div>
          </div>
        </div>
      ))}
    </div>
  )
}

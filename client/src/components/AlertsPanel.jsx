import { AlertTriangle, MessageCircle, X } from 'lucide-react'

export default function AlertsPanel({ alerts, onDismiss }) {
  if (!alerts || alerts.length === 0) return null

  return (
    <div className="alerts-panel-section" style={{ border: '1px solid rgba(239, 68, 68, 0.25)' }}>
      <h3 style={{ color: 'var(--danger)' }}>
        <AlertTriangle size={14} />
        Alerts ({alerts.length})
      </h3>
      {alerts.map((a, i) => (
        <div key={i} className={`alert-item ${a.severity === 'warning' ? 'warning' : 'error'}`}>
          {a.type === 'negative_comment' ? (
            <MessageCircle size={16} className="alert-icon" style={{ color: 'var(--danger)' }} />
          ) : (
            <AlertTriangle size={16} className="alert-icon" style={{ color: a.severity === 'warning' ? 'var(--warning)' : 'var(--danger)' }} />
          )}
          <div style={{ flex: 1 }}>
            <div className="alert-text">{a.message}</div>
            <div className="alert-time">{new Date(a.created_at).toLocaleString()}</div>
          </div>
        </div>
      ))}
    </div>
  )
}

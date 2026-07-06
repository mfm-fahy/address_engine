import { Inbox } from 'lucide-react'

export default function EmptyState({
  icon: Icon = Inbox,
  title = 'No data found',
  description = '',
  action,
  compact = false,
}) {
  return (
    <div className={`empty-state ${compact ? 'empty-state-compact' : ''}`}>
      <div className="empty-state-icon">
        <Icon size={compact ? 28 : 40} />
      </div>
      <h3 className="empty-state-title">{title}</h3>
      {description && <p className="empty-state-desc">{description}</p>}
      {action && <div className="empty-state-action">{action}</div>}
    </div>
  )
}

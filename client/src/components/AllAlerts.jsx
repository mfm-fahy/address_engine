import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AlertTriangle, MessageCircle, ShieldAlert, Search,
  ArrowLeft, X, Filter, Inbox
} from 'lucide-react'
import { fetchAlerts } from '../api'
import { EmptyState } from './ui'

const SEVERITY_OPTIONS = [
  { value: 'warning', label: 'Warning' },
  { value: 'error', label: 'Error' },
]

const TYPE_OPTIONS = [
  { value: 'negative_comment', label: 'Negative Comment' },
  { value: 'bad_command', label: 'Bad Command' },
]

export default function AllAlerts() {
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [severityFilter, setSeverityFilter] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    fetchAlerts()
      .then(res => setAlerts(res.alerts || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const filtered = useMemo(() => {
    let result = [...alerts]
    if (search) {
      const q = search.toLowerCase()
      result = result.filter(a =>
        a.message?.toLowerCase().includes(q) ||
        a.customer_id?.toLowerCase().includes(q)
      )
    }
    if (severityFilter) result = result.filter(a => a.severity === severityFilter)
    if (typeFilter) result = result.filter(a => a.type === typeFilter)
    return result
  }, [alerts, search, severityFilter, typeFilter])

  const stats = useMemo(() => ({
    total: alerts.length,
    warnings: alerts.filter(a => a.severity === 'warning').length,
    errors: alerts.filter(a => a.severity === 'error').length,
    negativeComments: alerts.filter(a => a.type === 'negative_comment').length,
    badCommands: alerts.filter(a => a.type === 'bad_command').length,
  }), [alerts])

  const getAlertIcon = (a) => {
    if (a.type === 'bad_command') return <ShieldAlert size={16} style={{ color: 'var(--danger)' }} />
    if (a.type === 'negative_comment') return <MessageCircle size={16} style={{ color: 'var(--danger)' }} />
    return <AlertTriangle size={16} style={{ color: a.severity === 'warning' ? 'var(--warning)' : 'var(--danger)' }} />
  }

  return (
    <div>
      <button className="back-btn" onClick={() => navigate('/')}>
        <ArrowLeft size={16} /> Back to Dashboard
      </button>

      <div className="page-toolbar">
        <div className="page-toolbar-left">
          <h1 className="page-title">All Alerts</h1>
          <span className="page-subtitle">{alerts.length} total alerts</span>
        </div>
      </div>

      <div className="stats-grid">
        <div className="stat-card stat-card-accent danger">
          <div className="stat-icon stat-icon-bg-danger"><AlertTriangle size={20} /></div>
          <div className="stat-body">
            <div className="stat-label">Total Alerts</div>
            <div className="stat-value">{stats.total}</div>
          </div>
        </div>
        <div className="stat-card stat-card-accent warning">
          <div className="stat-icon stat-icon-bg-warning"><MessageCircle size={20} /></div>
          <div className="stat-body">
            <div className="stat-label">Negative Comments</div>
            <div className="stat-value">{stats.negativeComments}</div>
          </div>
        </div>
        <div className="stat-card stat-card-accent primary">
          <div className="stat-icon stat-icon-bg-primary"><ShieldAlert size={20} /></div>
          <div className="stat-body">
            <div className="stat-label">Bad Commands</div>
            <div className="stat-value">{stats.badCommands}</div>
          </div>
        </div>
      </div>

      <div className="filter-system">
        <div className="filter-bar">
          <div className="filter-search-wrapper">
            <Search size={14} className="filter-search-icon" />
            <input
              type="text"
              className="filter-search-input"
              placeholder="Search alerts by message or customer ID..."
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
            {search && (
              <button className="filter-search-clear" onClick={() => setSearch('')}>
                <X size={14} />
              </button>
            )}
          </div>
          <div className="filter-actions">
            <select
              className="filter-select"
              value={severityFilter}
              onChange={e => setSeverityFilter(e.target.value)}
            >
              <option value="">All Severities</option>
              {SEVERITY_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
            <select
              className="filter-select"
              value={typeFilter}
              onChange={e => setTypeFilter(e.target.value)}
            >
              <option value="">All Types</option>
              {TYPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
        </div>
      </div>

      <div className="results-meta">
        <span>{filtered.length} of {alerts.length} alerts</span>
        {(search || severityFilter || typeFilter) && (
          <button className="btn btn-ghost btn-sm" onClick={() => { setSearch(''); setSeverityFilter(''); setTypeFilter('') }}>
            <X size={12} /> Clear filters
          </button>
        )}
      </div>

      {loading ? (
        <div className="skeleton-table">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="skeleton-row" style={{ gridTemplateColumns: '1fr 2fr 1fr 1fr' }}>
              <div className="skeleton-cell" />
              <div className="skeleton-cell" />
              <div className="skeleton-cell" />
              <div className="skeleton-cell" />
            </div>
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={Inbox}
          title={alerts.length === 0 ? 'No alerts yet' : 'No matching alerts'}
          description={alerts.length === 0
            ? 'Alerts will appear here when negative comments or bad commands are detected.'
            : 'Try adjusting your search or filters.'}
          action={alerts.length > 0 ? (
            <button className="btn btn-secondary btn-sm" onClick={() => { setSearch(''); setSeverityFilter(''); setTypeFilter('') }}>
              <X size={12} /> Clear all filters
            </button>
          ) : null}
        />
      ) : (
        <div className="customers-list">
          <div className="list-header" style={{ gridTemplateColumns: '0.5fr 1fr 1.5fr 1fr 0.8fr' }}>
            <span>Severity</span>
            <span>Type</span>
            <span>Message</span>
            <span>Customer</span>
            <span>Date</span>
          </div>
          {filtered.map((a, i) => (
            <div
              key={i}
              className="list-row"
              style={{ gridTemplateColumns: '0.5fr 1fr 1.5fr 1fr 0.8fr', cursor: a.customer_id ? 'pointer' : 'default' }}
              onClick={() => a.customer_id && navigate(`/customer/${a.customer_id}`)}
              role={a.customer_id ? 'button' : undefined}
              tabIndex={a.customer_id ? 0 : undefined}
              onKeyDown={a.customer_id ? (e) => e.key === 'Enter' && navigate(`/customer/${a.customer_id}`) : undefined}
            >
              <span>
                <span className={`pill ${a.severity === 'warning' ? 'pill-warning' : 'pill-danger'}`}>
                  {a.severity}
                </span>
              </span>
              <span>
                <span className={`pill ${a.type === 'bad_command' ? 'pill-danger' : 'pill-warning'}`}>
                  {a.type === 'bad_command' ? 'Bad Command' : a.type === 'negative_comment' ? 'Negative Comment' : a.type}
                </span>
              </span>
              <span style={{ fontSize: 13, lineHeight: 1.4 }}>{a.message}</span>
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                {a.customer_id ? a.customer_id : '-'}
              </span>
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                {new Date(a.created_at).toLocaleDateString()}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

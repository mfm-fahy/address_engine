import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ShoppingCart, MessageCircle, AlertTriangle, TrendingUp,
  RefreshCw, Search, Users, IndianRupee, X,
  Instagram, Globe, CreditCard,
  Package, PieChart, SlidersHorizontal, LayoutGrid, List
} from 'lucide-react'
import { fetchCustomers, fetchAlerts, triggerRefreshAll } from '../api'
import AlertsPanel from './AlertsPanel'

const SOURCES = [
  { key: 'instaxbot', label: 'Instagram', icon: Instagram, color: '#e1306c' },
  { key: 'gowhats', label: 'WhatsApp', icon: MessageCircle, color: '#25d366' },
  { key: 'f3', label: 'F3', icon: Globe, color: '#a855f7' },
  { key: 'bill', label: 'Billzzy', icon: CreditCard, color: '#3b82f6' },
]

export default function Dashboard() {
  const [customers, setCustomers] = useState([])
  const [alerts, setAlerts] = useState([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [showFilters, setShowFilters] = useState(false)
  const [viewMode, setViewMode] = useState('grid')
  const navigate = useNavigate()

  const [filters, setFilters] = useState({
    sources: [],
    hasOrders: false,
    hasBills: false,
    hasAlerts: false,
    sortBy: 'recent',
    minSpent: '',
    maxSpent: '',
  })

  const loadData = async () => {
    try {
      const [cRes, aRes] = await Promise.all([fetchCustomers(), fetchAlerts()])
      setCustomers(cRes.customers || [])
      setAlerts(aRes.alerts || [])
    } catch (e) {
      console.error('Failed to load data', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadData() }, [])

  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      await triggerRefreshAll()
      await loadData()
    } catch (e) {
      console.error('Refresh failed', e)
    } finally {
      setRefreshing(false)
    }
  }

  const toggleSource = (key) => {
    setFilters(f => ({
      ...f,
      sources: f.sources.includes(key)
        ? f.sources.filter(s => s !== key)
        : [...f.sources, key]
    }))
  }

  const activeFilterCount = useMemo(() => {
    let count = filters.sources.length
    if (filters.hasOrders) count++
    if (filters.hasBills) count++
    if (filters.hasAlerts) count++
    if (filters.minSpent || filters.maxSpent) count++
    if (filters.sortBy !== 'recent') count++
    return count
  }, [filters])

  const filtered = useMemo(() => {
    let result = [...customers]

    if (search) {
      const q = search.toLowerCase()
      result = result.filter(c =>
        c.name?.toLowerCase().includes(q) ||
        c.phone?.includes(q) ||
        c.customer_id?.toLowerCase().includes(q) ||
        c.email?.toLowerCase().includes(q)
      )
    }

    if (filters.sources.length > 0) {
      result = result.filter(c =>
        filters.sources.some(s => c.sources?.includes(s))
      )
    }

    if (filters.hasOrders) result = result.filter(c => c.total_orders > 0)
    if (filters.hasBills) result = result.filter(c => c.total_bills > 0)
    if (filters.hasAlerts) {
      const alertCustomerIds = new Set(alerts.map(a => a.customer_id))
      result = result.filter(c => alertCustomerIds.has(c.customer_id))
    }

    if (filters.minSpent) result = result.filter(c => (c.total_spent || 0) >= Number(filters.minSpent))
    if (filters.maxSpent) result = result.filter(c => (c.total_spent || 0) <= Number(filters.maxSpent))

    switch (filters.sortBy) {
      case 'name':
        result.sort((a, b) => (a.name || '').localeCompare(b.name || ''))
        break
      case 'spent':
        result.sort((a, b) => (b.total_spent || 0) - (a.total_spent || 0))
        break
      case 'orders':
        result.sort((a, b) => (b.total_orders || 0) - (a.total_orders || 0))
        break
      case 'recent':
      default:
        result.sort((a, b) => new Date(b.last_activity || 0) - new Date(a.last_activity || 0))
        break
    }

    return result
  }, [customers, search, filters, alerts])

  const stats = useMemo(() => ({
    total: customers.length,
    withOrders: customers.filter(c => c.total_orders > 0).length,
    withBills: customers.filter(c => c.total_bills > 0).length,
    negativeAlerts: alerts.filter(a => a.severity === 'warning').length,
    totalSpent: customers.reduce((s, c) => s + (c.total_spent || 0), 0),
    multiSource: customers.filter(c => (c.sources?.length || 0) > 1).length,
  }), [customers, alerts])

  const clearFilters = () => {
    setFilters({
      sources: [], hasOrders: false, hasBills: false, hasAlerts: false,
      sortBy: 'recent', minSpent: '', maxSpent: '',
    })
    setSearch('')
  }

  if (loading) return (
    <div>
      <div className="stats-grid">
        {[1,2,3,4].map(i => <div key={i} className="stat-card"><div className="skeleton-value" /></div>)}
      </div>
      <div className="customers-grid">
        {[1,2,3,4,5,6].map(i => <div key={i} className="customer-card"><div className="skeleton-card" /></div>)}
      </div>
    </div>
  )

  return (
    <div>
      <div className="page-toolbar">
        <div className="page-toolbar-left">
          <span className="header-subtitle">{customers.length} customers tracked</span>
        </div>
        <div className="header-actions">
          <button
            className={`btn ${activeFilterCount > 0 ? 'btn-active' : 'btn-outline'}`}
            onClick={() => setShowFilters(!showFilters)}
          >
            <SlidersHorizontal size={14} />
            Filters
            {activeFilterCount > 0 && <span className="filter-badge">{activeFilterCount}</span>}
          </button>
          <button className="btn btn-primary" onClick={handleRefresh} disabled={refreshing}>
            <RefreshCw size={14} className={refreshing ? 'spin' : ''} />
            {refreshing ? 'Syncing...' : 'Sync All Data'}
          </button>
        </div>
      </div>

      <div className="stats-grid">
        <div className="stat-card stat-accent">
          <div className="stat-icon"><Users size={20} /></div>
          <div className="stat-body">
            <div className="label">Total Customers</div>
            <div className="value">{stats.total}</div>
            <div className="sub">{stats.withOrders} with orders &middot; {stats.withBills} with bills</div>
          </div>
        </div>
        <div className="stat-card stat-accent">
          <div className="stat-icon" style={{ color: 'var(--success)' }}><IndianRupee size={20} /></div>
          <div className="stat-body">
            <div className="label">Total Revenue</div>
            <div className="value">₹{stats.totalSpent.toLocaleString()}</div>
            <div className="sub">{stats.multiSource} customers on multiple platforms</div>
          </div>
        </div>
        <div className="stat-card stat-accent">
          <div className="stat-icon" style={{ color: stats.negativeAlerts > 0 ? 'var(--danger)' : 'var(--success)' }}>
            <AlertTriangle size={20} />
          </div>
          <div className="stat-body">
            <div className="label">Alerts</div>
            <div className="value" style={{ color: stats.negativeAlerts > 0 ? 'var(--danger)' : 'var(--success)' }}>
              {stats.negativeAlerts}
            </div>
            <div className="sub">{stats.negativeAlerts > 0 ? 'Negative reviews / comments' : 'All clear'}</div>
          </div>
        </div>
        <div className="stat-card stat-accent">
          <div className="stat-icon" style={{ color: 'var(--warning)' }}><PieChart size={20} /></div>
          <div className="stat-body">
            <div className="label">Platforms Synced</div>
            <div className="value">4</div>
            <div className="sub">GoWhats, InstaXbot, F3, Billzzy</div>
          </div>
        </div>
      </div>

      <div className="search-filter-bar">
        <div className="search-wrapper">
          <Search size={16} className="search-icon" />
          <input
            type="text"
            placeholder="Search by name, phone, ID, or email..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          {search && <X size={16} className="search-clear" onClick={() => setSearch('')} />}
        </div>

        <div className="view-toggle">
          <button
            className={`btn btn-sm ${viewMode === 'grid' ? 'btn-primary' : 'btn-outline'}`}
            onClick={() => setViewMode('grid')}
          ><LayoutGrid size={14} /></button>
          <button
            className={`btn btn-sm ${viewMode === 'list' ? 'btn-primary' : 'btn-outline'}`}
            onClick={() => setViewMode('list')}
          ><List size={14} /></button>
        </div>
      </div>

      {showFilters && (
        <div className="filter-panel">
          <div className="filter-section">
            <div className="filter-label">Source</div>
            <div className="filter-chips">
              {SOURCES.map(s => {
                const active = filters.sources.includes(s.key)
                return (
                  <button
                    key={s.key}
                    className={`chip ${active ? 'active' : ''}`}
                    style={active ? { borderColor: s.color, color: s.color, background: `${s.color}15` } : {}}
                    onClick={() => toggleSource(s.key)}
                  >
                    <s.icon size={12} />
                    {s.label}
                  </button>
                )
              })}
            </div>
          </div>

          <div className="filter-section">
            <div className="filter-label">Has</div>
            <div className="filter-chips">
              {[
                { key: 'hasOrders', label: 'Orders', icon: Package },
                { key: 'hasBills', label: 'Bills', icon: CreditCard },
                { key: 'hasAlerts', label: 'Alerts', icon: AlertTriangle },
              ].map(f => (
                <button
                  key={f.key}
                  className={`chip ${filters[f.key] ? 'active' : ''}`}
                  onClick={() => setFilters(fs => ({ ...fs, [f.key]: !fs[f.key] }))}
                >
                  <f.icon size={12} />
                  {f.label}
                </button>
              ))}
            </div>
          </div>

          <div className="filter-section">
            <div className="filter-label">Spent Range (₹)</div>
            <div className="filter-range">
              <input
                type="number"
                placeholder="Min"
                value={filters.minSpent}
                onChange={e => setFilters(fs => ({ ...fs, minSpent: e.target.value }))}
              />
              <span>to</span>
              <input
                type="number"
                placeholder="Max"
                value={filters.maxSpent}
                onChange={e => setFilters(fs => ({ ...fs, maxSpent: e.target.value }))}
              />
            </div>
          </div>

          <div className="filter-section">
            <div className="filter-label">Sort by</div>
            <select
              value={filters.sortBy}
              onChange={e => setFilters(fs => ({ ...fs, sortBy: e.target.value }))}
              className="filter-select"
            >
              <option value="recent">Recent Activity</option>
              <option value="name">Name A-Z</option>
              <option value="spent">Highest Spent</option>
              <option value="orders">Most Orders</option>
            </select>
          </div>

          {activeFilterCount > 0 && (
            <button className="btn btn-sm btn-outline" onClick={clearFilters} style={{ alignSelf: 'flex-start' }}>
              <X size={12} /> Clear all filters
            </button>
          )}
        </div>
      )}

      {activeFilterCount > 0 && search && (
        <div className="active-filters">
          {search && <span className="filter-chip">Search: "{search}" <X size={12} onClick={() => setSearch('')} /></span>}
          {filters.sources.map(s => (
            <span key={s} className="filter-chip">
              {SOURCES.find(sr => sr.key === s)?.label || s}
              <X size={12} onClick={() => toggleSource(s)} />
            </span>
          ))}
          {filters.hasOrders && <span className="filter-chip">Has orders <X size={12} onClick={() => setFilters(fs => ({ ...fs, hasOrders: false }))} /></span>}
          {filters.hasBills && <span className="filter-chip">Has bills <X size={12} onClick={() => setFilters(fs => ({ ...fs, hasBills: false }))} /></span>}
          {filters.hasAlerts && <span className="filter-chip">Has alerts <X size={12} onClick={() => setFilters(fs => ({ ...fs, hasAlerts: false }))} /></span>}
        </div>
      )}

      {alerts.filter(a => a.severity === 'warning').length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <AlertsPanel alerts={alerts.filter(a => a.severity === 'warning')} />
        </div>
      )}

      <div className="results-meta">
        <span>{filtered.length} of {customers.length} customers</span>
        {filtered.length > 0 && (
          <span className="results-spent">
            Total: ₹{filtered.reduce((s, c) => s + (c.total_spent || 0), 0).toLocaleString()}
          </span>
        )}
      </div>

      {filtered.length === 0 ? (
        <div className="empty-state">
          <TrendingUp size={40} />
          <h3>{customers.length === 0 ? 'No customers yet' : 'No matching customers'}</h3>
          <p>
            {customers.length === 0
              ? 'Click "Sync All Data" to fetch from all platforms and build customer profiles.'
              : 'Try adjusting your filters or search terms.'}
          </p>
          {customers.length > 0 && <button className="btn btn-outline" onClick={clearFilters}>Clear all filters</button>}
        </div>
      ) : viewMode === 'grid' ? (
        <div className="customers-grid">
          {filtered.map(c => (
            <div key={c.customer_id} className="customer-card" onClick={() => navigate(`/customer/${c.customer_id}`)}>
              <div className="card-top">
                <div className="name">{c.name || 'Unknown'}</div>
                {c.total_spent >= 50000 && <span className="vip-badge">VIP</span>}
              </div>
              <div className="phone">{c.phone ? `+91 ${c.phone}` : 'No phone'}</div>
              <div className="badges">
                {c.sources?.includes('instaxbot') && <span className="badge badge-insta">Instagram</span>}
                {c.sources?.includes('gowhats') && <span className="badge badge-whats">WhatsApp</span>}
                {c.sources?.includes('f3') && <span className="badge badge-f3">F3</span>}
                {c.sources?.includes('bill') && <span className="badge badge-bill">Bill</span>}
                {c.username && <span className="badge badge-insta">@{c.username}</span>}
              </div>
              <div className="stats-row">
                <span><ShoppingCart size={12} /> {c.total_orders} orders</span>
                <span><TrendingUp size={12} /> ₹{c.total_spent?.toLocaleString()}</span>
                <span><MessageCircle size={12} /> {c.comment_count || 0}</span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="customers-list">
          <div className="list-header">
            <span>Customer</span>
            <span>Phone</span>
            <span>Sources</span>
            <span>Orders</span>
            <span>Spent</span>
          </div>
          {filtered.map(c => (
            <div key={c.customer_id} className="list-row" onClick={() => navigate(`/customer/${c.customer_id}`)}>
              <span className="list-name">
                {c.name || 'Unknown'}
                <span className="list-id">{c.customer_id}</span>
              </span>
              <span className="list-phone">{c.phone ? `+91 ${c.phone}` : '-'}</span>
              <span className="list-sources">
                {c.sources?.includes('instaxbot') && <span className="badge badge-insta">IG</span>}
                {c.sources?.includes('gowhats') && <span className="badge badge-whats">WA</span>}
                {c.sources?.includes('f3') && <span className="badge badge-f3">F3</span>}
                {c.sources?.includes('bill') && <span className="badge badge-bill">BL</span>}
              </span>
              <span>{c.total_orders}</span>
              <span className="list-spent">₹{c.total_spent?.toLocaleString()}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

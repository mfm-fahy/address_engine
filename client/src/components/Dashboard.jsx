import { useState, useEffect, useMemo, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ShoppingCart, MessageCircle, AlertTriangle, TrendingUp,
  RefreshCw, Search, Users, X,
  Instagram, Globe, CreditCard,
  Package, SlidersHorizontal, LayoutGrid, List, Inbox, UserCheck
} from 'lucide-react'
import { fetchCustomers, fetchAlerts, triggerRefreshAll } from '../api'
import { FilterPanel, SkeletonStats, SkeletonGrid, SkeletonTable, EmptyState, useToast } from './ui'

const SOURCES = [
  { key: 'instaxbot', label: 'Instaxbot', icon: Instagram, color: '#e1306c' },
  { key: 'gowhats', label: 'GoWhats', icon: MessageCircle, color: '#25d366' },
  { key: 'f3', label: 'F3', icon: Globe, color: '#a855f7' },
  { key: 'bill', label: 'Billzy', icon: CreditCard, color: '#3b82f6' },
]

export default function Dashboard() {
  const [customers, setCustomers] = useState([])
  const [alerts, setAlerts] = useState([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [viewMode, setViewMode] = useState('grid')
  const navigate = useNavigate()
  const toast = useToast()

  const [filters, setFilters] = useState({
    sources: [],
    hasOrders: false,
    hasBills: false,
    hasAlerts: false,
    sortBy: 'recent',
  })

  const [spendRange, setSpendRange] = useState({ minSpent: '', maxSpent: '' })

  const loadData = useCallback(async () => {
    try {
      const [cRes, aRes] = await Promise.all([fetchCustomers(), fetchAlerts()])
      setCustomers(cRes.customers || [])
      setAlerts(aRes.alerts || [])
    } catch (e) {
      console.error('Failed to load data', e)
      toast('Failed to load dashboard data', 'error')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => { loadData() }, [loadData])

  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      await triggerRefreshAll()
      await loadData()
    } catch (e) {
      console.error('Refresh failed', e)
      toast('Sync failed. Please try again.', 'error')
    } finally {
      setRefreshing(false)
    }
  }

  const toggleSource = useCallback((key) => {
    setFilters(f => ({
      ...f,
      sources: f.sources.includes(key)
        ? f.sources.filter(s => s !== key)
        : [...f.sources, key]
    }))
  }, [])

  const handleFilterChange = useCallback((key, value) => {
    setFilters(f => ({ ...f, [key]: value }))
  }, [])

  const handleRangeChange = useCallback((key, value) => {
    setSpendRange(r => ({ ...r, [key]: value }))
  }, [])

  const clearFilters = useCallback(() => {
    setFilters({ sources: [], hasOrders: false, hasBills: false, hasAlerts: false, sortBy: 'recent' })
    setSpendRange({ minSpent: '', maxSpent: '' })
    setSearch('')
  }, [])

  const activeFilterCount = useMemo(() => {
    let count = filters.sources.length
    if (filters.hasOrders) count++
    if (filters.hasBills) count++
    if (filters.hasAlerts) count++
    if (filters.sortBy !== 'recent') count++
    if (spendRange.minSpent || spendRange.maxSpent) count++
    return count
  }, [filters, spendRange])

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

    if (spendRange.minSpent) result = result.filter(c => (c.total_spent || 0) >= Number(spendRange.minSpent))
    if (spendRange.maxSpent) result = result.filter(c => (c.total_spent || 0) <= Number(spendRange.maxSpent))

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
      default:
        result.sort((a, b) => new Date(b.last_activity || 0) - new Date(a.last_activity || 0))
        break
    }

    return result
  }, [customers, search, filters, spendRange, alerts])

  const stats = useMemo(() => ({
    total: customers.length,
    withOrders: customers.filter(c => c.total_orders > 0).length,
    withBills: customers.filter(c => c.total_bills > 0).length,
    negativeAlerts: alerts.filter(a => a.severity === 'warning').length,
    totalSpent: customers.reduce((s, c) => s + (isFinite(c.total_spent) ? c.total_spent : 0), 0),
    multiSource: customers.filter(c => (c.sources?.length || 0) > 1).length,
  }), [customers, alerts])

  const filterConfig = [
    {
      label: 'Source',
      key: 'sources',
      type: 'chips',
      options: SOURCES.map(s => ({ value: s.key, label: s.label, icon: s.icon, color: s.color })),
    },
    {
      label: 'Has',
      type: 'toggle',
      options: [
        { value: 'hasOrders', label: 'Orders' },
        { value: 'hasBills', label: 'Bills' },
        { value: 'hasAlerts', label: 'Alerts' },
      ],
    },
    {
      label: 'Spent Range (₹)',
      type: 'range',
      key: 'spend',
      minKey: 'minSpent',
      maxKey: 'maxSpent',
      minPlaceholder: 'Min',
      maxPlaceholder: 'Max',
    },
    {
      label: 'Sort by',
      key: 'sortBy',
      type: 'select',
      options: [
        { value: 'recent', label: 'Recent Activity' },
        { value: 'name', label: 'Name A-Z' },
        { value: 'spent', label: 'Highest Spent' },
        { value: 'orders', label: 'Most Orders' },
      ],
    },
  ]

  if (loading) {
    return (
      <div>
        <div className="page-toolbar">
          <div className="page-toolbar-left">
            <h1 className="page-title">Dashboard</h1>
          </div>
        </div>
        <SkeletonStats />
        <SkeletonGrid count={6} />
      </div>
    )
  }

  return (
    <div>
      <div className="page-toolbar">
        <div className="page-toolbar-left">
          <h1 className="page-title">Dashboard</h1>
          <span className="page-subtitle">{customers.length} customers tracked</span>
        </div>
        <div className="header-actions">
          <button
            className="btn btn-primary"
            onClick={handleRefresh}
            disabled={refreshing}
          >
            <RefreshCw size={14} className={refreshing ? 'spin' : ''} />
            {refreshing ? 'Syncing...' : 'Sync All Data'}
          </button>
        </div>
      </div>

      <div className="stats-grid">
        <div className="stat-card stat-card-accent primary">
          <div className="stat-icon stat-icon-bg-primary"><Users size={20} /></div>
          <div className="stat-body">
            <div className="stat-label">Total Customers</div>
            <div className="stat-value">{stats.total}</div>
            <div className="stat-sub">{stats.withOrders} with orders &middot; {stats.withBills} with bills</div>
          </div>
        </div>
        <div
          className="stat-card stat-card-accent danger"
          style={{ cursor: 'pointer' }}
          onClick={() => navigate('/alerts')}
          role="button"
          tabIndex={0}
          onKeyDown={e => e.key === 'Enter' && navigate('/alerts')}
        >
          <div className="stat-icon stat-icon-bg-danger"><AlertTriangle size={20} /></div>
          <div className="stat-body">
            <div className="stat-label">Alerts</div>
            <div className="stat-value" style={{ color: stats.negativeAlerts > 0 ? 'var(--danger)' : 'var(--success)' }}>
              {stats.negativeAlerts}
            </div>
            <div className="stat-sub">{stats.negativeAlerts > 0 ? 'Click to view all' : 'All clear'}</div>
          </div>
        </div>
        <div className="stat-card stat-card-accent warning">
          <div className="stat-icon stat-icon-bg-warning"><Package size={20} /></div>
          <div className="stat-body">
            <div className="stat-label">Platforms Synced</div>
            <div className="stat-value">4</div>
            <div className="stat-sub">Instaxbot &middot; GoWhats &middot; F3 &middot; Billzy</div>
          </div>
        </div>
      </div>

      <FilterPanel
        search={search}
        onSearchChange={setSearch}
        searchPlaceholder="Search by name, phone, ID, or email..."
        filters={{ ...filters, ...spendRange }}
        onFilterChange={(key, value) => {
          if (key === 'minSpent' || key === 'maxSpent') {
            handleRangeChange(key, value)
          } else {
            handleFilterChange(key, value)
          }
        }}
        filterConfig={filterConfig}
        activeFilterCount={activeFilterCount}
        onClearAll={clearFilters}
      />

      <div className="results-meta">
        <span>{filtered.length} of {customers.length} customers</span>
        <div className="view-toggle">
            <button
              className={`btn btn-sm ${viewMode === 'grid' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setViewMode('grid')}
              aria-label="Grid view"
            ><LayoutGrid size={14} /></button>
            <button
              className={`btn btn-sm ${viewMode === 'list' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setViewMode('list')}
              aria-label="List view"
            ><List size={14} /></button>
        </div>
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          icon={customers.length === 0 ? Inbox : Search}
          title={customers.length === 0 ? 'No customers yet' : 'No matching customers'}
          description={customers.length === 0
            ? 'Click "Sync All Data" to fetch from all platforms and build customer profiles.'
            : 'Try adjusting your filters or search terms.'}
          action={customers.length > 0 ? (
            <button className="btn btn-secondary btn-sm" onClick={clearFilters}>
              <X size={12} /> Clear all filters
            </button>
          ) : (
            <button className="btn btn-primary btn-sm" onClick={handleRefresh}>
              <RefreshCw size={12} /> Sync All Data
            </button>
          )}
        />
      ) : viewMode === 'grid' ? (
        <div className="customers-grid">
          {filtered.map(c => (
            <div
              key={c.customer_id}
              className="customer-card"
              onClick={() => navigate(`/customer/${c.customer_id}`)}
              role="button"
              tabIndex={0}
              aria-label={`View customer ${c.name || 'Unknown'}`}
              onKeyDown={e => e.key === 'Enter' && navigate(`/customer/${c.customer_id}`)}
            >
              <div className="card-top">
                <div className="name">{c.name || 'Unknown'}</div>
                {c.total_spent >= 50000 && <span className="badge badge-vip">VIP</span>}
              </div>
              <div className="phone">{c.phone ? `+91 ${c.phone}` : 'No phone'}</div>
              <div className="badges">
                {c.sources?.includes('instaxbot') && <span className="badge badge-insta">Instaxbot</span>}
                {c.sources?.includes('gowhats') && <span className="badge badge-whats">GoWhats</span>}
                {c.sources?.includes('f3') && <span className="badge badge-f3">F3</span>}
                {c.sources?.includes('bill') && <span className="badge badge-bill">Billzy</span>}
                {c.username && <span className="badge badge-default">@{c.username}</span>}
              </div>
              <div className="stats-row">
                <span><ShoppingCart size={12} /> {c.total_orders} orders</span>
                <span><TrendingUp size={12} /> ₹{isFinite(c.total_spent) ? c.total_spent.toLocaleString() : 0}</span>
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
            <div
              key={c.customer_id}
              className="list-row"
              onClick={() => navigate(`/customer/${c.customer_id}`)}
              role="button"
              tabIndex={0}
              onKeyDown={e => e.key === 'Enter' && navigate(`/customer/${c.customer_id}`)}
            >
              <span className="list-name">
                {c.name || 'Unknown'}
                <span className="list-id">{c.customer_id}</span>
              </span>
              <span className="list-phone">{c.phone ? `+91 ${c.phone}` : '-'}</span>
              <span className="list-sources">
                {c.sources?.includes('instaxbot') && <span className="badge badge-insta">IG</span>}
                {c.sources?.includes('gowhats') && <span className="badge badge-whats">GW</span>}
                {c.sources?.includes('f3') && <span className="badge badge-f3">F3</span>}
                {c.sources?.includes('bill') && <span className="badge badge-bill">BZ</span>}
              </span>
              <span>{c.total_orders}</span>
              <span className="list-spent">₹{isFinite(c.total_spent) ? c.total_spent.toLocaleString() : 0}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

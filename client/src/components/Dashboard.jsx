import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ShoppingCart, MessageCircle, AlertTriangle, TrendingUp,
  RefreshCw, Search, Users, X,
  Instagram, Globe, CreditCard,
  Package, LayoutGrid, List, Inbox
} from 'lucide-react'
import { List as VList } from 'react-window'
import { fetchCustomers, fetchAlerts, triggerRefreshAll } from '../api'
import { FilterPanel, SkeletonStats, SkeletonGrid, EmptyState, useToast } from './ui'

const SOURCES = [
  { key: 'instaxbot', label: 'Instaxbot', icon: Instagram, color: '#e1306c' },
  { key: 'gowhats', label: 'GoWhats', icon: MessageCircle, color: '#25d366' },
  { key: 'f3', label: 'F3', icon: Globe, color: '#a855f7' },
  { key: 'bill', label: 'Billzy', icon: CreditCard, color: '#3b82f6' },
]

const PAGE_SIZE = 50000
const CARD_HEIGHT_GRID = 160
const ROW_HEIGHT_LIST = 56

function GridRow({ index, style, data }) {
  const { items, cols, navigate } = data
  const rowItems = items.slice(index * cols, index * cols + cols)
  return (
    <div style={{ ...style, display: 'grid', gridTemplateColumns: `repeat(${cols}, 1fr)`, gap: 16, padding: '0 0 16px 0' }}>
      {rowItems.map(c => (
        <div
          key={c.customer_id}
          className="customer-card"
          onClick={() => navigate(`/customer/${c.customer_id}`)}
          role="button"
          tabIndex={0}
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
  )
}

function ListRow({ index, style, data }) {
  const c = data.items[index]
  if (!c) return null
  const { navigate } = data
  return (
    <div
      style={style}
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
  )
}

export default function Dashboard() {
  const [customers, setCustomers] = useState([])
  const [alerts, setAlerts] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const customersLenRef = useRef(0)
  const autoLoadingRef = useRef(false)
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [refreshing, setRefreshing] = useState(false)
  const [viewMode, setViewMode] = useState('grid')
  const [gridCols, setGridCols] = useState(3)
  const containerRef = useRef(null)
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

  useEffect(() => {
    const calcCols = () => {
      const w = containerRef.current?.offsetWidth || 1200
      setGridCols(Math.max(1, Math.floor((w + 16) / 336)))
    }
    calcCols()
    window.addEventListener('resize', calcCols)
    return () => window.removeEventListener('resize', calcCols)
  }, [])

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 400)
    return () => clearTimeout(t)
  }, [search])

  const loadData = useCallback(async (reset = true, offset = 0) => {
    try {
      if (reset) setLoading(true)
      const sortMap = { recent: 'last_activity', name: 'name', spent: 'total_spent', orders: 'total_orders' }
      const sortCol = sortMap[filters.sortBy] || 'last_activity'
      const [cRes, aRes] = await Promise.all([
        fetchCustomers({ limit: PAGE_SIZE, offset, search: debouncedSearch, sort: sortCol, order: 'DESC' }),
        reset ? fetchAlerts() : Promise.resolve(null),
      ])
      const customerList = cRes.customers || cRes.data || []
      if (reset) {
        setCustomers(customerList)
        if (aRes) setAlerts(aRes.alerts || aRes.data || [])
      } else {
        setCustomers(prev => [...prev, ...customerList])
      }
      setTotal(cRes.total || 0)
    } catch (e) {
      console.error('Failed to load data', e)
      toast('Failed to load dashboard data', 'error')
    } finally {
      setLoading(false)
    }
  }, [toast, debouncedSearch, filters.sortBy])

  useEffect(() => { customersLenRef.current = customers.length }, [customers.length])

  useEffect(() => { loadData(true, 0) }, [debouncedSearch, filters.sortBy])

  useEffect(() => {
    if (!loading && total > 0 && customersLenRef.current < total && !autoLoadingRef.current) {
      autoLoadingRef.current = true
      const loadAll = async () => {
        let current = customersLenRef.current
        while (current < total) {
          try {
            const sortMap = { recent: 'last_activity', name: 'name', spent: 'total_spent', orders: 'total_orders' }
            const sortCol = sortMap[filters.sortBy] || 'last_activity'
            const cRes = await fetchCustomers({ limit: PAGE_SIZE, offset: current, search: debouncedSearch, sort: sortCol, order: 'DESC' })
            const list = cRes.customers || cRes.data || []
            if (list.length === 0) break
            setCustomers(prev => [...prev, ...list])
            current += list.length
          } catch (e) {
            console.error('Auto-load failed', e)
            break
          }
        }
        autoLoadingRef.current = false
      }
      loadAll()
    }
  }, [loading, total, debouncedSearch, filters.sortBy])

  const handleRefresh = async () => {
    setRefreshing(true)
    autoLoadingRef.current = false
    try {
      await triggerRefreshAll()
      await loadData(true, 0)
    } catch (e) {
      console.error('Refresh failed', e)
      toast('Sync failed. Please try again.', 'error')
    } finally {
      setRefreshing(false)
    }
  }

  const handleFilterChange = useCallback((key, value) => {
    setFilters(f => ({ ...f, [key]: value }))
    if (key === 'sortBy') {
      autoLoadingRef.current = false
      const sortMap = { recent: 'last_activity', name: 'name', spent: 'total_spent', orders: 'total_orders' }
      const sortCol = sortMap[value] || 'last_activity'
      setLoading(true)
      fetchCustomers({ limit: PAGE_SIZE, offset: 0, search: debouncedSearch, sort: sortCol, order: 'DESC' })
        .then(cRes => { setCustomers(cRes.customers || cRes.data || []); setTotal(cRes.total || 0) })
        .catch(() => toast('Failed to reload', 'error'))
        .finally(() => setLoading(false))
    }
  }, [debouncedSearch, toast])

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
    let result = customers

    if (filters.sources.length > 0) {
      result = result.filter(c => filters.sources.some(s => c.sources?.includes(s)))
    }
    if (filters.hasOrders) result = result.filter(c => c.total_orders > 0)
    if (filters.hasBills) result = result.filter(c => c.total_bills > 0)
    if (filters.hasAlerts) {
      const ids = new Set(alerts.map(a => a.customer_id))
      result = result.filter(c => ids.has(c.customer_id))
    }
    if (spendRange.minSpent) result = result.filter(c => (c.total_spent || 0) >= Number(spendRange.minSpent))
    if (spendRange.maxSpent) result = result.filter(c => (c.total_spent || 0) <= Number(spendRange.maxSpent))

    return result
  }, [customers, filters, spendRange, alerts])

  const stats = useMemo(() => ({
    total: customers.length,
    withOrders: customers.filter(c => c.total_orders > 0).length,
    withBills: customers.filter(c => c.total_bills > 0).length,
    negativeAlerts: alerts.filter(a => a.severity === 'warning').length,
  }), [customers, alerts])

  const filterConfig = [
    { label: 'Source', key: 'sources', type: 'chips', options: SOURCES.map(s => ({ value: s.key, label: s.label, icon: s.icon, color: s.color })) },
    { label: 'Has', type: 'toggle', options: [
      { value: 'hasOrders', label: 'Orders' },
      { value: 'hasBills', label: 'Bills' },
      { value: 'hasAlerts', label: 'Alerts' },
    ]},
    { label: 'Spent Range (₹)', type: 'range', key: 'spend', minKey: 'minSpent', maxKey: 'maxSpent', minPlaceholder: 'Min', maxPlaceholder: 'Max' },
    { label: 'Sort by', key: 'sortBy', type: 'select', options: [
      { value: 'recent', label: 'Recent Activity' },
      { value: 'name', label: 'Name A-Z' },
      { value: 'spent', label: 'Highest Spent' },
      { value: 'orders', label: 'Most Orders' },
    ]},
  ]

  if (loading) {
    return (
      <div>
        <div className="page-toolbar">
          <div className="page-toolbar-left"><h1 className="page-title">Dashboard</h1></div>
        </div>
        <SkeletonStats />
        <SkeletonGrid count={6} />
      </div>
    )
  }

  const listHeight = Math.min(filtered.length * ROW_HEIGHT_LIST, 800)
  const gridRows = Math.ceil(filtered.length / gridCols)
  const gridHeight = Math.min(gridRows * (CARD_HEIGHT_GRID + 16), 800)

  return (
    <div ref={containerRef}>
      <div className="page-toolbar">
        <div className="page-toolbar-left">
          <h1 className="page-title">Dashboard</h1>
          <span className="page-subtitle">
            {customers.length} customers loaded {customers.length < total && `of ${total}`}
          </span>
        </div>
        <div className="header-actions">
          <button className="btn btn-primary" onClick={handleRefresh} disabled={refreshing}>
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
            <div className="stat-value">{stats.total.toLocaleString()}</div>
            <div className="stat-sub">{stats.withOrders} with orders &middot; {stats.withBills} with bills</div>
          </div>
        </div>
        <div className="stat-card stat-card-accent danger" style={{ cursor: 'pointer' }} onClick={() => navigate('/alerts')} role="button" tabIndex={0} onKeyDown={e => e.key === 'Enter' && navigate('/alerts')}>
          <div className="stat-icon stat-icon-bg-danger"><AlertTriangle size={20} /></div>
          <div className="stat-body">
            <div className="stat-label">Alerts</div>
            <div className="stat-value" style={{ color: stats.negativeAlerts > 0 ? 'var(--danger)' : 'var(--success)' }}>{stats.negativeAlerts}</div>
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
          if (key === 'minSpent' || key === 'maxSpent') handleRangeChange(key, value)
          else handleFilterChange(key, value)
        }}
        filterConfig={filterConfig}
        activeFilterCount={activeFilterCount}
        onClearAll={clearFilters}
      />

      <div className="results-meta">
        <span>{filtered.length} of {customers.length} customers</span>
        <div className="view-toggle">
          <button className={`btn btn-sm ${viewMode === 'grid' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setViewMode('grid')} aria-label="Grid view"><LayoutGrid size={14} /></button>
          <button className={`btn btn-sm ${viewMode === 'list' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setViewMode('list')} aria-label="List view"><List size={14} /></button>
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
            <button className="btn btn-secondary btn-sm" onClick={clearFilters}><X size={12} /> Clear all filters</button>
          ) : (
            <button className="btn btn-primary btn-sm" onClick={handleRefresh}><RefreshCw size={12} /> Sync All Data</button>
          )}
        />
      ) : viewMode === 'grid' ? (
        <VList
          height={gridHeight}
          itemCount={gridRows}
          itemSize={CARD_HEIGHT_GRID + 16}
          width="100%"
          overscanCount={3}
          itemData={{ items: filtered, cols: gridCols, navigate }}
        >
          {GridRow}
        </VList>
      ) : (
        <>
          <div className="customers-list">
            <div className="list-header">
              <span>Customer</span>
              <span>Phone</span>
              <span>Sources</span>
              <span>Orders</span>
              <span>Spent</span>
            </div>
          </div>
          <VList
            height={listHeight}
            itemCount={filtered.length}
            itemSize={ROW_HEIGHT_LIST}
            width="100%"
            overscanCount={10}
            itemData={{ items: filtered, navigate }}
          >
            {ListRow}
          </VList>
        </>
      )}
    </div>
  )
}

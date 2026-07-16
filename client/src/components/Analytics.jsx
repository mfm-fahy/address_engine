import { useState, useEffect, useMemo, useCallback } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, LineChart, Line, CartesianGrid, Legend
} from 'recharts'
import { fetchCustomers, fetchAlerts } from '../api'
import {
  TrendingUp, Users, AlertTriangle,
  RefreshCw, BarChart3, PieChart as PieChartIcon
} from 'lucide-react'
import { SkeletonStats, SkeletonChart, EmptyState, useToast } from './ui'

const COLORS = ['#6366f1', '#22c55e', '#f59e0b', '#3b82f6', '#e1306c', '#a855f7']
const SOURCE_LABELS = { instaxbot: 'Instaxbot', gowhats: 'GoWhats', f3: 'F3', bill: 'Billzy' }

const fmt = (n) => !isFinite(n) ? '₹0' : n >= 100000 ? `₹${(n / 100000).toFixed(1)}L` : n >= 1000 ? `₹${(n / 1000).toFixed(1)}K` : `₹${n}`

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: 'var(--bg-elevated)', border: '1px solid var(--border-light)',
      borderRadius: 8, padding: '10px 14px', fontSize: 13,
      boxShadow: 'var(--shadow-lg)'
    }}>
      <div style={{ color: 'var(--text-muted)', marginBottom: 4, fontSize: 12 }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color, fontWeight: 600, marginTop: 2 }}>
          {p.name}: {typeof p.value === 'number' && p.name?.includes('Revenue') ? fmt(p.value) : p.value}
        </div>
      ))}
    </div>
  )
}

export default function Analytics() {
  const [customers, setCustomers] = useState([])
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const toast = useToast()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [cRes, aRes] = await Promise.all([fetchCustomers(), fetchAlerts()])
      setCustomers(cRes.customers || [])
      setAlerts(aRes.alerts || [])
    } catch {
      toast('Failed to load analytics data', 'error')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => { load() }, [load])

  const sourceStats = useMemo(() => {
    const map = {}
    customers.forEach(c => {
      (c.sources || []).forEach(s => {
        if (!map[s]) map[s] = { name: SOURCE_LABELS[s] || s, customers: 0, revenue: 0 }
        map[s].customers++
        map[s].revenue += c.total_spent || 0
      })
    })
    return Object.values(map)
  }, [customers])

  const topCustomers = useMemo(() =>
    [...customers]
      .filter(c => c.total_spent > 0)
      .sort((a, b) => b.total_spent - a.total_spent)
      .slice(0, 10)
      .map(c => ({ name: c.name?.split(' ')[0] || c.phone, spent: Math.round(c.total_spent), orders: c.total_orders }))
  , [customers])

  const spendBuckets = useMemo(() => {
    const buckets = [
      { name: '₹0', range: [0, 0], count: 0 },
      { name: '₹1-1K', range: [1, 1000], count: 0 },
      { name: '₹1K-5K', range: [1000, 5000], count: 0 },
      { name: '₹5K-20K', range: [5000, 20000], count: 0 },
      { name: '₹20K-50K', range: [20000, 50000], count: 0 },
      { name: '₹50K+', range: [50000, Infinity], count: 0 },
    ]
    customers.forEach(c => {
      const s = c.total_spent || 0
      const b = buckets.find(b => s >= b.range[0] && s < b.range[1])
      if (b) b.count++
    })
    return buckets
  }, [customers])

  const monthlyRevenue = useMemo(() => {
    const map = {}
    customers.forEach(c => {
      const activity = c.last_activity
      if (!activity) return
      const month = new Date(activity).toLocaleDateString('en-IN', { month: 'short', year: '2-digit' })
      if (!map[month]) map[month] = { month, revenue: 0, customers: 0 }
      map[month].revenue += c.total_spent || 0
      map[month].customers++
    })
    return Object.values(map).slice(-8)
  }, [customers])

  const multiSourceCount = customers.filter(c => (c.sources?.length || 0) > 1).length
  const totalRevenue = customers.reduce((s, c) => s + (isFinite(c.total_spent) ? c.total_spent : 0), 0)
  const avgSpend = customers.length && isFinite(totalRevenue) ? totalRevenue / customers.length : 0
  const negAlerts = alerts.filter(a => a.severity === 'warning').length

  if (loading) {
    return (
      <div>
        <div className="page-toolbar">
          <div className="page-toolbar-left">
            <h1 className="page-title">Analytics</h1>
          </div>
        </div>
        <SkeletonStats count={4} />
        <div className="charts-grid">
          <SkeletonChart />
          <SkeletonChart />
          <div style={{ gridColumn: 'span 2' }}><SkeletonChart /></div>
          <SkeletonChart />
          <SkeletonChart />
        </div>
      </div>
    )
  }

  if (customers.length === 0) {
    return (
      <div className="analytics-page">
        <div className="page-toolbar">
          <div className="page-toolbar-left">
            <h1 className="page-title">Analytics</h1>
          </div>
        </div>
        <EmptyState
          icon={BarChart3}
          title="No analytics data"
          description="Sync customer data from all platforms to see analytics and insights."
        />
      </div>
    )
  }

  return (
    <div className="analytics-page">
      <div className="page-toolbar">
        <div className="page-toolbar-left">
          <h1 className="page-title">Analytics</h1>
        </div>
      </div>

      <div className="analytics-stats">
        <div className="stat-card stat-card-accent primary">
          <div className="stat-icon stat-icon-bg-primary"><TrendingUp size={20} /></div>
          <div className="stat-body">
            <div className="stat-label">Avg. Spend / Customer</div>
            <div className="stat-value">{fmt(Math.round(avgSpend))}</div>
          </div>
        </div>
        <div className="stat-card stat-card-accent warning">
          <div className="stat-icon stat-icon-bg-warning"><Users size={20} /></div>
          <div className="stat-body">
            <div className="stat-label">Multi-Platform</div>
            <div className="stat-value">{multiSourceCount}</div>
          </div>
        </div>
        <div className="stat-card stat-card-accent danger">
          <div className="stat-icon stat-icon-bg-danger"><AlertTriangle size={20} /></div>
          <div className="stat-body">
            <div className="stat-label">Active Alerts</div>
            <div className="stat-value" style={{ color: negAlerts > 0 ? 'var(--danger)' : 'var(--success)' }}>
              {negAlerts}
            </div>
          </div>
        </div>
      </div>

      <div className="charts-grid">
        <div className="chart-card">
          <div className="chart-title">Revenue by Platform</div>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={sourceStats} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
              <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 12 }} axisLine={{ stroke: '#334155' }} />
              <YAxis tickFormatter={v => fmt(v)} tick={{ fill: '#94a3b8', fontSize: 11 }} axisLine={{ stroke: '#334155' }} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="revenue" fill="#6366f1" radius={[4, 4, 0, 0]} maxBarSize={40} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card">
          <div className="chart-title">Customers by Platform</div>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie
                data={sourceStats}
                dataKey="customers"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={90}
                innerRadius={45}
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                labelLine={false}
              >
                {sourceStats.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card chart-card-wide">
          <div className="chart-title">Top 10 Customers by Revenue</div>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={topCustomers} layout="vertical" margin={{ top: 5, right: 30, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" horizontal={false} />
              <XAxis type="number" tickFormatter={v => fmt(v)} tick={{ fill: '#94a3b8', fontSize: 11 }} axisLine={{ stroke: '#334155' }} />
              <YAxis type="category" dataKey="name" tick={{ fill: '#94a3b8', fontSize: 12 }} width={80} axisLine={{ stroke: '#334155' }} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="spent" fill="#22c55e" radius={[0, 4, 4, 0]} maxBarSize={16} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card">
          <div className="chart-title">Customer Spend Distribution</div>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={spendBuckets} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
              <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 11 }} axisLine={{ stroke: '#334155' }} />
              <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} axisLine={{ stroke: '#334155' }} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="count" fill="#a855f7" radius={[4, 4, 0, 0]} maxBarSize={40} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card">
          <div className="chart-title">Activity by Last Seen Month</div>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={monthlyRevenue} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="month" tick={{ fill: '#94a3b8', fontSize: 11 }} axisLine={{ stroke: '#334155' }} />
              <YAxis yAxisId="left" tickFormatter={v => fmt(v)} tick={{ fill: '#94a3b8', fontSize: 11 }} axisLine={{ stroke: '#334155' }} />
              <YAxis yAxisId="right" orientation="right" tick={{ fill: '#94a3b8', fontSize: 11 }} axisLine={{ stroke: '#334155' }} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: 12, color: '#94a3b8', paddingTop: 8 }} />
              <Line yAxisId="left" type="monotone" dataKey="revenue" stroke="#6366f1" strokeWidth={2.5} dot={{ r: 0 }} activeDot={{ r: 4, fill: '#6366f1' }} name="Revenue" />
              <Line yAxisId="right" type="monotone" dataKey="customers" stroke="#22c55e" strokeWidth={2.5} dot={{ r: 0 }} activeDot={{ r: 4, fill: '#22c55e' }} name="Customers" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}

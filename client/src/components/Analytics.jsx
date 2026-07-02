import { useState, useEffect, useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, LineChart, Line, CartesianGrid, Legend
} from 'recharts'
import { fetchCustomers, fetchAlerts } from '../api'
import { TrendingUp, Users, IndianRupee, AlertTriangle, RefreshCw } from 'lucide-react'

const COLORS = ['#6366f1', '#22c55e', '#f59e0b', '#3b82f6', '#e1306c', '#a855f7']
const SOURCE_LABELS = { instaxbot: 'Instagram', gowhats: 'WhatsApp', f3: 'F3', bill: 'Billzzy' }

const fmt = (n) => n >= 100000 ? `₹${(n / 100000).toFixed(1)}L` : n >= 1000 ? `₹${(n / 1000).toFixed(1)}K` : `₹${n}`

export default function Analytics() {
  const [customers, setCustomers] = useState([])
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    try {
      const [cRes, aRes] = await Promise.all([fetchCustomers(), fetchAlerts()])
      setCustomers(cRes.customers || [])
      setAlerts(aRes.alerts || [])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

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
  const totalRevenue = customers.reduce((s, c) => s + (c.total_spent || 0), 0)
  const avgSpend = customers.length ? totalRevenue / customers.length : 0
  const negAlerts = alerts.filter(a => a.severity === 'warning').length

  if (loading) return (
    <div className="loading" style={{ minHeight: 400 }}>
      <RefreshCw size={24} className="spin" style={{ marginRight: 8 }} /> Loading analytics...
    </div>
  )

  return (
    <div className="analytics-page">
      <div className="analytics-stats">
        {[
          { label: 'Total Revenue', value: fmt(Math.round(totalRevenue)), icon: IndianRupee, color: 'var(--success)' },
          { label: 'Avg. Spend / Customer', value: fmt(Math.round(avgSpend)), icon: TrendingUp, color: 'var(--primary)' },
          { label: 'Multi-Platform', value: multiSourceCount, icon: Users, color: '#f59e0b' },
          { label: 'Active Alerts', value: negAlerts, icon: AlertTriangle, color: negAlerts > 0 ? 'var(--danger)' : 'var(--success)' },
        ].map(s => (
          <div key={s.label} className="stat-card stat-accent">
            <div className="stat-icon" style={{ color: s.color }}><s.icon size={20} /></div>
            <div className="stat-body">
              <div className="label">{s.label}</div>
              <div className="value" style={{ color: s.color }}>{s.value}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="charts-grid">
        <div className="chart-card">
          <div className="chart-title">Revenue by Platform</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={sourceStats} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 12 }} />
              <YAxis tickFormatter={v => fmt(v)} tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <Tooltip formatter={(v) => fmt(v)} contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }} />
              <Bar dataKey="revenue" fill="#6366f1" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card">
          <div className="chart-title">Customers by Platform</div>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={sourceStats} dataKey="customers" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`} labelLine={false}>
                {sourceStats.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card chart-wide">
          <div className="chart-title">Top 10 Customers by Revenue</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={topCustomers} layout="vertical" margin={{ top: 5, right: 30, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" horizontal={false} />
              <XAxis type="number" tickFormatter={v => fmt(v)} tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <YAxis type="category" dataKey="name" tick={{ fill: '#94a3b8', fontSize: 12 }} width={70} />
              <Tooltip formatter={(v) => fmt(v)} contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }} />
              <Bar dataKey="spent" fill="#22c55e" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card">
          <div className="chart-title">Customer Spend Distribution</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={spendBuckets} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }} />
              <Bar dataKey="count" fill="#a855f7" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card">
          <div className="chart-title">Activity by Last Seen Month</div>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={monthlyRevenue} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="month" tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <YAxis yAxisId="left" tickFormatter={v => fmt(v)} tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <YAxis yAxisId="right" orientation="right" tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }} />
              <Legend wrapperStyle={{ fontSize: 12, color: '#94a3b8' }} />
              <Line yAxisId="left" type="monotone" dataKey="revenue" stroke="#6366f1" strokeWidth={2} dot={false} name="Revenue" />
              <Line yAxisId="right" type="monotone" dataKey="customers" stroke="#22c55e" strokeWidth={2} dot={false} name="Customers" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}

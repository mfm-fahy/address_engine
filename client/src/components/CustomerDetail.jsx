import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, ShoppingCart, MessageCircle, Receipt, IndianRupee, AlertTriangle } from 'lucide-react'
import { fetchCustomer } from '../api'

export default function CustomerDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [customer, setCustomer] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        const data = await fetchCustomer(id)
        setCustomer(data)
      } catch (e) {
        console.error('Failed to load customer', e)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [id])

  if (loading) return <div className="loading">Loading customer...</div>
  if (!customer) return <div className="empty-state"><h3>Customer not found</h3></div>

  const allActivity = [
    ...(customer.orders || []).map(o => ({ ...o, type: 'order' })),
    ...(customer.bills || []).map(b => ({ ...b, type: 'bill' }))
  ].sort((a, b) => new Date(b.date || 0) - new Date(a.date || 0))

  return (
    <div className="detail-page">
      <button className="back-btn" onClick={() => navigate('/')}>
        <ArrowLeft size={16} /> Back to Dashboard
      </button>

      <div className="detail-header">
        <h2>{customer.name || 'Unknown Customer'}</h2>
        <div className="meta">
          {customer.customer_id} &middot; +91 {customer.phone}
          {customer.email ? ` &middot; ${customer.email}` : ''}
          {customer.username ? ` &middot; @${customer.username}` : ''}
        </div>
        <div className="badges">
          {customer.sources?.includes('instaxbot') && <span className="badge badge-insta">Instagram</span>}
          {customer.sources?.includes('gowhats') && <span className="badge badge-whats">WhatsApp</span>}
          {customer.sources?.includes('f3') && <span className="badge badge-f3">F3</span>}
          {customer.sources?.includes('bill') && <span className="badge badge-bill">Bill</span>}
        </div>
      </div>

      <div className="detail-grid">
        <div className="detail-card">
          <h3><ShoppingCart size={14} /> Orders ({customer.orders?.length || 0})</h3>
          {customer.orders?.length === 0 ? (
            <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>No orders yet</div>
          ) : (
            customer.orders?.map((o, i) => (
              <div key={i} className="order-item">
                <div className="order-header">
                  <span className="order-id">#{o.order_id}</span>
                  <span className={`order-status status-${o.status?.toLowerCase()}`}>{o.status}</span>
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  {o.source} &middot; {o.items?.length || 0} items
                </div>
                <div className="order-amount">₹{o.amount}</div>
              </div>
            ))
          )}
        </div>

        <div className="detail-card">
          <h3><Receipt size={14} /> Bills ({customer.bills?.length || 0})</h3>
          {customer.bills?.length === 0 ? (
            <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>No bills yet</div>
          ) : (
            customer.bills?.map((b, i) => (
              <div key={i} className="order-item">
                <div className="order-header">
                  <span className="order-id">Bill #{b.bill_no}</span>
                  <span className={`order-status status-${b.status?.toLowerCase()}`}>{b.status}</span>
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  {b.date} &middot; {b.items?.length || 0} items
                </div>
                <div className="order-amount">₹{b.amount}</div>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="detail-grid">
        <div className="detail-card">
          <h3><DollarSign size={14} /> Summary</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>Total Spent</span>
              <span style={{ fontWeight: 600, color: 'var(--success)' }}>₹{customer.total_spent?.toLocaleString()}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>Total Orders</span>
              <span style={{ fontWeight: 600 }}>{customer.total_orders}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>Total Bills</span>
              <span style={{ fontWeight: 600 }}>{customer.total_bills}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>Comments</span>
              <span style={{ fontWeight: 600 }}>{customer.comment_count || 0}</span>
            </div>
          </div>
        </div>

        <div className="alerts-panel">
          <h3><AlertTriangle size={14} /> Alerts</h3>
          {customer.alerts?.length === 0 || !customer.alerts ? (
            <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>No alerts</div>
          ) : (
            customer.alerts.map((a, i) => (
              <div key={i} className={`alert-item ${a.severity}`}>
                <AlertTriangle size={16} className="alert-icon" style={{ color: a.severity === 'warning' ? 'var(--warning)' : 'var(--danger)' }} />
                <div>
                  <div className="alert-text">{a.message}</div>
                  <div className="alert-time">{new Date(a.created_at).toLocaleString()}</div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {allActivity.length > 0 && (
        <div className="detail-card" style={{ marginTop: 20 }}>
          <h3>Activity Timeline</h3>
          {allActivity.slice(0, 20).map((a, i) => (
            <div key={i} className="order-item" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <span style={{ fontWeight: 600, fontSize: 13 }}>
                  {a.type === 'order' ? '🛒 Order' : '🧾 Bill'} #{a.order_id || a.bill_no}
                </span>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  {a.source} &middot; ₹{a.amount || a.amount}
                </div>
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'right' }}>
                <div>{new Date(a.date).toLocaleDateString()}</div>
                <span className={`order-status status-${a.status?.toLowerCase()}`}>{a.status}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

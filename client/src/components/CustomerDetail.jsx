import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, ShoppingCart, MessageCircle, IndianRupee,
  AlertTriangle, ChevronDown, ChevronUp, Package, MapPin,
  CreditCard, Truck, Clock, Store, Phone, Mail, User,
  Calendar, Shield, BadgePercent, Activity, RefreshCw, Sparkles, ShieldAlert
} from 'lucide-react'
import { fetchCustomer, fetchCustomerSummary, fetchCustomerBadComments } from '../api'
import { SkeletonDetail, EmptyState } from './ui'

function ExpandableSection({ title, count, children, defaultOpen }) {
  const [open, setOpen] = useState(defaultOpen || false)
  return (
    <div className="detail-card-section">
      <div className="expandable-header" onClick={() => setOpen(!open)}>
        <h3>{title} ({count})</h3>
        {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </div>
      {open && <div style={{ marginTop: 12 }}>{children}</div>}
    </div>
  )
}

function OrderItems({ items }) {
  if (!items || items.length === 0) return <div className="detail-muted">No items</div>
  return (
    <div className="items-list">
      {items.map((item, i) => (
        <div key={i} className="item-row">
          {item.imageUrl && <img src={item.imageUrl} alt={item.name} className="item-thumb" loading="lazy" />}
          <div className="item-info">
            <div className="item-name">{item.name}</div>
            <div className="item-meta">
              {item.sku && <span>SKU: {item.sku}</span>}
              {item.quantity > 1 && <span>Qty: {item.quantity}</span>}
            </div>
          </div>
          <div className="item-price">
            {item.quantity > 1 && <span className="item-unit">₹{item.price} × {item.quantity}</span>}
            <span className="item-total">₹{item.totalPrice || item.price * item.quantity}</span>
          </div>
        </div>
      ))}
    </div>
  )
}

function AddressBlock({ label, address }) {
  if (!address || !address.addressLine1) return null
  return (
    <div className="address-block">
      {label && <div className="address-label">{label}</div>}
      {address.name && <div>{address.name}{address.phone ? ` (${address.phone})` : ''}</div>}
      <div>{address.addressLine1}</div>
      {address.addressLine2 && <div>{address.addressLine2}</div>}
      <div>{[address.city, address.state, address.pincode].filter(Boolean).join(', ')}</div>
      {address.country && <div>{address.country}</div>}
    </div>
  )
}

function PaymentBlock({ raw }) {
  if (!raw) return null
  const pm = raw.paymentMethod
  const ps = raw.paymentStatus
  const pd = raw.paymentDetails
  return (
    <div className="detail-row">
      <CreditCard size={14} />
      <span>
        {pm && <span className="pill pill-info">{pm}</span>}
        {ps && <span className={`pill ${ps === 'completed' ? 'pill-success' : 'pill-warning'}`}>{ps}</span>}
        {pd?.paidAt && <span className="detail-muted">{new Date(pd.paidAt).toLocaleString()}</span>}
        {pd?.paidAmount && <span className="pill pill-success">₹{pd.paidAmount}</span>}
      </span>
    </div>
  )
}

function StatusHistory({ raw }) {
  const history = raw?.metadata?.statusHistory || raw?.statusHistory
  if (!history || history.length === 0) return null
  return (
    <div className="timeline" style={{ marginTop: 8 }}>
      <div className="detail-label">Status History</div>
      {history.map((h, i) => (
        <div key={i} className="timeline-item">
          <div className="timeline-dot" />
          <div>
            <span className={`order-status status-${h.status?.toLowerCase()}`}>{h.status}</span>
            <span className="detail-muted" style={{ marginLeft: 8 }}>
              {new Date(h.changedAt || h.changed_at).toLocaleString()}
            </span>
            {h.changedBy && <span className="detail-muted" style={{ marginLeft: 4 }}>by {h.changedBy}</span>}
          </div>
        </div>
      ))}
    </div>
  )
}

function OrderDetailCard({ order }) {
  const raw = order.raw || {}
  return (
    <div className="order-detail-card">
      <div className="order-detail-header">
        <div>
          <span className="order-id">#{order.order_id}</span>
          <span className={`order-status status-${order.status?.toLowerCase()}`}>{order.status}</span>
        </div>
        <div className="order-amount">₹{order.amount}</div>
      </div>
      <div className="detail-row">
        <Clock size={14} />
        <span className="detail-muted">{new Date(order.date).toLocaleString()}</span>
        <span className="pill pill-info">{order.source}</span>
      </div>

      <PaymentBlock raw={raw} />

      {raw.shippingAddress?.addressLine1 && (
        <div className="detail-row">
          <MapPin size={14} />
          <AddressBlock label="Shipping" address={raw.shippingAddress} />
        </div>
      )}

      {raw.billingAddress?.addressLine1 && (
        <div className="detail-row">
          <MapPin size={14} />
          <AddressBlock label="Billing" address={raw.billingAddress} />
        </div>
      )}

      <div className="detail-row">
        <Package size={14} />
        <span>
          {raw.orderAmount != null && <span className="pill">Subtotal: ₹{raw.orderAmount}</span>}
          {raw.shippingCost > 0 && <span className="pill">Shipping: ₹{raw.shippingCost}</span>}
          {raw.taxAmount > 0 && <span className="pill">Tax: ₹{raw.taxAmount}</span>}
          {raw.discountAmount > 0 && <span className="pill pill-warning">Discount: -₹{raw.discountAmount}</span>}
        </span>
      </div>

      {raw.salesPersonName && (
        <div className="detail-row">
          <span className="detail-muted">Sales Person: {raw.salesPersonName}</span>
        </div>
      )}

      <div style={{ marginTop: 8 }}>
        <div className="detail-label">Products ({order.items?.length || 0})</div>
        <OrderItems items={order.items} />
      </div>

      <StatusHistory raw={raw} />

      {raw.metadata?.trackingHistory?.length > 0 && (
        <div className="detail-row">
          <Truck size={14} />
          <span className="detail-muted">Tracking: {raw.metadata.trackingHistory.length} events</span>
        </div>
      )}

      {raw._id && <div className="detail-muted" style={{ fontSize: 10, marginTop: 4, color: 'var(--text-dim)' }}>ID: {raw._id}</div>}
    </div>
  )
}

function BillDetailCard({ bill }) {
  const raw = bill.raw || {}
  return (
    <div className="order-detail-card">
      <div className="order-detail-header">
        <div>
          <span className="order-id">Bill #{bill.bill_no}</span>
          <span className={`order-status status-${bill.status?.toLowerCase()}`}>{bill.status}</span>
        </div>
        <div className="order-amount">₹{bill.amount}</div>
      </div>
      <div className="detail-row">
        <Clock size={14} />
        <span className="detail-muted">{bill.date}</span>
        {raw.transactionId && <span className="pill">Txn: {raw.transactionId}</span>}
      </div>
      {raw.customer?.address && (
        <div className="detail-row">
          <MapPin size={14} />
          <span className="detail-muted">{raw.customer.address}</span>
        </div>
      )}
      <div style={{ marginTop: 8 }}>
        <div className="detail-label">Products ({bill.items?.length || 0})</div>
        <OrderItems items={bill.items} />
      </div>
      {raw.internalBillNo && <div className="detail-muted" style={{ fontSize: 10, marginTop: 4, color: 'var(--text-dim)' }}>Internal: {raw.internalBillNo}</div>}
    </div>
  )
}

export default function CustomerDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [customer, setCustomer] = useState(null)
  const [loading, setLoading] = useState(true)
  const [summary, setSummary] = useState('')
  const [summaryLoading, setSummaryLoading] = useState(false)
  const [badComments, setBadComments] = useState([])
  const [badCommentsLoading, setBadCommentsLoading] = useState(false)

  useEffect(() => {
    const load = async () => {
      try {
        const data = await fetchCustomer(id)
        setCustomer(data)
        if (data.profile_summary) {
          setSummary(data.profile_summary)
        }
        setBadCommentsLoading(true)
        try {
          const bc = await fetchCustomerBadComments(id)
          setBadComments(bc.bad_comments || [])
        } catch (e) {
          console.error('Failed to load bad comments', e)
        } finally {
          setBadCommentsLoading(false)
        }
      } catch (e) {
        console.error('Failed to load customer', e)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [id])

  const handleRefreshSummary = useCallback(async () => {
    setSummaryLoading(true)
    try {
      const result = await fetchCustomerSummary(id, true)
      setSummary(result.summary)
    } catch (e) {
      console.error('Failed to refresh summary', e)
    } finally {
      setSummaryLoading(false)
    }
  }, [id])

  if (loading) return <SkeletonDetail />
  if (!customer) return <EmptyState icon={User} title="Customer not found" description="The customer you're looking for doesn't exist or has been removed." />

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
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
          <div>
            <h2>{customer.name || 'Unknown Customer'}</h2>
            <div className="meta">
              {customer.customer_id} &middot; +91 {customer.phone}
              {customer.email ? ` &middot; ${customer.email}` : ''}
              {customer.username ? ` &middot; @${customer.username}` : ''}
            </div>
          </div>
          {customer.total_spent >= 50000 && (
            <span className="badge badge-vip" style={{ fontSize: 12, padding: '4px 12px' }}>VIP</span>
          )}
        </div>
        {customer.address?.addressLine1 && (
          <div className="detail-row" style={{ marginTop: 8 }}>
            <MapPin size={14} />
            <AddressBlock label="" address={customer.address} />
          </div>
        )}
        <div className="badges">
          {customer.sources?.includes('instaxbot') && <span className="badge badge-insta">Instaxbot</span>}
          {customer.sources?.includes('gowhats') && <span className="badge badge-whats">GoWhats</span>}
          {customer.sources?.includes('f3') && <span className="badge badge-f3">F3</span>}
          {customer.sources?.includes('bill') && <span className="badge badge-bill">Billzy</span>}
        </div>
      </div>

      <div className="detail-grid">
        <div className="detail-card-section">
          <h3><IndianRupee size={14} /> Summary</h3>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <div className="summary-row">
              <span className="detail-muted">Total Spent</span>
              <span className="summary-value" style={{ color: 'var(--success)' }}>₹{isFinite(customer.total_spent) ? customer.total_spent.toLocaleString() : 0}</span>
            </div>
            <div className="summary-row">
              <span className="detail-muted">Total Orders</span>
              <span className="summary-value">{customer.total_orders}</span>
            </div>
            <div className="summary-row">
              <span className="detail-muted">Total Bills</span>
              <span className="summary-value">{customer.total_bills}</span>
            </div>
            <div className="summary-row">
              <span className="detail-muted">Comments</span>
              <span className="summary-value">{customer.comment_count || 0}</span>
            </div>
            <div className="summary-row">
              <span className="detail-muted">Last Activity</span>
              <span className="summary-value" style={{ fontSize: 12, fontWeight: 500 }}>{customer.last_activity ? new Date(customer.last_activity).toLocaleDateString() : '-'}</span>
            </div>
          </div>
        </div>

        <div className="alerts-panel-section" style={customer.alerts?.length > 0 ? { border: '1px solid rgba(239, 68, 68, 0.25)' } : {}}>
          <h3 style={customer.alerts?.length > 0 ? { color: 'var(--danger)' } : {}}>
            <AlertTriangle size={14} /> Alerts ({customer.alerts?.length || 0})
          </h3>
          {customer.alerts?.length === 0 || !customer.alerts ? (
            <div className="detail-muted" style={{ textAlign: 'center', padding: 20 }}>No alerts</div>
          ) : (
            customer.alerts.map((a, i) => (
              <div key={i} className={`alert-item ${a.severity === 'warning' ? 'warning' : 'error'}`}>
                <AlertTriangle size={16} className="alert-icon" style={{ color: a.severity === 'warning' ? 'var(--warning)' : 'var(--danger)' }} />
                <div style={{ flex: 1 }}>
                  <div className="alert-text">{a.message}</div>
                  <div className="alert-time">{new Date(a.created_at).toLocaleString()}</div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="detail-card-section summary-section">
        <div className="summary-header">
          <h3><Sparkles size={14} /> AI Profile Summary</h3>
          <button className="btn btn-ghost btn-sm" onClick={handleRefreshSummary} disabled={summaryLoading}>
            <RefreshCw size={14} className={summaryLoading ? 'spin' : ''} />
            {summaryLoading ? 'Generating...' : 'Refresh'}
          </button>
        </div>
        {summary ? (
          <p className="summary-text">{summary}</p>
        ) : summaryLoading ? (
          <div className="summary-loading">
            <div className="skeleton-line" style={{ width: '100%' }} />
            <div className="skeleton-line" style={{ width: '85%' }} />
            <div className="skeleton-line" style={{ width: '60%' }} />
          </div>
        ) : (
          <div className="detail-muted" style={{ textAlign: 'center', padding: 16 }}>
            No summary available. Click refresh to generate one.
          </div>
        )}
      </div>

      {customer.stores?.length > 0 && (
        <div className="detail-card-section stores-section">
          <h3><Store size={14} /> Stores Purchased From ({customer.stores.length})</h3>
          <div className="stores-grid">
            {customer.stores.map((store, i) => (
              <div key={i} className="store-card">
                <div className="store-name">{store.name}</div>
                <div className="store-meta">
                  <span className={`pill ${store.type === 'bill_org' ? 'badge-bill' : 'badge-f3'}`}>
                    {store.type === 'bill_org' ? 'Bill' : 'Retailer'}
                  </span>
                  <span className="pill pill-info">
                    {store.sources?.join(', ')}
                  </span>
                </div>
                <div className="store-stats">
                  <div className="store-stat">
                    <ShoppingCart size={12} />
                    <span>{store.order_count} {store.order_count === 1 ? 'order' : 'orders'}</span>
                  </div>
                  <div className="store-stat">
                    <IndianRupee size={12} />
                    <span>₹{isFinite(store.total_spent) ? store.total_spent.toLocaleString() : 0}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <ExpandableSection title="Orders" count={customer.orders?.length || 0} defaultOpen={true}>
          {customer.orders?.length === 0 ? (
            <div className="detail-muted" style={{ textAlign: 'center', padding: 12 }}>No orders yet</div>
          ) : (
            customer.orders.map((o, i) => <OrderDetailCard key={i} order={o} />)
          )}
        </ExpandableSection>

        <ExpandableSection title="Bills" count={customer.bills?.length || 0} defaultOpen={true}>
          {customer.bills?.length === 0 ? (
            <div className="detail-muted" style={{ textAlign: 'center', padding: 12 }}>No bills yet</div>
          ) : (
            customer.bills.map((b, i) => <BillDetailCard key={i} bill={b} />)
          )}
        </ExpandableSection>

        <ExpandableSection title="Comments" count={customer.comments?.length || 0} defaultOpen={true}>
          {customer.comments?.length === 0 ? (
            <div className="detail-muted" style={{ textAlign: 'center', padding: 12 }}>No comments yet</div>
          ) : (
            customer.comments.map((c, i) => (
              <div key={i} className={`comment-card ${c.is_negative ? 'comment-negative' : ''} ${c.triggered_rule === 'bad_command' ? 'comment-bad-command' : ''}`}>
                <div className="comment-header">
                  <span className="comment-username">@{c.username}</span>
                  <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                    {c.triggered_rule === 'bad_command' && (
                      <span className="pill pill-bad-command">
                        <ShieldAlert size={10} /> Bad Command
                      </span>
                    )}
                    <span className={`pill ${c.is_negative ? 'pill-danger' : c.sentiment_label === 'positive' ? 'pill-success' : 'pill-info'}`}>
                      {c.sentiment_label}
                    </span>
                  </div>
                </div>
                <div className="comment-text">{c.text}</div>
                <div className="comment-meta">
                  <MessageCircle size={12} />
                  <span>{new Date(c.created_at).toLocaleString()}</span>
                </div>
              </div>
            ))
          )}
        </ExpandableSection>

        {badComments.length > 0 && (
          <div className="detail-card-section bad-comments-section">
            <div className="bad-comments-banner">
              <ShieldAlert size={16} />
              <span>Bad Commands Detected ({badComments.length})</span>
            </div>
            <div className="bad-comments-alert">
              <AlertTriangle size={14} />
              <span>These comments were flagged by the bad commands detection system</span>
            </div>
            {badComments.map((c, i) => (
              <div key={i} className="comment-card comment-negative comment-bad-command">
                <div className="comment-header">
                  <span className="comment-username">@{c.username}</span>
                  <span className="pill pill-bad-command">
                    <ShieldAlert size={10} /> Bad Command
                  </span>
                </div>
                <div className="comment-text">{c.text}</div>
                <div className="comment-meta">
                  <MessageCircle size={12} />
                  <span>{new Date(c.created_at).toLocaleString()}</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {allActivity.length > 0 && (
          <ExpandableSection title="Activity Timeline" count={allActivity.length}>
            {allActivity.slice(0, 50).map((a, i) => (
              <div key={i} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '10px 0', borderBottom: '1px solid var(--border-subtle)'
              }}>
                <div>
                  <span style={{ fontWeight: 600, fontSize: 13 }}>
                    {a.type === 'order' ? 'Order' : 'Bill'} #{a.order_id || a.bill_no}
                  </span>
                  <div className="detail-muted" style={{ fontSize: 12, marginTop: 2 }}>
                    {a.source} &middot; ₹{a.amount}
                  </div>
                </div>
                <div style={{ fontSize: 12, textAlign: 'right' }}>
                  <div className="detail-muted">{new Date(a.date).toLocaleDateString()}</div>
                  <span className={`order-status status-${a.status?.toLowerCase()}`}>{a.status}</span>
                </div>
              </div>
            ))}
          </ExpandableSection>
        )}
      </div>
    </div>
  )
}

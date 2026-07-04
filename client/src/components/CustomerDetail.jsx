import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, ShoppingCart, MessageCircle, Receipt, IndianRupee, AlertTriangle, ChevronDown, ChevronUp, Package, MapPin, CreditCard, Truck, Clock } from 'lucide-react'
import { fetchCustomer } from '../api'

function ExpandableSection({ title, count, children, defaultOpen }) {
  const [open, setOpen] = useState(defaultOpen || false)
  return (
    <div className="detail-card">
      <div className="expandable-header" onClick={() => setOpen(!open)} style={{ cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0 }}>{title} ({count})</h3>
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
          {item.imageUrl && <img src={item.imageUrl} alt={item.name} className="item-thumb" />}
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
      <div className="address-label">{label}</div>
      <div>{address.name}{address.phone ? ` (${address.phone})` : ''}</div>
      <div>{address.addressLine1}</div>
      {address.addressLine2 && <div>{address.addressLine2}</div>}
      <div>{[address.city, address.state, address.pincode].filter(Boolean).join(', ')}</div>
      <div>{address.country}</div>
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
    <div className="timeline">
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
        <div className="detail-row"><span className="detail-muted">Sales Person: {raw.salesPersonName}</span></div>
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

      {raw._id && <div className="detail-muted" style={{ fontSize: 10, marginTop: 4 }}>ID: {raw._id}</div>}
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
      {raw.internalBillNo && <div className="detail-muted" style={{ fontSize: 10, marginTop: 4 }}>Internal: {raw.internalBillNo}</div>}
    </div>
  )
}

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
        {customer.metadata?.flatNo && (
          <div className="meta" style={{ fontSize: 13, marginTop: 4 }}>
            <MapPin size={12} style={{ verticalAlign: 'middle', marginRight: 4 }} />
            {[
              customer.metadata.flatNo,
              customer.metadata.street,
              customer.metadata.district,
              customer.metadata.state,
              customer.metadata.pincode
            ].filter(Boolean).join(', ')}
          </div>
        )}
        <div className="badges">
          {customer.sources?.includes('instaxbot') && <span className="badge badge-insta">Instagram</span>}
          {customer.sources?.includes('gowhats') && <span className="badge badge-whats">WhatsApp</span>}
          {customer.sources?.includes('f3') && <span className="badge badge-f3">F3</span>}
          {customer.sources?.includes('bill') && <span className="badge badge-bill">Bill</span>}
        </div>
      </div>

      <div className="detail-grid">
        <div className="detail-card">
          <h3><IndianRupee size={14} /> Summary</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div className="summary-row">
              <span className="detail-muted">Total Spent</span>
              <span className="summary-value" style={{ color: 'var(--success)' }}>₹{customer.total_spent?.toLocaleString()}</span>
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
              <span className="summary-value" style={{ fontSize: 12 }}>{customer.last_activity ? new Date(customer.last_activity).toLocaleDateString() : '-'}</span>
            </div>
          </div>
        </div>

        <div className="alerts-panel">
          <h3><AlertTriangle size={14} /> Alerts ({customer.alerts?.length || 0})</h3>
          {customer.alerts?.length === 0 || !customer.alerts ? (
            <div className="detail-muted">No alerts</div>
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

      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <ExpandableSection title="Orders" count={customer.orders?.length || 0} defaultOpen={true}>
          {customer.orders?.length === 0 ? (
            <div className="detail-muted">No orders yet</div>
          ) : (
            customer.orders.map((o, i) => <OrderDetailCard key={i} order={o} />)
          )}
        </ExpandableSection>

        <ExpandableSection title="Bills" count={customer.bills?.length || 0} defaultOpen={true}>
          {customer.bills?.length === 0 ? (
            <div className="detail-muted">No bills yet</div>
          ) : (
            customer.bills.map((b, i) => <BillDetailCard key={i} bill={b} />)
          )}
        </ExpandableSection>

        {allActivity.length > 0 && (
          <ExpandableSection title="Activity Timeline" count={allActivity.length}>
            {allActivity.slice(0, 50).map((a, i) => (
              <div key={i} className="order-item" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <span style={{ fontWeight: 600, fontSize: 13 }}>
                    {a.type === 'order' ? 'Order' : 'Bill'} #{a.order_id || a.bill_no}
                  </span>
                  <div className="detail-muted" style={{ fontSize: 12 }}>
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

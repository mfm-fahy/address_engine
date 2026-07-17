const BASE = '/api'

async function request(url, options = {}) {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export const fetchCustomers = (params = {}) => {
  const qs = new URLSearchParams()
  if (params.limit) qs.set('limit', params.limit)
  if (params.offset) qs.set('offset', params.offset)
  if (params.search) qs.set('search', params.search)
  if (params.sort) qs.set('sort', params.sort)
  if (params.order) qs.set('order', params.order)
  const q = qs.toString()
  return request(`/customers${q ? '?' + q : ''}`)
}
export const fetchCustomer = (id) => request(`/customers/${id}?include_comments=true`)
export const fetchAlerts = () => request('/alerts?limit=10000')
export const triggerFetchData = () => request('/fetch-data', { method: 'POST' })
export const triggerBuildProfiles = () => request('/build-profiles', { method: 'POST' })
export const triggerAnalyzeComments = () => request('/analyze-comments', { method: 'POST' })
export const triggerRefreshAll = () => request('/refresh-all', { method: 'POST' })
export const fetchCustomerSummary = (id, refresh = false) => request(`/customers/${id}/summary${refresh ? '?refresh=true' : ''}`)
export const fetchCustomerBadComments = (id) => request(`/customers/${id}/bad-comments`)

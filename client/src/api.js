const BASE = '/api'

async function request(url, options = {}) {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export const fetchCustomers = () => request('/customers')
export const fetchCustomer = (id) => request(`/customers/${id}`)
export const fetchAlerts = () => request('/alerts')
export const triggerFetchData = () => request('/fetch-data', { method: 'POST' })
export const triggerBuildProfiles = () => request('/build-profiles', { method: 'POST' })
export const triggerAnalyzeComments = () => request('/analyze-comments', { method: 'POST' })
export const triggerRefreshAll = () => request('/refresh-all', { method: 'POST' })
export const fetchCustomerSummary = (id, refresh = false) => request(`/customers/${id}/summary${refresh ? '?refresh=true' : ''}`)

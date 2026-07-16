import { useState, useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './AuthContext'
import Dashboard from './components/Dashboard'
import CustomerDetail from './components/CustomerDetail'
import Analytics from './components/Analytics'
import AllAlerts from './components/AllAlerts'
import Login from './components/Login'
import Navbar from './components/Navbar'
import { ToastProvider } from './components/ui'
import { fetchAlerts } from './api'

function Protected({ children }) {
  const { user } = useAuth()
  return user ? children : <Navigate to="/login" replace />
}

function Layout({ children }) {
  const { user } = useAuth()
  const [alertCount, setAlertCount] = useState(0)

  useEffect(() => {
    fetchAlerts()
      .then(res => setAlertCount((res.alerts || []).length))
      .catch(() => {})
  }, [])

  return (
    <div className="layout">
      <Navbar alertCount={alertCount} />
      <main className="main-content">{children}</main>
    </div>
  )
}

export default function App() {
  return (
    <ToastProvider>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<Protected><Layout><Dashboard /></Layout></Protected>} />
          <Route path="/customer/:id" element={<Protected><Layout><CustomerDetail /></Layout></Protected>} />
          <Route path="/alerts" element={<Protected><Layout><AllAlerts /></Layout></Protected>} />
          <Route path="/analytics" element={<Protected><Layout><Analytics /></Layout></Protected>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </ToastProvider>
  )
}

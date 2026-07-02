import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './AuthContext'
import Dashboard from './components/Dashboard'
import CustomerDetail from './components/CustomerDetail'
import Analytics from './components/Analytics'
import Login from './components/Login'
import Navbar from './components/Navbar'

function Protected({ children }) {
  const { user } = useAuth()
  return user ? children : <Navigate to="/login" replace />
}

function Layout({ children }) {
  return (
    <div className="layout">
      <Navbar />
      <main className="main-content">{children}</main>
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<Protected><Layout><Dashboard /></Layout></Protected>} />
        <Route path="/customer/:id" element={<Protected><Layout><CustomerDetail /></Layout></Protected>} />
        <Route path="/analytics" element={<Protected><Layout><Analytics /></Layout></Protected>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  )
}

import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../AuthContext'
import { LayoutDashboard, BarChart3, LogOut, Bell, Users } from 'lucide-react'

export default function Navbar({ alertCount = 0 }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <nav className="navbar" role="navigation" aria-label="Main navigation">
      <NavLink to="/" className="navbar-brand" aria-label="Dashboard home">
        <div className="navbar-brand-icon">
          <Users size={18} />
        </div>
        <span className="navbar-brand-text">Customer360</span>
      </NavLink>
      <div className="navbar-links">
        <NavLink to="/" end className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          <LayoutDashboard size={15} />
          <span>Dashboard</span>
        </NavLink>
        <NavLink to="/analytics" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          <BarChart3 size={15} />
          <span>Analytics</span>
        </NavLink>
      </div>
      <div className="navbar-right">
        {alertCount > 0 && (
          <div
            className="nav-alert-badge"
            role="button"
            tabIndex={0}
            aria-label={`${alertCount} alerts`}
            onClick={() => navigate('/alerts')}
            onKeyDown={e => e.key === 'Enter' && navigate('/alerts')}
          >
            <Bell size={14} />
            <span>{alertCount}</span>
          </div>
        )}
        {user && <span className="nav-user" title={user}>{user}</span>}
        <button className="btn btn-ghost btn-sm" onClick={handleLogout} aria-label="Sign out">
          <LogOut size={13} />
          <span>Sign Out</span>
        </button>
      </div>
    </nav>
  )
}

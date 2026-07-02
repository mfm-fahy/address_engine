import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../AuthContext'
import { Users, BarChart2, LogOut, Bell } from 'lucide-react'

export default function Navbar({ alertCount = 0 }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <nav className="navbar">
      <div className="navbar-brand">
        <Users size={20} />
        <span>Customer360</span>
      </div>
      <div className="navbar-links">
        <NavLink to="/" end className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          <Users size={15} /> Customers
        </NavLink>
        <NavLink to="/analytics" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          <BarChart2 size={15} /> Analytics
        </NavLink>
      </div>
      <div className="navbar-right">
        {alertCount > 0 && (
          <div className="nav-alert-badge">
            <Bell size={15} />
            <span>{alertCount}</span>
          </div>
        )}
        <span className="nav-user">{user}</span>
        <button className="btn btn-outline btn-sm" onClick={handleLogout}>
          <LogOut size={13} /> Logout
        </button>
      </div>
    </nav>
  )
}

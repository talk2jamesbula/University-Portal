import { useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { roleLabel } from '../auth/access'
import { useAuth } from '../auth/useAuth'
import { UNIVERSITY_NAME } from '../utils/format'
import Icon from './Icon'
import { NAV, showsAdminConsole } from './navigation'
import NotificationBell from './NotificationBell'
import { Avatar } from './ui'

export default function Layout() {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)

  const items = NAV.filter((item) => item.show(user))

  return (
    <div className={`shell ${open ? 'nav-open' : ''}`}>
      {/* On mobile, following any link or button in the drawer closes it. */}
      <aside className="sidebar" onClick={(e) => e.target.closest('a, button') && setOpen(false)}>
        <Link to="/" className="brand" title="Go to the university website">
          <span className="brand-mark"><Icon name="cap" size={20} strokeWidth={2} /></span>
          <div>
            <div className="brand-name">{UNIVERSITY_NAME}</div>
            <div className="brand-sub">University Portal</div>
          </div>
        </Link>
        <nav className="nav" aria-label="Main">
          {items.map((item) => (
            <NavLink key={`${item.to}-${item.label}`} to={item.to} end={item.end} className="nav-link">
              <Icon name={item.icon} />
              <span>{item.label}</span>
            </NavLink>
          ))}
          {showsAdminConsole(user) && (
            <a className="nav-link" href="/admin/" target="_blank" rel="noreferrer">
              <Icon name="lock" />
              <span>Admin Console</span>
            </a>
          )}
        </nav>
        <div className="sidebar-footer">
          <NavLink to="/portal/profile" className="nav-link">
            <Icon name="user" />
            <span>My Profile</span>
          </NavLink>
          <Link to="/" className="nav-link">
            <Icon name="globe" />
            <span>University website</span>
          </Link>
          <button className="nav-link" onClick={() => logout('/')}>
            <Icon name="logout" />
            <span>Sign out</span>
          </button>
        </div>
      </aside>
      <div className="scrim" onClick={() => setOpen(false)} />

      <div className="main">
        <header className="topbar">
          <button className="icon-btn menu-btn" onClick={() => setOpen(true)} aria-label="Open menu">
            <Icon name="menu" size={20} />
          </button>
          <div className="topbar-spacer" />
          <NotificationBell />
          <NavLink to="/portal/profile" className="user-chip">
            <Avatar name={user.full_name || user.username} src={user.avatar_url} size={34} />
            <div className="user-chip-text">
              <span className="user-chip-name">{user.full_name || user.username}</span>
              <span className="user-chip-role">{roleLabel(user)}{user.university_id ? ` · ${user.university_id}` : ''}</span>
            </div>
          </NavLink>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

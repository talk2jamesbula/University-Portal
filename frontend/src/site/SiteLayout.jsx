import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import Icon from '../components/Icon'
import ChatWidget from './ChatWidget'
import { SITE } from './content'

const MENU = [
  { label: 'About', to: '/about' },
  {
    label: 'Academics',
    items: [
      { to: '/faculties', label: 'Faculties & Departments', text: 'Our four faculties and their departments' },
      { to: '/programmes', label: 'Academic Programmes', text: 'Undergraduate degrees and curricula' },
      { to: '/research', label: 'Research', text: 'Centres, groups and research support' },
      { to: '/library', label: 'Library', text: 'Opening hours, services and e-resources' },
    ],
  },
  { label: 'Admissions', to: '/admissions' },
  {
    label: 'News & Events',
    items: [
      { to: '/news', label: 'News & Announcements', text: 'The latest from around the university' },
      { to: '/events', label: 'Events', text: 'Ceremonies, deadlines and campus life' },
    ],
  },
  { label: 'Contact', to: '/contact' },
]

function Dropdown({ group }) {
  const { pathname } = useLocation()
  const active = group.items.some((item) => pathname.startsWith(item.to))
  return (
    <div className="site-dropdown">
      <button className={`site-nav-link ${active ? 'active' : ''}`} aria-haspopup="true">
        {group.label} <Icon name="chevronDown" size={14} />
      </button>
      <div className="site-dropdown-panel">
        {group.items.map((item) => (
          <NavLink key={item.to} to={item.to} className="site-dropdown-item">
            <strong>{item.label}</strong>
            <span>{item.text}</span>
          </NavLink>
        ))}
      </div>
    </div>
  )
}

function PortalButtons() {
  const { user } = useAuth()
  if (user) {
    return <Link to="/portal" className="btn btn-gold btn-sm"><Icon name="home" size={15} /> Go to my portal</Link>
  }
  return (
    <>
      <Link to="/login/staff" className="btn btn-outline-light btn-sm">Staff Portal</Link>
      <Link to="/login/student" className="btn btn-gold btn-sm">Student Portal</Link>
    </>
  )
}

export default function SiteLayout() {
  const [open, setOpen] = useState(false)
  const { pathname } = useLocation()

  // Start each new page at the top.
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])

  return (
    <div className="site">
      <div className="site-topbar">
        <div className="site-container site-topbar-inner">
          <span className="site-topbar-contact">
            <a href={`tel:${SITE.phone.replace(/\s/g, '')}`}><Icon name="phone" size={13} /> {SITE.phone}</a>
            <a href={`mailto:${SITE.email}`}><Icon name="mail" size={13} /> {SITE.email}</a>
          </span>
          <span className="site-topbar-links">
            <Link to="/apply">Apply online</Link>
            <Link to="/login/applicant">Applicant sign-in</Link>
            <Link to="/library">Library</Link>
            <Link to="/login/student">Student Portal</Link>
            <Link to="/login/staff">Staff Portal</Link>
          </span>
        </div>
      </div>

      <header className="site-header">
        <div className="site-container site-header-inner">
          <Link to="/" className="site-brand" onClick={() => setOpen(false)}>
            <span className="brand-mark"><Icon name="cap" size={22} strokeWidth={2} /></span>
            <span>
              <span className="site-brand-name">{SITE.name}</span>
              <span className="site-brand-motto">{SITE.motto}</span>
            </span>
          </Link>
          <nav className="site-nav" aria-label="Main">
            <NavLink to="/" end className="site-nav-link">Home</NavLink>
            {MENU.map((item) => item.items
              ? <Dropdown key={item.label} group={item} />
              : <NavLink key={item.to} to={item.to} className="site-nav-link">{item.label}</NavLink>)}
          </nav>
          <div className="site-header-actions"><PortalButtons /></div>
          <button className="icon-btn site-menu-btn" onClick={() => setOpen(!open)} aria-expanded={open} aria-label="Menu">
            <Icon name={open ? 'close' : 'menu'} size={22} />
          </button>
        </div>
        {open && (
          <div className="site-mobile-menu" onClick={(e) => e.target.closest('a') && setOpen(false)}>
            <NavLink to="/" end>Home</NavLink>
            {MENU.flatMap((item) => item.items ? item.items : [item]).map((item) => (
              <NavLink key={item.to} to={item.to}>{item.label}</NavLink>
            ))}
            <div className="site-mobile-actions"><PortalButtons /></div>
          </div>
        )}
      </header>

      <main className="site-main"><Outlet /></main>
      <ChatWidget />

      <footer className="site-footer">
        <div className="site-container site-footer-grid">
          <div>
            <div className="site-brand site-brand-footer">
              <span className="brand-mark"><Icon name="cap" size={20} strokeWidth={2} /></span>
              <span className="site-brand-name">{SITE.name}</span>
            </div>
            <p>{SITE.motto}. Accredited by the National Universities Commission.</p>
            <address>
              {SITE.address.map((line) => <span key={line}>{line}</span>)}
            </address>
          </div>
          <div>
            <h3>The University</h3>
            <Link to="/about">About us</Link>
            <Link to="/faculties">Faculties & Departments</Link>
            <Link to="/programmes">Academic Programmes</Link>
            <Link to="/research">Research</Link>
          </div>
          <div>
            <h3>Students</h3>
            <Link to="/admissions">Admissions</Link>
            <Link to="/library">Library</Link>
            <Link to="/login/student">Student Portal</Link>
            <Link to="/events">Academic calendar & events</Link>
          </div>
          <div>
            <h3>Get in touch</h3>
            <a href={`tel:${SITE.phone.replace(/\s/g, '')}`}>{SITE.phone}</a>
            <a href={`mailto:${SITE.email}`}>{SITE.email}</a>
            <Link to="/contact">Contact form</Link>
            <Link to="/login/staff">Staff Portal</Link>
          </div>
        </div>
        <div className="site-container site-footer-bottom">
          <span>© {new Date().getFullYear()} {SITE.name}. All rights reserved.</span>
          <span className="site-footer-bottom-links">
            <Link to="/news">News & Announcements</Link>
            <Link to="/credits">Photo credits</Link>
          </span>
        </div>
      </footer>
    </div>
  )
}

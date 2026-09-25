import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import api from '../api/client'
import { timeAgo } from '../utils/format'
import Icon from './Icon'

const POLL_MS = 60_000

/** Top-bar bell with an unread count and the latest notifications. */
export default function NotificationBell() {
  const [open, setOpen] = useState(false)
  const [count, setCount] = useState(0)
  const [items, setItems] = useState(null)
  const ref = useRef(null)
  const navigate = useNavigate()

  useEffect(() => {
    let active = true
    const poll = () => api.get('/notifications/unread_count/')
      .then(({ data }) => active && setCount(data.count))
      .catch(() => {})
    poll()
    const timer = setInterval(poll, POLL_MS)
    return () => { active = false; clearInterval(timer) }
  }, [])

  useEffect(() => {
    if (!open) return undefined
    const close = (e) => !ref.current?.contains(e.target) && setOpen(false)
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  const toggle = async () => {
    const next = !open
    setOpen(next)
    if (next) {
      const { data } = await api.get('/notifications/')
      setItems(data.results.slice(0, 6))
    }
  }

  const openItem = async (n) => {
    setOpen(false)
    if (!n.is_read) {
      await api.post(`/notifications/${n.id}/read/`)
      setCount((c) => Math.max(0, c - 1))
    }
    if (n.link) navigate(n.link)
  }

  const markAll = async () => {
    await api.post('/notifications/read_all/')
    setCount(0)
    setItems((list) => list?.map((n) => ({ ...n, is_read: true })))
  }

  return (
    <div className="bell" ref={ref}>
      <button className="icon-btn bell-btn" onClick={toggle} aria-label={`Notifications${count ? `, ${count} unread` : ''}`}>
        <Icon name="bell" size={20} />
        {count > 0 && <span className="bell-count">{count > 9 ? '9+' : count}</span>}
      </button>
      {open && (
        <div className="bell-panel" role="dialog" aria-label="Notifications">
          <div className="bell-head">
            <strong>Notifications</strong>
            {count > 0 && <button className="link" onClick={markAll}>Mark all as read</button>}
          </div>
          {items === null ? (
            <div className="bell-empty muted small">Loading…</div>
          ) : items.length === 0 ? (
            <div className="bell-empty muted small">You're all caught up.</div>
          ) : (
            <ul className="bell-list">
              {items.map((n) => (
                <li key={n.id}>
                  <button className={`bell-item ${n.is_read ? '' : 'is-unread'}`} onClick={() => openItem(n)}>
                    <span className="bell-title">{n.title}</span>
                    <span className="muted small">{n.category_label} · {timeAgo(n.created_at)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <Link to="/portal/notifications" className="bell-all" onClick={() => setOpen(false)}>View all notifications</Link>
        </div>
      )}
    </div>
  )
}

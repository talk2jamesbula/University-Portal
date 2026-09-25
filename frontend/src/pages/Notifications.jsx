import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api, { results } from '../api/client'
import Icon from '../components/Icon'
import { Alert, EmptyState, PageHeader, Spinner } from '../components/ui'
import { formatDateTime, timeAgo } from '../utils/format'
import useApi from '../utils/useApi'

export default function Notifications() {
  const [unreadOnly, setUnreadOnly] = useState(false)
  const { data, loading, error, reload } = useApi('/notifications/', unreadOnly ? { unread: true } : {})
  const navigate = useNavigate()
  const items = results(data)

  const open = async (n) => {
    if (!n.is_read) await api.post(`/notifications/${n.id}/read/`)
    if (n.link) navigate(n.link)
    else reload()
  }

  const markAll = async () => {
    await api.post('/notifications/read_all/')
    reload()
  }

  return (
    <div className="stack-lg">
      <PageHeader
        title="Notifications"
        subtitle="Updates about registration, results, examinations, fees and more"
        actions={<button className="btn btn-ghost" onClick={markAll}><Icon name="check" size={16} /> Mark all as read</button>}
      />
      <div className="chips">
        <button className={`chip ${!unreadOnly ? 'active' : ''}`} onClick={() => setUnreadOnly(false)}>All</button>
        <button className={`chip ${unreadOnly ? 'active' : ''}`} onClick={() => setUnreadOnly(true)}>Unread</button>
      </div>
      {error && <Alert>{error}</Alert>}
      {loading && !data ? <Spinner /> : items.length === 0 ? (
        <EmptyState icon="bell" title={unreadOnly ? 'No unread notifications' : 'No notifications yet'} />
      ) : (
        <div className="card">
          <ul className="notification-list">
            {items.map((n) => (
              <li key={n.id}>
                <button className={`notification ${n.is_read ? '' : 'is-unread'}`} onClick={() => open(n)}>
                  <span className={`dot ${n.is_read ? '' : 'dot-unread'}`} />
                  <span className="grow">
                    <span className="notification-title">{n.title}</span>
                    {n.body && <span className="notification-body">{n.body}</span>}
                    <span className="muted small" title={formatDateTime(n.created_at)}>{n.category_label} · {timeAgo(n.created_at)}</span>
                  </span>
                  {n.link && <Icon name="chevronRight" size={16} className="muted" />}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

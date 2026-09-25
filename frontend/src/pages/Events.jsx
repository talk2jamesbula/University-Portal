import { useState } from 'react'
import { results } from '../api/client'
import Icon from '../components/Icon'
import { Alert, Badge, EmptyState, PageHeader, Spinner } from '../components/ui'
import { CATEGORY_TONE } from '../utils/format'
import useApi from '../utils/useApi'

const CATEGORIES = ['', 'academic', 'career', 'social', 'sports', 'deadline']
const time = (v) => new Date(v).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })

export default function Events() {
  const [category, setCategory] = useState('')
  const { data, loading, error } = useApi('/campus/events/', { upcoming: true, category })
  const events = results(data)

  // Group by month for a calendar-like reading order.
  const groups = events.reduce((acc, e) => {
    const key = new Date(e.starts_at).toLocaleString(undefined, { month: 'long', year: 'numeric' })
    ;(acc[key] ??= []).push(e)
    return acc
  }, {})

  return (
    <div className="stack-lg">
      <PageHeader title="Events" subtitle="What's happening on campus" />
      <div className="chips">
        {CATEGORIES.map((c) => (
          <button key={c} className={`chip ${category === c ? 'active' : ''}`} onClick={() => setCategory(c)}>
            {c ? c[0].toUpperCase() + c.slice(1) : 'All'}
          </button>
        ))}
      </div>
      {error && <Alert>{error}</Alert>}
      {loading && !data ? (
        <Spinner />
      ) : events.length === 0 ? (
        <EmptyState icon="calendar" title="No upcoming events" />
      ) : (
        Object.entries(groups).map(([month, items]) => (
          <section key={month} className="stack">
            <h2 className="section-title">{month}</h2>
            <div className="event-grid">
              {items.map((e) => {
                const d = new Date(e.starts_at)
                return (
                  <article key={e.id} className="event-card">
                    <div className="date-tile date-tile-lg">
                      <span>{d.toLocaleString(undefined, { weekday: 'short' })}</span>
                      <strong>{d.getDate()}</strong>
                    </div>
                    <div className="grow">
                      <Badge tone={CATEGORY_TONE[e.category]}>{e.category}</Badge>
                      <h3>{e.title}</h3>
                      <div className="event-meta">
                        <span><Icon name="clock" size={14} /> {time(e.starts_at)}{e.ends_at ? ` – ${time(e.ends_at)}` : ''}</span>
                        <span><Icon name="pin" size={14} /> {e.location || 'TBA'}</span>
                      </div>
                      {e.description && <p className="muted small">{e.description}</p>}
                    </div>
                  </article>
                )
              })}
            </div>
          </section>
        ))
      )}
    </div>
  )
}

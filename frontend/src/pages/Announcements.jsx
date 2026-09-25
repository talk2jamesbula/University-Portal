import { useState } from 'react'
import api, { errorMessage, results } from '../api/client'
import { can, isStaff, isSuperAdmin } from '../auth/access'
import { useAuth } from '../auth/useAuth'
import Icon from '../components/Icon'
import { Alert, Badge, EmptyState, Modal, PageHeader, Spinner } from '../components/ui'
import { PRIORITY_TONE, formatDateTime, timeAgo } from '../utils/format'
import useApi from '../utils/useApi'

const EMPTY = { title: '', body: '', priority: 'normal', scope: 'course', audience: 'all', offering: '', department: '', pinned: false }

function ComposeModal({ onClose, onCreated }) {
  const { user } = useAuth()
  const broadcaster = can(user, 'communications.send')
  const { data: myCourses } = useApi('/academics/offerings/', { mine: true })
  const { data: departments } = useApi(broadcaster ? '/academics/departments/' : null)
  const [form, setForm] = useState({ ...EMPTY, scope: broadcaster ? 'university' : 'course' })
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      await api.post('/campus/announcements/', {
        title: form.title, body: form.body, priority: form.priority,
        audience: form.scope === 'university' ? form.audience : 'all',
        offering: form.scope === 'course' ? form.offering : null,
        department: form.scope === 'department' ? form.department : null,
        pinned: broadcaster && form.pinned,
      })
      onCreated()
    } catch (err) {
      setError(errorMessage(err))
      setSaving(false)
    }
  }

  return (
    <Modal
      title="New announcement"
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" form="compose" disabled={saving}>{saving ? 'Posting…' : 'Post'}</button>
        </>
      }
    >
      <form id="compose" className="form" onSubmit={submit}>
        <Alert>{error}</Alert>
        <label className="field"><span>Title</span><input value={form.title} onChange={set('title')} required maxLength={200} /></label>
        <label className="field"><span>Message</span><textarea rows={5} value={form.body} onChange={set('body')} required /></label>
        <div className="form-row">
          <label className="field">
            <span>Send to</span>
            <select value={form.scope} onChange={set('scope')} disabled={!broadcaster}>
              {broadcaster && <option value="university">The university</option>}
              {broadcaster && <option value="department">A department</option>}
              <option value="course">Students in one of my courses</option>
            </select>
          </label>
          <label className="field">
            <span>Priority</span>
            <select value={form.priority} onChange={set('priority')}>
              <option value="normal">Normal</option>
              <option value="important">Important</option>
              <option value="urgent">Urgent</option>
            </select>
          </label>
        </div>
        {form.scope === 'course' && (
          <label className="field"><span>Course</span>
            <select value={form.offering} onChange={set('offering')} required>
              <option value="">Select a course</option>
              {results(myCourses).map((c) => <option key={c.id} value={c.id}>{c.code} · {c.title}</option>)}
            </select>
          </label>
        )}
        {form.scope === 'department' && (
          <label className="field"><span>Department</span>
            <select value={form.department} onChange={set('department')} required>
              <option value="">Select a department</option>
              {departments?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </label>
        )}
        {form.scope === 'university' && (
          <div className="form-row">
            <label className="field"><span>Audience</span>
              <select value={form.audience} onChange={set('audience')}>
                <option value="all">Everyone</option>
                <option value="student">Students</option>
                <option value="staff">Staff</option>
              </select>
            </label>
            <label className="checkbox"><input type="checkbox" checked={form.pinned} onChange={set('pinned')} /> Pin to top</label>
          </div>
        )}
      </form>
    </Modal>
  )
}

export default function Announcements() {
  const { user } = useAuth()
  const [priority, setPriority] = useState('')
  const [composing, setComposing] = useState(false)
  const [expanded, setExpanded] = useState(null)
  const { data, loading, error, reload } = useApi('/campus/announcements/', { priority })
  const items = results(data)

  return (
    <div className="stack-lg">
      <PageHeader
        title="Announcements"
        subtitle="University, department and course announcements"
        actions={(isStaff(user) || isSuperAdmin(user)) && (
          <button className="btn btn-primary" onClick={() => setComposing(true)}><Icon name="plus" size={16} /> New announcement</button>
        )}
      />

      <div className="tabs" role="tablist">
        {[['', 'All'], ['urgent', 'Urgent'], ['important', 'Important'], ['normal', 'General']].map(([value, label]) => (
          <button key={value} role="tab" aria-selected={priority === value} className={`tab ${priority === value ? 'active' : ''}`} onClick={() => setPriority(value)}>
            {label}
          </button>
        ))}
      </div>

      {error && <Alert>{error}</Alert>}
      {loading && !data ? (
        <Spinner />
      ) : items.length === 0 ? (
        <EmptyState icon="megaphone" title="No announcements" />
      ) : (
        <div className="stack">
          {items.map((a) => (
            <article key={a.id} className={`announcement priority-${a.priority}`}>
              <div className="announcement-head">
                <div className="grow">
                  <div className="announcement-tags">
                    {a.pinned && <Badge tone="blue"><Icon name="pinned" size={12} /> Pinned</Badge>}
                    {a.priority !== 'normal' && <Badge tone={PRIORITY_TONE[a.priority]}>{a.priority}</Badge>}
                    <Badge>{a.course_code || a.department_name || (a.audience === 'all' ? 'University-wide' : a.audience === 'student' ? 'Students' : 'Staff')}</Badge>
                  </div>
                  <h3>{a.title}</h3>
                  <div className="list-meta" title={formatDateTime(a.created_at)}>
                    {a.author_name || 'University Administration'} · {timeAgo(a.created_at)}
                  </div>
                </div>
              </div>
              <p className={expanded === a.id ? '' : 'clamp'}>{a.body}</p>
              {a.body.length > 220 && (
                <button className="link" onClick={() => setExpanded(expanded === a.id ? null : a.id)}>
                  {expanded === a.id ? 'Show less' : 'Read more'}
                </button>
              )}
            </article>
          ))}
        </div>
      )}

      {composing && <ComposeModal onClose={() => setComposing(false)} onCreated={() => { setComposing(false); reload() }} />}
    </div>
  )
}

import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import api, { errorMessage } from '../../api/client'
import { isSuperAdmin } from '../../auth/access'
import { useAuth } from '../../auth/useAuth'
import Icon from '../../components/Icon'
import { Alert, Badge, Card, EmptyState, Modal, PageHeader, Spinner, Stat } from '../../components/ui'
import { formatDate, formatTime, localToday } from '../../utils/format'
import useApi from '../../utils/useApi'
import { SESSION_TONE, formatPercent } from './attendance'
import PercentBar from './PercentBar'
import UploadRegisterModal from './UploadRegisterModal'

function NewSessionModal({ offering, onClose, onCreated }) {
  const [form, setForm] = useState({
    date: localToday(),
    start_time: offering.start_time?.slice(0, 5) || '08:00',
    topic: '',
    checkin_minutes: 15,
    late_after_minutes: 10,
  })
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value })

  const save = async (e, startNow) => {
    e?.preventDefault()
    setSaving(true)
    setError('')
    try {
      const { data } = await api.post('/attendance/sessions/', { ...form, offering: offering.id })
      if (startNow) await api.post(`/attendance/sessions/${data.id}/open/`)
      onCreated(data)
    } catch (err) {
      setError(errorMessage(err))
      setSaving(false)
    }
  }

  const isToday = form.date === localToday()
  return (
    <Modal
      title={`New attendance session · ${offering.code}`}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-ghost" form="session-form" disabled={saving}>Save for later</button>
          {isToday && (
            <button className="btn btn-primary" disabled={saving} onClick={(e) => save(e, true)}>
              <Icon name="qr" size={15} /> {saving ? 'Starting…' : 'Create and start'}
            </button>
          )}
        </>
      }
    >
      <form id="session-form" className="form" onSubmit={(e) => save(e, false)}>
        <Alert>{error}</Alert>
        <div className="form-row">
          <label className="field"><span>Date</span><input type="date" value={form.date} onChange={set('date')} required /></label>
          <label className="field"><span>Start time</span><input type="time" value={form.start_time} onChange={set('start_time')} required /></label>
        </div>
        <label className="field"><span>Topic (optional)</span><input value={form.topic} onChange={set('topic')} maxLength={200} placeholder="e.g. Week 3: Linked lists" /></label>
        <div className="form-row">
          <label className="field">
            <span>Check-in open for (minutes)</span>
            <input type="number" min="1" max="180" value={form.checkin_minutes} onChange={set('checkin_minutes')} required />
          </label>
          <label className="field">
            <span>Late after (minutes)</span>
            <input type="number" min="0" max="180" value={form.late_after_minutes} onChange={set('late_after_minutes')} required />
          </label>
        </div>
        <p className="muted small">
          Students check in by scanning the QR code or typing the 6-digit code during the check-in window. Anyone who
          checks in after the late threshold is marked late. When you close the session, everyone else is marked absent.
        </p>
      </form>
    </Modal>
  )
}

/** A lecturer's (or HOD's) view of attendance for one course: sessions held and each student's percentage. */
export default function CourseAttendance() {
  const { id } = useParams()
  const { user } = useAuth()
  const navigate = useNavigate()
  const [tab, setTab] = useState('sessions')
  const [creating, setCreating] = useState(false)
  const [uploading, setUploading] = useState(false)
  const { data: offering, error: offeringError } = useApi(`/academics/offerings/${id}/`)
  const { data: sessions, error: sessionsError, reload: reloadSessions } = useApi('/attendance/sessions/', { offering: id })
  const { data: stats, error: statsError, reload: reloadStats } = useApi(`/attendance/offerings/${id}/stats/`)

  const error = offeringError || sessionsError || statsError
  if (error) return <Alert>{error}</Alert>
  if (!offering || !sessions || !stats) return <Spinner />

  const { summary } = stats
  const minimum = stats.minimum_percent
  const mine = offering.lecturer === user.id || isSuperAdmin(user)

  return (
    <div className="stack-lg">
      <button onClick={() => navigate(-1)} className="back-link"><Icon name="arrowLeft" size={16} /> Back</button>
      <PageHeader
        title={`Attendance · ${offering.code}`}
        subtitle={`${offering.title} · ${offering.semester_name}`}
        actions={mine && (
          <>
            <button className="btn btn-ghost" onClick={() => setUploading(true)}><Icon name="register" size={16} /> Upload register</button>
            <button className="btn btn-primary" onClick={() => setCreating(true)}><Icon name="plus" size={16} /> New session</button>
          </>
        )}
      />
      <div className="stats-grid">
        <Stat icon="calendar" label="Sessions held" value={summary.sessions_held} />
        <Stat icon="check" label="Average attendance" value={formatPercent(summary.average_percent)} tone="green" />
        <Stat icon="users" label="Registered students" value={summary.students} tone="purple" />
        <Stat icon="alert" label={`Below ${minimum}%`} value={summary.at_risk} tone={summary.at_risk ? 'red' : 'green'} />
      </div>

      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === 'sessions'} className={`tab ${tab === 'sessions' ? 'active' : ''}`} onClick={() => setTab('sessions')}>
          Sessions ({sessions.length})
        </button>
        <button role="tab" aria-selected={tab === 'students'} className={`tab ${tab === 'students' ? 'active' : ''}`} onClick={() => setTab('students')}>
          Students ({stats.students.length})
        </button>
      </div>

      {tab === 'sessions' ? (
        sessions.length === 0 ? (
          <EmptyState icon="qr" title="No attendance sessions yet">
            {mine ? 'Create a session at the start of each class.' : 'The lecturer has not recorded attendance yet.'}
          </EmptyState>
        ) : (
          <Card padded={false}>
            <table className="table table-clickable">
              <thead>
                <tr><th>Date</th><th>Time</th><th>Topic</th><th>Status</th><th className="num">Attended</th><th /></tr>
              </thead>
              <tbody>
                {sessions.map((s) => (
                  <tr key={s.id} onClick={() => navigate(`/portal/attendance/sessions/${s.id}`)}>
                    <td className="cell-title">{formatDate(s.date, { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })}</td>
                    <td>{formatTime(s.start_time)}</td>
                    <td>{s.topic || <span className="muted">—</span>}</td>
                    <td><Badge tone={SESSION_TONE[s.status]}>{s.status_label}</Badge></td>
                    <td className="num">{s.status === 'scheduled' ? '—' : `${s.attended_count} / ${s.status === 'closed' ? s.record_count : summary.students}`}</td>
                    <td className="align-right nowrap">
                      {mine && s.status !== 'closed' && s.date === localToday() && (
                        <Link to={`/portal/attendance/sessions/${s.id}`} onClick={(e) => e.stopPropagation()} className="btn btn-primary btn-sm">
                          <Icon name="qr" size={14} /> {s.status === 'open' ? 'Show QR code' : 'Start'}
                        </Link>
                      )}{' '}
                      <Link to={`/portal/attendance/sessions/${s.id}`} onClick={(e) => e.stopPropagation()} aria-label="Open session"><Icon name="chevronRight" size={16} /></Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )
      ) : (
        <Card padded={false}>
          {stats.students.length === 0 ? <EmptyState icon="users" title="No students registered" /> : (
            <table className="table">
              <thead>
                <tr>
                  <th>Student</th><th>Matric no.</th><th className="num">Present</th><th className="num">Late</th>
                  <th className="num">Excused</th><th className="num">Absent</th><th>Attendance</th>
                </tr>
              </thead>
              <tbody>
                {stats.students.map((s) => (
                  <tr key={s.student}>
                    <td className="cell-title">{s.student_name} {s.at_risk && <Badge tone="red">Below {minimum}%</Badge>}</td>
                    <td className="mono">{s.matric_number}</td>
                    <td className="num">{s.present}</td>
                    <td className="num">{s.late}</td>
                    <td className="num">{s.excused}</td>
                    <td className="num">{s.absent}</td>
                    <td><PercentBar value={s.percent} minimum={minimum} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      )}

      {uploading && (
        <UploadRegisterModal
          offering={offering}
          onClose={() => setUploading(false)}
          onSaved={() => { reloadSessions(); reloadStats() }}
        />
      )}
      {creating && (
        <NewSessionModal
          offering={offering}
          onClose={() => setCreating(false)}
          onCreated={(session) => navigate(`/portal/attendance/sessions/${session.id}`)}
        />
      )}
    </div>
  )
}

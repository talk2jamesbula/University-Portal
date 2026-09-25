import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import api, { errorMessage } from '../../api/client'
import Icon from '../../components/Icon'
import { Alert, Badge, Card, EmptyState, Modal, PageHeader, Spinner } from '../../components/ui'
import { formatClock, formatDate, formatDateTime, formatTime, localToday } from '../../utils/format'
import useApi from '../../utils/useApi'
import { SESSION_TONE, STATUS_LABEL, STATUS_OPTIONS, STATUS_TONE } from './attendance'

/**
 * The rotating QR code for the lecturer's screen. It re-fetches when the code rotates and every
 * few seconds in between, so the live check-in count stays current.
 */
function LiveQr({ sessionId, onCount, onEnded }) {
  const [qr, setQr] = useState(null)
  const [error, setError] = useState('')
  const [now, setNow] = useState(() => Date.now())
  const [presenting, setPresenting] = useState(false)

  useEffect(() => {
    let timer
    let active = true
    const poll = async () => {
      try {
        const { data } = await api.get(`/attendance/sessions/${sessionId}/qr/`)
        if (!active) return
        setError('')
        setQr({ ...data, expiresAt: Date.now() + (data.seconds_left ?? 0) * 1000 })
        if (!data.accepting) return onEnded()
        onCount(data.checked_in)
        timer = setTimeout(poll, Math.min(data.seconds_left, 4) * 1000 + 150)
      } catch (err) {
        if (!active) return
        setError(errorMessage(err))
        timer = setTimeout(poll, 5000)
      }
    }
    poll()
    return () => { active = false; clearTimeout(timer) }
  }, [sessionId, onCount, onEnded])

  useEffect(() => {
    const tick = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(tick)
  }, [])

  useEffect(() => {
    if (!presenting) return undefined
    const onKey = (e) => e.key === 'Escape' && setPresenting(false)
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [presenting])

  if (error && !qr) return <Alert>{error}</Alert>
  if (!qr) return <Spinner label="Generating QR code…" />
  if (!qr.accepting) {
    return (
      <div className="callout">
        <Icon name="clock" />
        <span>The check-in window has closed. Mark any remaining students by hand, then close the session.</span>
      </div>
    )
  }

  const secondsLeft = Math.max(0, Math.ceil((qr.expiresAt - now) / 1000))
  const panel = (
    <div className={`qr-panel ${presenting ? 'qr-presenting' : ''}`}>
      <div className="qr-image">
        <img src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(qr.svg)}`} alt="Attendance QR code" />
      </div>
      <div className="qr-side">
        <p className="eyebrow">Or enter this code</p>
        <div className="qr-code mono" aria-live="polite">{qr.code.slice(0, 3)} {qr.code.slice(3)}</div>
        <p className="muted small">Changes in {secondsLeft}s · check-in closes at {formatClock(qr.checkin_closes_at)}</p>
        <div className="qr-count"><strong>{qr.checked_in}</strong> of {qr.registered} checked in</div>
        {presenting
          ? <button className="btn btn-ghost" onClick={() => setPresenting(false)}><Icon name="close" size={16} /> Exit full screen</button>
          : <button className="btn btn-ghost" onClick={() => setPresenting(true)}><Icon name="qr" size={16} /> Show on projector</button>}
      </div>
    </div>
  )
  return presenting ? <div className="qr-stage" role="dialog" aria-label="Attendance QR code">{panel}</div> : panel
}

function CorrectionModal({ row, onClose, onDone }) {
  const current = row.record.status
  const [toStatus, setToStatus] = useState(STATUS_OPTIONS.find(([v]) => v !== current)[0])
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      await api.post(`/attendance/records/${row.record.id}/correction/`, { to_status: toStatus, reason })
      onDone(`Correction for ${row.student_name} sent for approval.`)
    } catch (err) {
      setError(errorMessage(err))
      setSaving(false)
    }
  }

  return (
    <Modal
      title="Request attendance correction"
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" form="correction-form" disabled={saving}>{saving ? 'Sending…' : 'Send for approval'}</button>
        </>
      }
    >
      <form id="correction-form" className="form" onSubmit={submit}>
        <Alert>{error}</Alert>
        <p className="muted">
          This session is closed, so changes need approval from your Head of Department. <strong className="text-strong">{row.student_name}</strong> is
          currently marked <Badge tone={STATUS_TONE[current]}>{row.record.status_label}</Badge>.
        </p>
        <label className="field">
          <span>Change to</span>
          <select value={toStatus} onChange={(e) => setToStatus(e.target.value)}>
            {STATUS_OPTIONS.filter(([v]) => v !== current).map(([v, label]) => <option key={v} value={v}>{label}</option>)}
          </select>
        </label>
        <label className="field">
          <span>Reason</span>
          <textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} minLength={5} maxLength={300} required
                    placeholder="e.g. Student presented a medical certificate" />
        </label>
      </form>
    </Modal>
  )
}

/** One attendance session: run check-in, mark students by hand, and request corrections once closed. */
export default function SessionDetail() {
  const { id } = useParams()
  const { data: session, loading, error, reload } = useApi(`/attendance/sessions/${id}/`)
  const [notice, setNotice] = useState({ tone: 'success', text: '' })
  const [busy, setBusy] = useState(null)
  const [correcting, setCorrecting] = useState(null)
  const [query, setQuery] = useState('')
  const lastCount = useRef(null)

  // Refresh the class list when new check-ins arrive.
  const onCount = useCallback((count) => {
    if (lastCount.current !== null && lastCount.current !== count) reload()
    lastCount.current = count
  }, [reload])

  if (loading && !session) return <Spinner />
  if (error && !session) return <Alert>{error}</Alert>

  const act = async (key, request, success) => {
    setBusy(key)
    try {
      await request()
      if (success) setNotice({ tone: 'success', text: success })
      reload()
    } catch (err) {
      setNotice({ tone: 'error', text: errorMessage(err) })
    } finally {
      setBusy(null)
    }
  }

  const start = () => act('open', () => api.post(`/attendance/sessions/${id}/open/`), 'Check-in has started. Show the QR code to the class.')
  const close = () => {
    const missing = session.roster.filter((r) => !r.record).length
    if (missing && !window.confirm(`Close this session? ${missing} student${missing === 1 ? '' : 's'} without a record will be marked absent and notified.`)) return
    act('close', () => api.post(`/attendance/sessions/${id}/close/`), 'Session closed. Absent students have been notified.')
  }
  const mark = (row, status) =>
    act(`mark-${row.student}`, () => api.post(`/attendance/sessions/${id}/mark/`, { student: row.student, status }))

  const isOpen = session.status === 'open'
  const isClosed = session.status === 'closed'
  const today = localToday()
  const isToday = session.date === today
  const canMark = session.can_mark && !isClosed
  const records = session.roster.map((r) => r.record).filter(Boolean)
  const counts = Object.fromEntries(STATUS_OPTIONS.map(([v]) => [v, records.filter((r) => r.status === v).length]))
  const flagged = records.filter((r) => r.flagged).length
  const q = query.toLowerCase()
  const rows = session.roster.filter((r) => !q || `${r.student_name} ${r.matric_number}`.toLowerCase().includes(q))

  return (
    <div className="stack-lg">
      <Link to={`/portal/teaching/${session.offering}/attendance`} className="back-link"><Icon name="arrowLeft" size={16} /> {session.course_code} attendance</Link>
      <PageHeader
        title={`${session.course_code} · ${formatDate(session.date, { weekday: 'long', day: 'numeric', month: 'long' })}`}
        subtitle={`${session.course_title} · ${formatTime(session.start_time)}${session.topic ? ` · ${session.topic}` : ''}`}
        actions={
          <>
            <Badge tone={SESSION_TONE[session.status]}>{session.status_label}</Badge>
            {session.can_mark && session.status === 'scheduled' && isToday && (
              <button className="btn btn-primary" onClick={start} disabled={busy === 'open'}><Icon name="qr" size={16} /> Start attendance</button>
            )}
            {session.can_mark && (isOpen || (session.status === 'scheduled' && session.date <= today)) && (
              <button className="btn btn-danger-ghost" onClick={close} disabled={busy === 'close'}>{busy === 'close' ? 'Closing…' : 'Close session'}</button>
            )}
          </>
        }
      />
      <Alert tone={notice.tone} onClose={() => setNotice({ ...notice, text: '' })}>{notice.text}</Alert>
      {session.can_mark && session.status === 'scheduled' && !isToday && (
        <div className="callout">
          <Icon name="calendar" />
          <span>
            {session.date > today
              ? 'QR check-in can be started on the day of the class.'
              : 'This class has passed. Mark each student by hand, then close the session to record everyone else as absent.'}
          </span>
        </div>
      )}

      {session.can_mark && session.status === 'scheduled' && isToday && (
        <Card>
          <div className="qr-placeholder">
            <div className="qr-placeholder-box"><Icon name="qr" size={72} strokeWidth={1.2} /></div>
            <div className="qr-side">
              <h2>Ready to take attendance</h2>
              <p className="muted">
                Start attendance to show the QR code and 6-digit code here. Students scan it from their phones, or open
                <strong className="text-strong"> Attendance → Scan QR code</strong> in the portal.
              </p>
              <button className="btn btn-primary btn-lg" onClick={start} disabled={busy === 'open'}>
                <Icon name="qr" size={18} /> {busy === 'open' ? 'Starting…' : 'Start attendance and show QR code'}
              </button>
            </div>
          </div>
        </Card>
      )}
      {!session.can_mark && isOpen && (
        <div className="callout callout-info">
          <Icon name="qr" />
          <span>Check-in is open. The QR code is shown on the course lecturer's screen.</span>
        </div>
      )}

      {session.can_mark && isOpen && (
        <Card>
          <LiveQr sessionId={session.id} onCount={onCount} onEnded={reload} />
        </Card>
      )}

      <div className="stats-inline">
        {STATUS_OPTIONS.map(([v, label]) => <div key={v}><strong>{counts[v]}</strong><span>{label}</span></div>)}
        <div><strong>{session.roster.length - records.length}</strong><span>Not yet marked</span></div>
        {flagged > 0 && <div><strong className="text-red">{flagged}</strong><span>Flagged</span></div>}
      </div>

      <Card
        title="Class list"
        padded={false}
        action={
          <label className="search search-sm">
            <Icon name="search" size={16} />
            <input placeholder="Filter by name or matric no." value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Filter students" />
          </label>
        }
      >
        {rows.length === 0 ? <EmptyState icon="users" title={session.roster.length ? 'No matching students' : 'No students registered'} /> : (
          <table className="table">
            <thead>
              <tr><th>Student</th><th>Matric no.</th><th>Status</th><th>Recorded</th><th className="align-right">{canMark ? 'Mark' : ''}</th></tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.student}>
                  <td className="cell-title">{r.student_name}</td>
                  <td className="mono">{r.matric_number}</td>
                  <td>
                    {r.record ? <Badge tone={STATUS_TONE[r.record.status]}>{r.record.status_label}</Badge> : <span className="muted">Not marked</span>}
                    {r.record?.flagged && <span className="flag" title={r.record.flag_reason}><Icon name="alert" size={14} /> Flagged</span>}
                    {r.record?.pending_correction && <div className="muted small">Correction to {STATUS_LABEL[r.record.pending_correction.to_status]} awaiting approval</div>}
                  </td>
                  <td className="muted small">{r.record ? <>{r.record.method_label} · {formatDateTime(r.record.marked_at)}</> : '—'}</td>
                  <td className="align-right">
                    {canMark && (
                      <div className="seg" role="group" aria-label={`Mark ${r.student_name}`}>
                        {STATUS_OPTIONS.map(([v, label]) => (
                          <button key={v} className={`seg-btn ${r.record?.status === v ? `active seg-${v}` : ''}`}
                                  disabled={busy === `mark-${r.student}`} onClick={() => mark(r, v)} title={label}>
                            {label}
                          </button>
                        ))}
                      </div>
                    )}
                    {session.can_mark && isClosed && r.record && !r.record.pending_correction && (
                      <button className="btn btn-ghost btn-sm" onClick={() => setCorrecting(r)}>Request correction</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {correcting && (
        <CorrectionModal
          row={correcting}
          onClose={() => setCorrecting(null)}
          onDone={(text) => { setCorrecting(null); setNotice({ tone: 'success', text }); reload() }}
        />
      )}
    </div>
  )
}

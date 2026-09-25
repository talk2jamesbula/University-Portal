import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import api, { blobErrorMessage, downloadFile, errorMessage } from '../../api/client'
import { can, isSuperAdmin } from '../../auth/access'
import { useAuth } from '../../auth/useAuth'
import Icon from '../../components/Icon'
import { Alert, Avatar, Badge, Card, EmptyState, Modal, PageHeader, Spinner, Stat } from '../../components/ui'
import { formatClock, formatDate, formatDateTime, formatTime } from '../../utils/format'
import useApi from '../../utils/useApi'
import { formatPercent } from '../attendance/attendance'
import { formatScore } from '../results/results'
import ExamFormModal from './ExamFormModal'
import { ATTEMPT_TONE, EXAM_STATUS_TONE, MODE_TONE, formatDuration } from './exams'
import Questions from './Questions'

function WaiverModal({ exam, row, onClose, onSaved }) {
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const waiving = !row.waived

  const save = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      await api.post(`/exams/timetable/${exam.id}/waive/`, { student: row.student.id, waived: waiving, reason })
      onSaved()
    } catch (err) {
      setError(errorMessage(err))
      setSaving(false)
    }
  }

  return (
    <Modal
      title={waiving ? `Let ${row.student.name} sit ${exam.code}` : `Remove ${row.student.name}'s waiver`}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className={`btn ${waiving ? 'btn-primary' : 'btn-danger'}`} form="waiver-form" disabled={saving}>
            {waiving ? 'Grant waiver' : 'Remove waiver'}
          </button>
        </>
      }
    >
      <form id="waiver-form" className="form" onSubmit={save}>
        <Alert>{error}</Alert>
        {row.reasons.length > 0 && <p className="muted">{row.reasons.join(' ')}</p>}
        {waiving ? (
          <label className="field">
            <span>Reason (recorded in the audit log)</span>
            <textarea rows={2} value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} required
                      placeholder="e.g. Medical report from the University Health Centre" />
          </label>
        ) : <p>The student will again need to meet the attendance and fees rules to sit this exam.</p>}
      </form>
    </Modal>
  )
}

function Candidates({ exam }) {
  const { data, error, reload } = useApi(`/exams/timetable/${exam.id}/candidates/`)
  const [filter, setFilter] = useState('all')
  const [waiver, setWaiver] = useState(null)
  const [cardError, setCardError] = useState('')

  if (error && !data) return <Alert>{error}</Alert>
  if (!data) return <Spinner />

  const counts = {
    all: data.rows.length,
    eligible: data.rows.filter((r) => r.eligible).length,
    blocked: data.rows.filter((r) => !r.eligible).length,
    waived: data.rows.filter((r) => r.waived).length,
  }
  const rows = data.rows.filter((r) => filter === 'all' || (filter === 'eligible' ? r.eligible : filter === 'blocked' ? !r.eligible : r.waived))
  const card = async (row) => {
    setCardError('')
    try {
      await downloadFile(`/exams/cards/${row.student.id}/`, { semester: exam.semester }, 'exam-card.pdf')
    } catch (err) {
      setCardError(await blobErrorMessage(err))
    }
  }

  return (
    <div className="stack">
      <Alert onClose={() => setCardError('')}>{cardError}</Alert>
      <div className="status-chips">
        {[['all', 'All candidates'], ['eligible', 'Eligible'], ['blocked', 'Not eligible'], ['waived', 'Waivers']].map(([key, label]) => (
          <button key={key} className={`status-chip ${filter === key ? 'active' : ''} ${key === 'blocked' && counts.blocked ? 'tone-chip-red' : ''}`} onClick={() => setFilter(key)}>
            <strong>{counts[key]}</strong>{label}
          </button>
        ))}
      </div>
      <Card padded={false}>
        {rows.length === 0 ? <EmptyState icon="users" title="No candidates here" /> : (
          <table className="table">
            <thead>
              <tr><th>Candidate</th><th className="num">Attendance</th><th>Eligibility</th><th>Seat</th><th>{exam.mode === 'cbt' ? 'Paper' : 'Checked in'}</th><th /></tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.student.id}>
                  <td>
                    <div className="person">
                      <Avatar name={r.student.name} src={r.student.avatar_url} size={32} />
                      <div><div className="cell-title">{r.student.name}</div><div className="muted small mono">{r.student.matric_number}</div></div>
                    </div>
                  </td>
                  <td className={`num ${r.attendance_percent != null && r.attendance_percent < data.minimum_percent ? 'text-red' : ''}`}>{formatPercent(r.attendance_percent)}</td>
                  <td>
                    {r.eligible ? <Badge tone={r.waived ? 'blue' : 'green'}>{r.waived ? 'Waiver' : 'Eligible'}</Badge> : <Badge tone="red">Not eligible</Badge>}
                    {r.reasons.length > 0 && <div className="muted small">{r.reasons.join(' ')}</div>}
                    {r.waiver_reason && <div className="muted small">Waiver: {r.waiver_reason}</div>}
                  </td>
                  <td className="small">{r.venue ? <>{r.venue} · <strong>{r.seat_number}</strong></> : <span className="muted">No seat</span>}</td>
                  <td className="small">
                    {exam.mode === 'cbt'
                      ? (r.attempt_status ? <Badge tone={ATTEMPT_TONE[r.attempt_status]}>{r.attempt_status.replace('_', ' ')}</Badge> : <span className="muted">Not started</span>)
                      : (r.checked_in_at ? formatClock(r.checked_in_at) : <span className="muted">—</span>)}
                  </td>
                  <td className="align-right nowrap">
                    {data.can_waive && (r.waived || !r.eligible) && (
                      <button className="link-button" onClick={() => setWaiver(r)}>{r.waived ? 'Remove waiver' : 'Waive'}</button>
                    )}
                    {data.can_waive && r.eligible && exam.status === 'published' && (
                      <button className="icon-btn" onClick={() => card(r)} aria-label={`Exam card for ${r.student.name}`} title="Exam card"><Icon name="printer" size={16} /></button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      {waiver && <WaiverModal exam={exam} row={waiver} onClose={() => setWaiver(null)} onSaved={() => { setWaiver(null); reload() }} />}
    </div>
  )
}

function Attempts({ exam, canRelease }) {
  const { data: attempts, error, reload } = useApi(`/exams/timetable/${exam.id}/attempts/`)
  const [releasing, setReleasing] = useState(false)
  const [result, setResult] = useState({ text: '', tone: 'success' })

  if (error && !attempts) return <Alert>{error}</Alert>
  if (!attempts) return <Spinner />

  const release = async () => {
    setResult({ text: '' })
    try {
      const { data } = await api.post(`/exams/timetable/${exam.id}/release-scores/`)
      setResult({
        tone: 'success',
        text: `Sent ${data.released} score${data.released === 1 ? '' : 's'} to the result sheet.${data.absent ? ` ${data.absent} registered student${data.absent === 1 ? '' : 's'} didn't sit the exam: enter their scores by hand.` : ''}`,
      })
      reload()
    } catch (err) {
      setResult({ tone: 'error', text: errorMessage(err) })
    } finally {
      setReleasing(false)
    }
  }
  const flagged = attempts.filter((a) => a.flagged).length

  return (
    <div className="stack">
      <Alert tone={result.tone} onClose={() => setResult({ text: '' })}>{result.text}</Alert>
      {flagged > 0 && (
        <div className="callout callout-danger">
          <Icon name="alert" /><span>{flagged} candidate{flagged === 1 ? '' : 's'} left the exam page several times. Review before releasing scores.</span>
        </div>
      )}
      <Card
        title={`Submitted papers (${attempts.filter((a) => a.status !== 'in_progress').length} of ${attempts.length} started)`}
        padded={false}
        action={canRelease && (
          <span className="row-actions">
            <Link to={`/portal/results/sheets/${exam.offering}`} className="btn btn-ghost btn-sm">Result sheet</Link>
            <button className="btn btn-primary btn-sm" onClick={() => setReleasing(true)} disabled={!attempts.length}>Send scores to result sheet</button>
          </span>
        )}
      >
        {attempts.length === 0 ? <EmptyState icon="register" title="Nobody has started this exam yet" /> : (
          <table className="table">
            <thead>
              <tr><th>Candidate</th><th>Status</th><th>Started</th><th className="num">Answered</th><th className="num">Marks</th><th className="num">Score /70</th><th className="num">Left page</th></tr>
            </thead>
            <tbody>
              {attempts.map((a) => (
                <tr key={a.id}>
                  <td><div className="cell-title">{a.student_name}</div><div className="muted small mono">{a.matric_number}</div></td>
                  <td><Badge tone={ATTEMPT_TONE[a.status]}>{a.status_label}</Badge></td>
                  <td className="small">{formatDateTime(a.started_at)}</td>
                  <td className="num">{a.answered}</td>
                  <td className="num">{a.score == null ? '—' : `${formatScore(a.score)} / ${a.max_score}`}</td>
                  <td className="num strong">{formatScore(a.scaled_score)}</td>
                  <td className="num">{a.focus_losses}{a.flagged && <span className="flag" title="Left the exam page several times"><Icon name="alert" size={13} /></span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      {releasing && (
        <Modal
          title="Send CBT scores to the result sheet?"
          onClose={() => setReleasing(false)}
          footer={<><button className="btn btn-ghost" onClick={() => setReleasing(false)}>Cancel</button><button className="btn btn-primary" onClick={release}>Send scores</button></>}
        >
          <p>Each candidate's marks are scaled to 70 and entered as their examination score. You can still review the sheet before submitting it to the HOD.</p>
        </Modal>
      )}
    </div>
  )
}

/** One exam: candidates and eligibility, seating, and (for CBT) the questions and submitted papers. */
export function ExamDetailView({ examId }) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const { data: exam, error, reload, setData } = useApi(`/exams/timetable/${examId}/`)
  const [tab, setTab] = useState('candidates')
  const [editing, setEditing] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [notice, setNotice] = useState({ text: '', tone: 'success' })
  const [version, setVersion] = useState(0)

  if (error && !exam) return <Alert>{error}</Alert>
  if (!exam) return <Spinner />

  const manager = can(user, 'exams.manage')
  const setter = exam.lecturer === user.id || isSuperAdmin(user)
  const cbt = exam.mode === 'cbt'
  const tabs = [['candidates', 'Candidates'], ...(cbt && setter ? [['questions', 'Questions']] : []), ...(cbt ? [['attempts', 'Submitted papers']] : [])]

  const allocate = async () => {
    setNotice({ text: '' })
    try {
      const { data } = await api.post(`/exams/timetable/${exam.id}/allocate-seats/`)
      setData(data.exam)
      setVersion((v) => v + 1)
      setNotice({ tone: 'success', text: data.seated ? `Gave seats to ${data.seated} student${data.seated === 1 ? '' : 's'}.` : 'Everyone already has a seat.' })
    } catch (err) {
      setNotice({ tone: 'error', text: errorMessage(err) })
    }
  }
  const remove = async () => {
    try {
      await api.delete(`/exams/timetable/${exam.id}/`)
      navigate('/portal/manage/exams')
    } catch (err) {
      setConfirmDelete(false)
      setNotice({ tone: 'error', text: errorMessage(err) })
    }
  }

  return (
    <div className="stack-lg">
      <button onClick={() => navigate(-1)} className="back-link"><Icon name="arrowLeft" size={16} /> Back</button>
      <PageHeader
        title={`${exam.code} examination`}
        subtitle={`${exam.title} · ${formatDate(exam.date, { weekday: 'long', day: 'numeric', month: 'long' })}, ${formatTime(exam.start_time)} · ${formatDuration(exam.duration_minutes)}`}
        actions={manager && (
          <>
            {exam.status === 'draft' && <button className="btn btn-danger-ghost" onClick={() => setConfirmDelete(true)}>Delete</button>}
            <button className="btn btn-ghost" onClick={allocate}><Icon name="users" size={16} /> Allocate seats</button>
            <button className="btn btn-primary" onClick={() => setEditing(true)}>Edit</button>
          </>
        )}
      />
      <div className="row-actions">
        <Badge tone={EXAM_STATUS_TONE[exam.status]}>{exam.status_label}</Badge>
        <Badge tone={MODE_TONE[exam.mode]}>{exam.mode_label}</Badge>
        <span className="muted small">{exam.venue_details.map((v) => `${v.name} (${v.capacity})`).join(' · ') || 'No venue yet'}</span>
      </div>
      <Alert tone={notice.tone} onClose={() => setNotice({ text: '' })}>{notice.text}</Alert>
      <div className="stats-grid">
        <Stat icon="users" label="Registered students" value={exam.registered_count} />
        <Stat icon="pin" label="Seated" value={`${exam.seated_count} / ${exam.registered_count}`} tone={exam.seated_count < exam.registered_count ? 'amber' : 'green'} />
        <Stat icon="building" label="Seats in venues" value={exam.venue_details.reduce((sum, v) => sum + v.capacity, 0)} tone="purple" />
        {cbt && <Stat icon="register" label="Questions" value={exam.question_count} tone={exam.question_count ? 'green' : 'red'} />}
      </div>
      <div className="tabs" role="tablist">
        {tabs.map(([key, label]) => (
          <button key={key} role="tab" aria-selected={tab === key} className={`tab ${tab === key ? 'active' : ''}`} onClick={() => setTab(key)}>{label}</button>
        ))}
      </div>
      {tab === 'candidates' && <Candidates key={version} exam={exam} />}
      {tab === 'questions' && <Questions exam={exam} onExamChange={() => reload()} />}
      {tab === 'attempts' && <Attempts exam={exam} canRelease={setter} />}
      {editing && (
        <ExamFormModal
          exam={exam}
          onClose={() => setEditing(false)}
          onSaved={(data) => { setEditing(false); setData(data); setVersion((v) => v + 1); setNotice({ tone: 'success', text: 'Saved.' }) }}
        />
      )}
      {confirmDelete && (
        <Modal
          title={`Delete the ${exam.code} exam?`}
          onClose={() => setConfirmDelete(false)}
          footer={<><button className="btn btn-ghost" onClick={() => setConfirmDelete(false)}>Cancel</button><button className="btn btn-danger" onClick={remove}>Delete</button></>}
        >
          <p>It is still a draft, so no student has been told about it.</p>
        </Modal>
      )}
    </div>
  )
}

/** /portal/manage/exams/:id */
export default function ExamDetail() {
  const { id } = useParams()
  return <ExamDetailView examId={id} />
}

/** /portal/teaching/:id/exam: a lecturer's view of their course's exam. */
export function CourseExam() {
  const { id } = useParams()
  const { data: exams, error } = useApi('/exams/timetable/', { offering: id })
  if (error) return <Alert>{error}</Alert>
  if (!exams) return <Spinner />
  if (!exams.length) {
    return (
      <EmptyState icon="calendar" title="No exam scheduled yet">
        The Examinations Office hasn't scheduled this course's exam. Once it's on the timetable you can set CBT questions here.
      </EmptyState>
    )
  }
  return <ExamDetailView examId={exams[0].id} />
}

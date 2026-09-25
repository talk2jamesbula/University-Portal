import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import api, { blobErrorMessage, downloadFile, errorMessage } from '../../api/client'
import Icon from '../../components/Icon'
import { Alert, Badge, Card, EmptyState, Modal, PageHeader, Spinner } from '../../components/ui'
import { formatClock, formatDate, formatTime } from '../../utils/format'
import { formatPercent } from '../attendance/attendance'
import { ATTEMPT_TONE, MODE_TONE, formatDuration, useMyExams } from './exams'

function StartModal({ exam, onClose }) {
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const [starting, setStarting] = useState(false)
  const resuming = exam.attempt?.status === 'in_progress'

  const start = async () => {
    setStarting(true)
    setError('')
    try {
      const { data } = await api.post(`/exams/timetable/${exam.id}/start/`)
      navigate(`/portal/exams/attempts/${data.id}`)
    } catch (err) {
      setError(errorMessage(err))
      setStarting(false)
    }
  }

  return (
    <Modal
      title={`${resuming ? 'Resume' : 'Start'} ${exam.code} examination`}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Not yet</button>
          <button className="btn btn-primary" onClick={start} disabled={starting}>
            {starting ? 'Opening…' : resuming ? 'Resume exam' : 'Start the exam now'}
          </button>
        </>
      }
    >
      <div className="stack">
        <Alert>{error}</Alert>
        <p><strong>{exam.title}</strong> · {formatDuration(exam.duration_minutes)}</p>
        <ul className="plain-list">
          <li>The timer starts as soon as you begin and keeps running if you close the page.</li>
          <li>Each answer is saved as you choose it. When time runs out, your paper is submitted automatically.</li>
          <li>You have one attempt. Stay on the exam page: leaving it is recorded and reported to your lecturer.</li>
        </ul>
      </div>
    </Modal>
  )
}

function Eligibility({ exam }) {
  if (exam.eligible) {
    return exam.waived ? <Badge tone="blue">Eligible (waiver)</Badge> : <Badge tone="green">Eligible</Badge>
  }
  return <Badge tone="red">Not eligible</Badge>
}

/** A student's exam timetable, eligibility and exam card; computer-based tests start from here. */
export default function MyExams() {
  const { data, error } = useMyExams()
  const [params, setParams] = useSearchParams()
  const [picked, setPicked] = useState(null)
  const [cardError, setCardError] = useState('')
  const [downloading, setDownloading] = useState(false)

  if (error && !data) return <Alert>{error}</Alert>
  if (!data) return <Spinner />

  const blocked = data.exams.filter((e) => !e.eligible)
  // Arriving from the dashboard's "Start exam" button (?start=<exam id>) opens the start dialog.
  const requested = data.exams.find((e) => e.id === Number(params.get('start')) && e.can_start)
  const starting = picked ?? requested
  const setStarting = (exam) => {
    setPicked(exam)
    if (!exam && params.get('start')) setParams({}, { replace: true })
  }
  const download = async () => {
    setDownloading(true)
    setCardError('')
    try {
      await downloadFile('/exams/me/card/', undefined, 'exam-card.pdf')
    } catch (err) {
      setCardError(await blobErrorMessage(err))
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="stack-lg">
      <PageHeader
        title="Examinations"
        subtitle={`${data.semester.name} · your timetable, venues and exam card`}
        actions={
          <button className="btn btn-primary" onClick={download} disabled={!data.card_available || downloading}>
            <Icon name="download" size={16} /> {downloading ? 'Preparing…' : 'Download exam card'}
          </button>
        }
      />
      <Alert onClose={() => setCardError('')}>{cardError}</Alert>
      {blocked.length > 0 && (
        <div className="callout callout-danger">
          <Icon name="alert" />
          <div>
            <strong>You can't sit {blocked.map((e) => e.code).join(', ')} yet.</strong>
            <ul className="plain-list">
              {blocked.map((e) => <li key={e.id}>{e.code}: {e.reasons.join(' ')}</li>)}
            </ul>
            <span className="small">Clear the issue before the exam, or ask the Examinations Office about a waiver.</span>
          </div>
        </div>
      )}
      {data.exams.length === 0 ? (
        <EmptyState icon="calendar" title="No examinations on the timetable yet">
          Your exams appear here once the Examinations Office publishes the timetable.
        </EmptyState>
      ) : (
        <Card padded={false}>
          <table className="table">
            <thead>
              <tr><th>Date</th><th>Course</th><th>Time</th><th>Venue</th><th className="num">Seat</th><th>Status</th><th /></tr>
            </thead>
            <tbody>
              {data.exams.map((e) => (
                <tr key={e.id}>
                  <td className="cell-title nowrap">{formatDate(e.date, { weekday: 'short', day: 'numeric', month: 'short' })}</td>
                  <td>
                    <div className="cell-title">{e.code} <Badge tone={MODE_TONE[e.mode]}>{e.mode === 'cbt' ? 'CBT' : 'Paper'}</Badge></div>
                    <div className="muted small">{e.title}</div>
                  </td>
                  <td className="nowrap">{formatTime(e.start_time)}<div className="muted small">{formatDuration(e.duration_minutes)}</div></td>
                  <td>{e.venue || <span className="muted">To be assigned</span>}{e.venue_location && <div className="muted small">{e.venue_location}</div>}</td>
                  <td className="num strong">{e.seat_number ?? '—'}</td>
                  <td>
                    <Eligibility exam={e} />
                    {e.attendance_percent != null && <div className="muted small">Attendance {formatPercent(e.attendance_percent)}</div>}
                  </td>
                  <td className="align-right nowrap">
                    {e.attempt && e.attempt.status !== 'in_progress' ? (
                      <Badge tone={ATTEMPT_TONE[e.attempt.status]}>{e.attempt.status_label}</Badge>
                    ) : e.can_start ? (
                      <button className="btn btn-primary btn-sm" onClick={() => setStarting(e)}>
                        {e.attempt ? 'Resume exam' : 'Start exam'}
                      </button>
                    ) : e.mode === 'cbt' && e.eligible && new Date(e.starts_at) > new Date() ? (
                      <span className="muted small">Opens {formatClock(e.starts_at)}</span>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
      <p className="muted small">
        You need at least {data.minimum_percent}% attendance in a course, and no overdue fees, to sit its examination.
        Bring your exam card and student ID to every paper.
      </p>
      {starting && <StartModal exam={starting} onClose={() => setStarting(null)} />}
    </div>
  )
}

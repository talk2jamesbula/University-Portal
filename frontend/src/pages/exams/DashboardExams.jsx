import { Link } from 'react-router-dom'
import Icon from '../../components/Icon'
import { Badge, Card } from '../../components/ui'
import { formatClock, formatDate, formatTime, localToday } from '../../utils/format'
import { MODE_TONE, formatDuration } from './exams'

/** Banners for CBTs the student can sit (or resume) right now. */
export function ExamAlerts({ exams }) {
  const open = exams.filter((e) => e.can_start)
  return open.map((e) => {
    const resuming = e.attempt?.status === 'in_progress'
    return (
      <div key={e.id} className="callout callout-info exam-alert">
        <Icon name="clock" />
        <span>
          <strong>{e.code} {resuming ? 'is in progress' : 'is open now'}.</strong>{' '}
          {e.title} · {formatDuration(e.duration_minutes)}
          {!resuming && <> · entry closes at {formatClock(e.entry_closes_at)}</>}
        </span>
        <Link to={`/portal/exams?start=${e.id}`} className="btn btn-primary btn-sm">{resuming ? 'Resume exam' : 'Start exam'}</Link>
      </div>
    )
  })
}

/** The next few exams on the student's timetable. */
export function UpcomingExams({ exams }) {
  const today = localToday()
  const upcoming = exams.filter((e) => e.date >= today && !(e.attempt && e.attempt.status !== 'in_progress')).slice(0, 4)
  if (!upcoming.length) return null
  return (
    <Card title="Upcoming examinations" action={<Link to="/portal/exams" className="link">Exam timetable</Link>}>
      <ul className="list">
        {upcoming.map((e) => (
          <li key={e.id} className="list-item">
            <div className="grow">
              <div className="list-title">
                {e.code} <Badge tone={MODE_TONE[e.mode]}>{e.mode === 'cbt' ? 'CBT' : 'Paper'}</Badge>{' '}
                {!e.eligible && <Badge tone="red">Not eligible</Badge>}
              </div>
              <div className="list-meta">
                {formatDate(e.date, { weekday: 'short', day: 'numeric', month: 'short' })}, {formatTime(e.start_time)}
                {e.venue && <> · {e.venue}, seat {e.seat_number}</>}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </Card>
  )
}

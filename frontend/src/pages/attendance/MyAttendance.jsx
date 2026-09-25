import { useState } from 'react'
import { Link } from 'react-router-dom'
import Icon from '../../components/Icon'
import { Alert, Badge, Card, EmptyState, PageHeader, Spinner, Stat } from '../../components/ui'
import { formatDate, formatTime } from '../../utils/format'
import useApi from '../../utils/useApi'
import { STATUS_TONE, formatPercent } from './attendance'
import PercentBar from './PercentBar'

function CourseAttendance({ course, minimum }) {
  const [open, setOpen] = useState(false)
  return (
    <Card padded={false}>
      <button className="attendance-course" onClick={() => setOpen(!open)} aria-expanded={open}>
        <div className="grow">
          <div className="cell-title">{course.course_code} {course.at_risk && <Badge tone="red">Below {minimum}%</Badge>}</div>
          <div className="muted small">{course.course_title}</div>
        </div>
        <div className="attendance-counts small muted">
          <span><strong className="text-strong">{course.attended}</strong> of {course.held} classes</span>
          {course.late > 0 && <span>{course.late} late</span>}
          {course.absent > 0 && <span className="text-red">{course.absent} absent</span>}
        </div>
        <PercentBar value={course.percent} minimum={minimum} />
        <Icon name="chevronDown" size={16} className={open ? 'rotate-180' : ''} />
      </button>
      {open && (course.history.length === 0 ? (
        <EmptyState icon="calendar" title="No classes recorded yet" />
      ) : (
        <table className="table">
          <thead><tr><th>Date</th><th>Time</th><th>Topic</th><th>Status</th><th>Recorded by</th></tr></thead>
          <tbody>
            {course.history.map((h) => (
              <tr key={`${h.date}-${h.start_time}`}>
                <td>{formatDate(h.date, { weekday: 'short', day: 'numeric', month: 'short' })}</td>
                <td>{formatTime(h.start_time)}</td>
                <td>{h.topic || <span className="muted">—</span>}</td>
                <td><Badge tone={STATUS_TONE[h.status]}>{h.status_label}</Badge>{h.session_open && <span className="muted small"> · class in progress</span>}</td>
                <td className="muted small">{h.method}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ))}
    </Card>
  )
}

/** A student's attendance for each course this semester. */
export default function MyAttendance() {
  const { data, loading, error } = useApi('/attendance/me/')

  if (loading && !data) return <Spinner />
  if (error) return <Alert>{error}</Alert>

  const minimum = data.minimum_percent
  const atRisk = data.courses.filter((c) => c.at_risk)
  const held = data.courses.reduce((sum, c) => sum + c.held, 0)
  const absences = data.courses.reduce((sum, c) => sum + c.absent, 0)

  return (
    <div className="stack-lg">
      <PageHeader
        title="Attendance"
        subtitle={`You need at least ${minimum}% attendance in each course to sit its examination.`}
        actions={<Link to="/portal/attend" className="btn btn-primary"><Icon name="qr" size={16} /> Scan QR code</Link>}
      />
      {atRisk.length > 0 && (
        <div className="callout callout-danger">
          <Icon name="alert" />
          <span>
            Your attendance is below {minimum}% in <strong>{atRisk.map((c) => c.course_code).join(', ')}</strong>.
            Attend every remaining class and speak to your lecturer or level adviser.
          </span>
        </div>
      )}
      <div className="stats-grid">
        <Stat icon="check" label="Overall attendance" value={formatPercent(data.overall_percent)}
              tone={data.overall_percent != null && data.overall_percent < minimum ? 'red' : 'green'} />
        <Stat icon="calendar" label="Classes held" value={held} />
        <Stat icon="close" label="Absences" value={absences} tone={absences ? 'amber' : 'green'} />
        <Stat icon="alert" label={`Courses below ${minimum}%`} value={atRisk.length} tone={atRisk.length ? 'red' : 'green'} />
      </div>
      {data.courses.length === 0 ? (
        <EmptyState icon="book" title="No registered courses this semester">
          <Link to="/portal/registration" className="link">Register your courses</Link> to start recording attendance.
        </EmptyState>
      ) : (
        <div className="stack">
          {data.courses.map((c) => <CourseAttendance key={c.offering} course={c} minimum={minimum} />)}
        </div>
      )}
    </div>
  )
}

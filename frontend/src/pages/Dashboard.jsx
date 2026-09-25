import { Link } from 'react-router-dom'
import { can, isStudent } from '../auth/access'
import { useAuth } from '../auth/useAuth'
import Icon from '../components/Icon'
import { Alert, Avatar, Badge, Card, EmptyState, Spinner, Stat } from '../components/ui'
import {
  CATEGORY_TONE,
  PRIORITY_TONE,
  formatDate,
  formatDateTime,
  formatMoney,
  formatSchedule,
  parseDate,
  timeAgo,
} from '../utils/format'
import useApi from '../utils/useApi'
import Analytics from './Analytics'
import { ExamAlerts, UpcomingExams } from './exams/DashboardExams'
import { useMyExams } from './exams/exams'
import WeekSchedule from './WeekSchedule'

const REGISTRATION_STATE = {
  not_started: { label: 'Not started', tone: 'red' },
  incomplete: { label: 'Incomplete', tone: 'amber' },
  complete: { label: 'Complete', tone: 'green' },
}

function greeting() {
  const h = new Date().getHours()
  return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening'
}

function StudentHeader({ user, data }) {
  const { profile, semester } = data
  return (
    <div className="welcome welcome-student">
      <Avatar name={user.full_name} src={user.avatar_url} size={76} />
      <div className="grow">
        <p className="eyebrow">{semester ? semester.name : 'No active semester'}</p>
        <h1>{greeting()}, {user.first_name}</h1>
        <div className="welcome-facts">
          <span><strong>{profile.matric_number}</strong></span>
          <span>{profile.programme}</span>
          <span>{profile.level} Level</span>
          <span>{profile.status}</span>
        </div>
      </div>
      {data.registration?.is_open && data.registration.state !== 'complete' && (
        <Link to="/portal/registration" className="btn btn-primary"><Icon name="register" size={16} /> Register courses</Link>
      )}
    </div>
  )
}

function StudentView({ user, data }) {
  const { stats, registration } = data
  const { data: attendance } = useApi('/attendance/me/')
  const { data: exams } = useMyExams()
  const lowAttendance = attendance?.courses.filter((c) => c.at_risk) ?? []
  const regState = registration && REGISTRATION_STATE[registration.state]
  return (
    <>
      <StudentHeader user={user} data={data} />
      {exams && <ExamAlerts exams={exams.exams} />}

      {stats.balance > 0 && (
        <div className={`callout ${stats.overdue > 0 ? 'callout-danger' : ''}`}>
          <Icon name="wallet" />
          <span>
            {stats.overdue > 0
              ? <>You have <strong>{formatMoney(stats.overdue)}</strong> in overdue fees.</>
              : <>Outstanding fees of <strong>{formatMoney(stats.balance)}</strong>{stats.next_due_date ? <> due by <strong>{formatDate(stats.next_due_date)}</strong></> : null}.</>}
          </span>
          <Link to="/portal/fees" className="btn btn-primary btn-sm">Pay now</Link>
        </div>
      )}

      {lowAttendance.length > 0 && (
        <div className="callout callout-danger">
          <Icon name="alert" />
          <span>
            Your attendance is below {attendance.minimum_percent}% in <strong>{lowAttendance.map((c) => c.course_code).join(', ')}</strong>.
            You may not be allowed to sit {lowAttendance.length === 1 ? 'its examination' : 'their examinations'}.
          </span>
          <Link to="/portal/attendance" className="btn btn-primary btn-sm">View attendance</Link>
        </div>
      )}

      <div className="stats-grid">
        <Stat icon="award" label="CGPA (5.00 scale)" value={stats.cgpa != null ? Number(stats.cgpa).toFixed(2) : '—'} hint={stats.standing} tone="green" />
        <Stat icon="wallet" label="Outstanding fees" value={formatMoney(Math.max(stats.balance, 0))} tone={stats.balance > 0 ? 'amber' : 'green'} />
        <Stat icon="register" label="Course registration" value={regState?.label ?? '—'}
              hint={registration ? `${registration.units} of ${registration.min_units}–${registration.max_units} units` : undefined}
              tone={regState?.tone === 'green' ? 'green' : regState?.tone === 'red' ? 'red' : 'amber'} />
        <Stat icon="check" label="Units passed" value={stats.units_passed} tone="purple" />
      </div>

      <div className="grid-2-1">
        <div className="stack-lg">
          <Card title="Lecture timetable" action={<Link to="/portal/my-courses" className="link">My courses</Link>}>
            {data.schedule.length ? <WeekSchedule courses={data.schedule} /> : (
              <EmptyState icon="calendar" title="No courses registered yet">
                {registration?.is_open ? <Link to="/portal/registration" className="link">Register your courses</Link> : 'Registration is closed.'}
              </EmptyState>
            )}
          </Card>
          {exams && <UpcomingExams exams={exams.exams} />}
        </div>
        <SideColumn data={data} />
      </div>
      <AnnouncementsCard items={data.announcements} />
    </>
  )
}

function StaffView({ user, data }) {
  const { stats } = data
  return (
    <>
      <div className="welcome">
        <div>
          <p className="eyebrow">{data.semester ? data.semester.name : 'No active semester'}</p>
          <h1>{greeting()}, {user.full_name}</h1>
          <p className="muted">{user.staff_profile?.designation}{user.department_name ? ` · ${user.department_name}` : ''}</p>
        </div>
      </div>
      <div className="stats-grid">
        <Stat icon="book" label="Assigned courses" value={stats.courses_teaching} />
        <Stat icon="users" label="Registered students" value={stats.total_students} tone="purple" />
        <Stat icon="clock" label="Classes today" value={stats.classes_today} tone="green" />
        <Stat icon="award" label="Results pending" value={stats.pending_results} tone="amber" />
      </div>
      <div className="grid-2-1">
        <Card title="Classes today" action={<Link to="/portal/teaching" className="link">All my courses</Link>}>
          {data.classes_today.length ? (
            <ul className="list">
              {data.classes_today.map((o) => (
                <li key={o.id} className="list-item">
                  <div className="list-icon"><Icon name="clock" /></div>
                  <div className="grow">
                    <div className="list-title">{o.code} · {o.title}</div>
                    <div className="list-meta">{formatSchedule(o)} · {o.venue}</div>
                  </div>
                  <Link to={`/portal/teaching/${o.id}/attendance`} className="btn btn-primary btn-sm"><Icon name="qr" size={14} /> Attendance</Link>
                </li>
              ))}
            </ul>
          ) : <EmptyState icon="calendar" title="No classes today" />}
        </Card>
        <SideColumn data={data} />
      </div>
      {data.schedule.length > 0 && (
        <Card title="Weekly teaching timetable"><WeekSchedule courses={data.schedule} /></Card>
      )}
      <AnnouncementsCard items={data.announcements} />
    </>
  )
}

function AdminView({ user, data }) {
  const { stats } = data
  return (
    <>
      <div className="welcome">
        <div>
          <p className="eyebrow">{data.semester ? data.semester.name : 'No active semester'}</p>
          <h1>{greeting()}, {user.full_name}</h1>
          <p className="muted">{user.assignments?.map((a) => a.role_name).join(' · ') || 'Super Admin'}</p>
        </div>
      </div>
      {stats.pending_proofs > 0 && can(user, 'finance.manage') && (
        <div className="callout callout-info">
          <Icon name="receipt" />
          <span><strong>{stats.pending_proofs}</strong> proof{stats.pending_proofs === 1 ? '' : 's'} of payment awaiting review.</span>
          <Link to="/portal/fees" className="btn btn-primary btn-sm">Review now</Link>
        </div>
      )}
      {can(user, 'students.manage') && (
        <div className="quick-actions">
          <Link to="/portal/manage/students?upload=1" className="btn btn-primary"><Icon name="register" size={16} /> Bulk upload students</Link>
          <Link to="/portal/manage/students" className="btn btn-ghost"><Icon name="users" size={16} /> Manage students</Link>
          {can(user, 'admissions.manage') && <Link to="/portal/manage/admissions" className="btn btn-ghost"><Icon name="cap" size={16} /> Admissions</Link>}
        </div>
      )}
      <div className="stats-grid">
        <Stat icon="users" label="Active students" value={stats.students} />
        <Stat icon="user" label="Staff" value={stats.staff} tone="purple" />
        <Stat icon="book" label="Courses offered this semester" value={stats.offerings} tone="green" />
        <Stat icon="register" label="Course registrations" value={stats.registrations} tone="amber" />
      </div>
      {can(user, 'reports.view') && <Analytics />}
      <div className="grid-2-1">
        <AnnouncementsCard items={data.announcements} />
        <SideColumn data={data} />
      </div>
    </>
  )
}

function SideColumn({ data }) {
  return (
    <div className="stack-lg">
      <Card title="Notifications" action={<Link to="/portal/notifications" className="link">View all</Link>}>
        {data.notifications.length ? (
          <ul className="list">
            {data.notifications.map((n) => (
              <li key={n.id} className="list-item">
                <span className={`dot ${n.read ? '' : 'dot-unread'}`} />
                <div className="grow">
                  <div className="list-title">{n.link ? <Link to={n.link}>{n.title}</Link> : n.title}</div>
                  <div className="list-meta">{timeAgo(n.created_at)}</div>
                </div>
              </li>
            ))}
          </ul>
        ) : <EmptyState icon="bell" title="No notifications" />}
      </Card>
      <Card title="Academic calendar" action={<Link to="/portal/events" className="link">Full calendar</Link>}>
        {data.academic_calendar.length ? (
          <ul className="list">
            {data.academic_calendar.map((e) => {
              const d = parseDate(e.starts_at)
              return (
                <li key={e.id} className="list-item">
                  <div className="date-tile">
                    <span>{d.toLocaleString(undefined, { month: 'short' })}</span>
                    <strong>{d.getDate()}</strong>
                  </div>
                  <div className="grow">
                    <div className="list-title">{e.title}</div>
                    <div className="list-meta">{formatDateTime(e.starts_at)}</div>
                  </div>
                  <Badge tone={CATEGORY_TONE[e.category]}>{e.category}</Badge>
                </li>
              )
            })}
          </ul>
        ) : <EmptyState icon="calendar" title="Nothing scheduled" />}
      </Card>
    </div>
  )
}

function AnnouncementsCard({ items }) {
  return (
    <Card title="Important announcements" action={<Link to="/portal/announcements" className="link">View all</Link>}>
      {items.length ? (
        <ul className="list">
          {items.map((a) => (
            <li key={a.id} className="list-item">
              <div className="list-icon"><Icon name="megaphone" /></div>
              <div className="grow">
                <div className="list-title">{a.title}</div>
                <div className="list-meta">{a.course_code || a.department_name || 'University'} · {timeAgo(a.created_at)}</div>
              </div>
              {a.priority !== 'normal' && <Badge tone={PRIORITY_TONE[a.priority]}>{a.priority}</Badge>}
            </li>
          ))}
        </ul>
      ) : <EmptyState icon="megaphone" title="No announcements yet" />}
    </Card>
  )
}

export default function Dashboard() {
  const { user } = useAuth()
  const { data, error, loading } = useApi('/academics/dashboard/')

  if (loading && !data) return <Spinner />
  if (error) return <Alert>{error}</Alert>

  const View = isStudent(user) ? StudentView : data.stats?.courses_teaching !== undefined ? StaffView : AdminView
  return <div className="stack-lg"><View user={user} data={data} /></div>
}

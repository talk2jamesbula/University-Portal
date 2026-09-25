import { Link } from 'react-router-dom'
import { results } from '../api/client'
import { isStudent } from '../auth/access'
import { useAuth } from '../auth/useAuth'
import Icon from '../components/Icon'
import { Alert, Badge, Card, EmptyState, PageHeader, Spinner } from '../components/ui'
import { formatSchedule } from '../utils/format'
import useApi from '../utils/useApi'
import WeekSchedule from './WeekSchedule'

/** Students: courses registered this semester. Lecturers: courses they teach. */
export default function MyCourses() {
  const { user } = useAuth()
  const student = isStudent(user)
  const { data: semesters } = useApi('/academics/semesters/', { is_current: true })
  const semester = semesters?.[0]
  const { data, loading, error } = useApi(semesters ? '/academics/offerings/' : null, {
    mine: true, ...(semester ? { semester: semester.id } : {}),
  })
  const courses = results(data)
  const units = courses.reduce((sum, c) => sum + c.units, 0)

  return (
    <div className="stack-lg">
      <PageHeader
        title="My Courses"
        subtitle={semester ? `${semester.name} · ${courses.length} courses${student ? ` · ${units} units` : ''}` : undefined}
        actions={student && <Link to="/portal/registration" className="btn btn-primary"><Icon name="register" size={16} /> Course registration</Link>}
      />
      {error && <Alert>{error}</Alert>}
      {loading && !data ? <Spinner /> : courses.length === 0 ? (
        <EmptyState icon="book" title={student ? "You haven't registered any courses" : 'No courses assigned to you this semester'}>
          {student ? <Link to="/portal/registration" className="link">Go to course registration</Link> : 'Your HOD assigns courses each semester.'}
        </EmptyState>
      ) : (
        <>
          <Card title="Weekly timetable"><WeekSchedule courses={courses} /></Card>
          <Card title="Courses" padded={false}>
            <table className="table">
              <thead>
                <tr>
                  <th>Course</th><th className="num">Units</th><th>{student ? 'Lecturer' : 'Students'}</th>
                  <th>Timetable</th><th>Venue</th>{!student && <th />}
                </tr>
              </thead>
              <tbody>
                {courses.map((c) => (
                  <tr key={c.id}>
                    <td><div className="cell-title">{c.code}</div><div className="muted small">{c.title}</div></td>
                    <td className="num">{c.units}</td>
                    <td>{student ? c.lecturer_name || 'TBA' : <Badge>{c.registered_count} / {c.capacity}</Badge>}</td>
                    <td>{formatSchedule(c)}</td>
                    <td>{c.venue}</td>
                    {!student && (
                      <td className="align-right nowrap">
                        <Link to={`/portal/teaching/${c.id}/attendance`} className="btn btn-ghost btn-sm"><Icon name="qr" size={14} /> Attendance</Link>{' '}
                        <Link to={`/portal/teaching/${c.id}`} className="btn btn-ghost btn-sm">Class list <Icon name="chevronRight" size={14} /></Link>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </>
      )}
    </div>
  )
}

import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import Icon from '../components/Icon'
import { Alert, Avatar, Badge, Card, EmptyState, PageHeader, Spinner } from '../components/ui'
import { formatSchedule } from '../utils/format'
import useApi from '../utils/useApi'

const score = (n) => (n == null ? '—' : Number(n).toFixed(1).replace(/\.0$/, ''))

/** The class list for a course offering, with each student's scores so far. */
export default function CourseRoster() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { data: offering, error: offeringError } = useApi(`/academics/offerings/${id}/`)
  const { data: roster, loading, error } = useApi(`/academics/offerings/${id}/roster/`)
  const [query, setQuery] = useState('')

  if (offeringError || error) return <Alert>{offeringError || error}</Alert>
  if (!offering || (loading && !roster)) return <Spinner />

  const q = query.toLowerCase()
  const rows = roster.filter((r) => !q || `${r.student_name} ${r.matric_number}`.toLowerCase().includes(q))

  return (
    <div className="stack-lg">
      <button onClick={() => navigate(-1)} className="back-link"><Icon name="arrowLeft" size={16} /> Back</button>
      <PageHeader
        title={`${offering.code} · ${offering.title}`}
        subtitle={`${offering.semester_name} · ${offering.units} units · ${formatSchedule(offering)} · ${offering.venue}`}
        actions={
          <>
            <Link to={`/portal/teaching/${id}/attendance`} className="btn btn-ghost"><Icon name="qr" size={16} /> Attendance</Link>
            <Link to={`/portal/teaching/${id}/exam`} className="btn btn-ghost"><Icon name="clock" size={16} /> Exam</Link>
            <Link to={`/portal/results/sheets/${id}`} className="btn btn-primary"><Icon name="award" size={16} /> Scores &amp; results</Link>
          </>
        }
      />
      <div className="stats-inline">
        <div><strong>{roster.length}</strong><span>Registered students</span></div>
        <div><strong>{offering.capacity}</strong><span>Capacity</span></div>
        <div><strong>{roster.filter((r) => r.is_carryover).length}</strong><span>Carry-over students</span></div>
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
        {rows.length === 0 ? <EmptyState icon="users" title={roster.length ? 'No matching students' : 'No students registered yet'} /> : (
          <table className="table">
            <thead>
              <tr><th>#</th><th>Student</th><th>Matric no.</th><th className="num">Level</th><th className="num">CA</th><th className="num">Exam</th><th className="num">Total</th><th>Grade</th></tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={r.id}>
                  <td className="muted">{i + 1}</td>
                  <td>
                    <div className="person">
                      <Avatar name={r.student_name} src={r.student_avatar_url} size={32} />
                      <div>
                        <div className="cell-title">{r.student_name} {r.is_carryover && <Badge tone="red">Carry-over</Badge>}</div>
                        <div className="muted small">{r.student_email}</div>
                      </div>
                    </div>
                  </td>
                  <td className="mono">{r.matric_number}</td>
                  <td className="num">{r.level}</td>
                  <td className="num">{score(r.ca_score)}</td>
                  <td className="num">{score(r.exam_score)}</td>
                  <td className="num">{score(r.total_score)}</td>
                  <td>{r.grade ? <Badge>{r.grade}</Badge> : <span className="muted">—</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  )
}

import { useState } from 'react'
import { results } from '../api/client'
import Icon from '../components/Icon'
import { Alert, Badge, Card, EmptyState, PageHeader, Spinner } from '../components/ui'
import { formatSchedule } from '../utils/format'
import useApi from '../utils/useApi'
import useDebounced from '../utils/useDebounced'

const LEVELS = [100, 200, 300, 400, 500]

/** Every course offered in a semester, searchable by department and level. */
export default function CourseOfferings() {
  const { data: semesters } = useApi('/academics/semesters/')
  const { data: departments } = useApi('/academics/departments/')
  const [filters, setFilters] = useState({ search: '', department: '', level: '', semester: '' })
  const search = useDebounced(filters.search)
  const semesterId = filters.semester || String(semesters?.find((s) => s.is_current)?.id ?? '')
  const { data, loading, error } = useApi(semesters ? '/academics/offerings/' : null, {
    search, semester: semesterId, course__department: filters.department, course__level: filters.level,
  })
  const offerings = results(data)
  const set = (key) => (e) => setFilters({ ...filters, [key]: e.target.value })

  return (
    <div className="stack-lg">
      <PageHeader title="Course Offerings" subtitle="Courses taught this semester across the university" />
      <div className="toolbar">
        <label className="search">
          <Icon name="search" />
          <input placeholder="Search by code, title or lecturer" value={filters.search} onChange={set('search')} aria-label="Search courses" />
        </label>
        <select value={filters.department} onChange={set('department')} aria-label="Department">
          <option value="">All departments</option>
          {departments?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
        <select value={filters.level} onChange={set('level')} aria-label="Level">
          <option value="">All levels</option>
          {LEVELS.map((l) => <option key={l} value={l}>{l} Level</option>)}
        </select>
        <select value={semesterId} onChange={set('semester')} aria-label="Semester">
          {semesters?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
      </div>
      {error && <Alert>{error}</Alert>}
      {loading && !data ? <Spinner /> : offerings.length === 0 ? (
        <EmptyState title="No courses match your filters" />
      ) : (
        <Card padded={false}>
          <table className="table">
            <thead>
              <tr><th>Code</th><th>Title</th><th>Dept.</th><th className="num">Level</th><th className="num">Units</th><th>Lecturer</th><th>Timetable</th><th>Venue</th></tr>
            </thead>
            <tbody>
              {offerings.map((o) => (
                <tr key={o.id}>
                  <td className="cell-title">{o.code}</td>
                  <td>{o.title}</td>
                  <td><Badge>{o.department_code}</Badge></td>
                  <td className="num">{o.level}</td>
                  <td className="num">{o.units}</td>
                  <td>{o.lecturer_name || 'TBA'}</td>
                  <td className="small">{formatSchedule(o)}</td>
                  <td className="small">{o.venue}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  )
}

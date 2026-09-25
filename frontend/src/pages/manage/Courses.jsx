import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { results } from '../../api/client'
import Icon from '../../components/Icon'
import { Alert, Badge, Card, EmptyState, PageHeader, Spinner } from '../../components/ui'
import useApi from '../../utils/useApi'
import useDebounced from '../../utils/useDebounced'
import CourseFormModal from './CourseFormModal'
import { LEVELS, SEMESTER_NUMBERS } from './courseOptions'

/** The course catalogue, for staff who manage the academic structure. */
export default function Courses() {
  const navigate = useNavigate()
  const { data: departments } = useApi('/academics/departments/')
  const [filters, setFilters] = useState({ search: '', department: '', level: '', semester_number: '', is_active: '' })
  const [creating, setCreating] = useState(false)
  const [notice, setNotice] = useState('')
  const search = useDebounced(filters.search)
  const { data, loading, error, reload } = useApi('/academics/courses/', { ...filters, search })
  const courses = results(data)
  const set = (key) => (e) => setFilters({ ...filters, [key]: e.target.value })

  return (
    <div className="stack-lg">
      <PageHeader
        title="Manage Courses"
        subtitle={data ? `${data.count} courses in the catalogue` : 'The university course catalogue'}
        actions={<button className="btn btn-primary" onClick={() => setCreating(true)}><Icon name="plus" size={16} /> New course</button>}
      />
      <Alert tone="success" onClose={() => setNotice('')}>{notice}</Alert>
      <div className="toolbar">
        <label className="search">
          <Icon name="search" />
          <input placeholder="Search by code or title" value={filters.search} onChange={set('search')} aria-label="Search courses" />
        </label>
        <select value={filters.department} onChange={set('department')} aria-label="Department">
          <option value="">All departments</option>
          {departments?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
        <select value={filters.level} onChange={set('level')} aria-label="Level">
          <option value="">All levels</option>
          {LEVELS.map((l) => <option key={l} value={l}>{l} Level</option>)}
        </select>
        <select value={filters.semester_number} onChange={set('semester_number')} aria-label="Semester">
          <option value="">Both semesters</option>
          {SEMESTER_NUMBERS.map(([n, label]) => <option key={n} value={n}>{label}</option>)}
        </select>
        <select value={filters.is_active} onChange={set('is_active')} aria-label="Status">
          <option value="">Active and inactive</option>
          <option value="true">Active</option>
          <option value="false">Inactive</option>
        </select>
      </div>
      {error && <Alert>{error}</Alert>}
      {loading && !data ? <Spinner /> : courses.length === 0 ? (
        <EmptyState icon="catalog" title="No courses match">Try other filters, or create a new course.</EmptyState>
      ) : (
        <Card padded={false}>
          <table className="table table-clickable">
            <thead>
              <tr>
                <th>Code</th><th>Title</th><th>Department</th><th className="num">Units</th><th className="num">Level</th>
                <th>Semester</th><th className="num">Programmes</th><th className="num">Times offered</th><th />
              </tr>
            </thead>
            <tbody>
              {courses.map((c) => (
                <tr key={c.id} onClick={() => navigate(`/portal/manage/courses/${c.id}`)}>
                  <td className="cell-title">{c.code}</td>
                  <td>{c.title} {!c.is_active && <Badge tone="red">Inactive</Badge>}</td>
                  <td>{c.department_name}</td>
                  <td className="num">{c.units}</td>
                  <td className="num">{c.level}</td>
                  <td>{c.semester_label}</td>
                  <td className="num">{c.programme_count}</td>
                  <td className="num">{c.offering_count}</td>
                  <td className="align-right"><Link to={`/portal/manage/courses/${c.id}`} onClick={(e) => e.stopPropagation()} aria-label={`Open ${c.code}`}><Icon name="chevronRight" size={16} /></Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
      {creating && (
        <CourseFormModal
          onClose={() => setCreating(false)}
          onSaved={(course) => {
            setCreating(false)
            setNotice(`${course.code} ${course.title} was added to the catalogue.`)
            reload()
          }}
        />
      )}
    </div>
  )
}

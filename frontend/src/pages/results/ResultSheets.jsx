import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Icon from '../../components/Icon'
import { Alert, Badge, Card, EmptyState, PageHeader, Spinner } from '../../components/ui'
import useApi from '../../utils/useApi'
import { APPROVE_LABEL, RESULT_STATUS_LABEL, RESULT_STATUS_TONE } from './results'

const FILTERS = [
  ['mine', 'Needs my action'],
  ['', 'All courses'],
  ['draft', 'Draft'],
  ['submitted', 'With HOD'],
  ['department_approved', 'With Dean'],
  ['faculty_approved', 'With Exams Office'],
  ['published', 'Published'],
]

function nextStep(row) {
  if (row.actions.includes('submit')) return row.complete < row.students ? 'Enter scores' : 'Submit to HOD'
  if (row.actions.includes('approve')) return APPROVE_LABEL[row.status]
  return null
}

/** Courses whose results the user teaches or reviews: score entry, approvals and publication. */
export default function ResultSheets() {
  const navigate = useNavigate()
  const [status, setStatus] = useState('mine')
  const [query, setQuery] = useState('')
  const { data, loading, error } = useApi('/academics/result-sheets/', status ? { status } : undefined)

  if (error && !data) return <Alert>{error}</Alert>
  if (!data) return <Spinner />

  const q = query.toLowerCase()
  const rows = data.rows.filter((r) => !q || `${r.code} ${r.title} ${r.lecturer_name}`.toLowerCase().includes(q))

  return (
    <div className="stack-lg">
      <PageHeader title="Result Sheets" subtitle={`${data.semester.name} · enter scores, approve and publish course results`} />
      <div className="toolbar">
        <div className="tabs tabs-scroll" role="tablist">
          {FILTERS.map(([value, label]) => (
            <button key={value} role="tab" aria-selected={status === value} className={`tab ${status === value ? 'active' : ''}`} onClick={() => setStatus(value)}>
              {label}
            </button>
          ))}
        </div>
        <label className="search search-sm">
          <Icon name="search" size={16} />
          <input placeholder="Filter by course or lecturer" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Filter courses" />
        </label>
      </div>
      <Card padded={false}>
        {loading && !rows.length ? <Spinner /> : rows.length === 0 ? (
          <EmptyState icon="award" title={status === 'mine' ? 'Nothing is waiting for you' : 'No courses to show'}>
            {status === 'mine' ? 'Result sheets appear here when they need your scores or approval.' : null}
          </EmptyState>
        ) : (
          <table className="table table-clickable">
            <thead>
              <tr><th>Course</th><th>Department</th><th>Lecturer</th><th className="num">Scores entered</th><th>Status</th><th /></tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const step = nextStep(r)
                return (
                  <tr key={r.offering} onClick={() => navigate(`/portal/results/sheets/${r.offering}`)}>
                    <td><div className="cell-title">{r.code}</div><div className="muted small">{r.title}</div></td>
                    <td className="small">{r.department}</td>
                    <td className="small">{r.lecturer_name || <span className="muted">—</span>}</td>
                    <td className="num">{r.complete} / {r.students}</td>
                    <td><Badge tone={RESULT_STATUS_TONE[r.status]}>{RESULT_STATUS_LABEL[r.status]}</Badge></td>
                    <td className="align-right nowrap">
                      {step && <span className="btn btn-primary btn-sm">{step}</span>}{' '}
                      <Icon name="chevronRight" size={16} />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  )
}

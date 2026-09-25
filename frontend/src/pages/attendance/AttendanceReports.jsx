import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import api, { blobErrorMessage, downloadFile, errorMessage, results } from '../../api/client'
import { can } from '../../auth/access'
import { useAuth } from '../../auth/useAuth'
import Icon from '../../components/Icon'
import { Alert, Badge, Card, EmptyState, Modal, PageHeader, Spinner, Stat } from '../../components/ui'
import { formatDate, timeAgo } from '../../utils/format'
import useApi from '../../utils/useApi'
import useDebounced from '../../utils/useDebounced'
import { CORRECTION_TONE, STATUS_LABEL, STATUS_TONE, formatPercent } from './attendance'
import PercentBar from './PercentBar'

function Reports() {
  const { data: semesters } = useApi('/academics/semesters/')
  const { data: faculties } = useApi('/academics/faculties/')
  // semester: null means "the current semester" until the user picks one ('' is all semesters).
  const [chosen, setFilters] = useState({ semester: null, faculty: '', department: '', offering: '', search: '', at_risk: '' })
  const current = semesters?.find((s) => s.is_current)
  const filters = { ...chosen, semester: chosen.semester ?? (current ? String(current.id) : '') }
  const [student, setStudent] = useState(null)
  const [exporting, setExporting] = useState('')
  const [exportError, setExportError] = useState('')
  const { data: departments } = useApi('/academics/departments/', filters.faculty ? { faculty: filters.faculty } : {})
  const { data: offerings } = useApi(
    filters.department ? '/academics/offerings/' : null,
    { course__department: filters.department, semester: filters.semester },
  )

  const search = useDebounced(filters.search)
  const params = { ...filters, search, student: student?.id ?? '' }
  const { data, loading, error } = useApi(semesters ? '/attendance/reports/' : null, params)

  const set = (key, reset = []) => (e) =>
    setFilters({ ...filters, [key]: e.target.value, ...Object.fromEntries(reset.map((k) => [k, ''])) })

  const exportAs = async (file) => {
    setExporting(file)
    setExportError('')
    try {
      await downloadFile('/attendance/reports/export/', { ...params, file }, `attendance.${file}`)
    } catch (err) {
      setExportError(await blobErrorMessage(err))
    } finally {
      setExporting('')
    }
  }

  const minimum = data?.minimum_percent
  return (
    <div className="stack-lg">
      <div className="toolbar">
        <select value={filters.semester} onChange={set('semester', ['offering'])} aria-label="Semester">
          <option value="">All semesters</option>
          {semesters?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <select value={filters.faculty} onChange={set('faculty', ['department', 'offering'])} aria-label="Faculty">
          <option value="">All faculties</option>
          {faculties?.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
        </select>
        <select value={filters.department} onChange={set('department', ['offering'])} aria-label="Department">
          <option value="">All departments</option>
          {departments?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
        <select value={filters.offering} onChange={set('offering')} aria-label="Course" disabled={!filters.department}
                title={filters.department ? undefined : 'Choose a department first'}>
          <option value="">{filters.department ? 'All courses' : 'All courses (choose a department)'}</option>
          {results(offerings).map((o) => <option key={o.id} value={o.id}>{o.code} · {o.title}</option>)}
        </select>
      </div>
      <div className="toolbar">
        <label className="search">
          <Icon name="search" />
          <input placeholder="Search students by name or matric no." value={filters.search} onChange={set('search')} aria-label="Search students" />
        </label>
        <label className="check-inline">
          <input type="checkbox" checked={filters.at_risk === 'true'} onChange={(e) => setFilters({ ...filters, at_risk: e.target.checked ? 'true' : '' })} />
          Only below {minimum ?? 75}%
        </label>
        <button className="btn btn-ghost" onClick={() => exportAs('csv')} disabled={Boolean(exporting)}>
          <Icon name="download" size={16} /> {exporting === 'csv' ? 'Exporting…' : 'CSV'}
        </button>
        <button className="btn btn-ghost" onClick={() => exportAs('xlsx')} disabled={Boolean(exporting)}>
          <Icon name="download" size={16} /> {exporting === 'xlsx' ? 'Exporting…' : 'Excel'}
        </button>
      </div>
      {student && (
        <div className="filter-chip">
          Showing <strong>{student.name}</strong>
          <button className="icon-btn" onClick={() => setStudent(null)} aria-label="Show all students"><Icon name="close" size={14} /></button>
        </div>
      )}
      <Alert>{exportError}</Alert>
      {error && <Alert>{error}</Alert>}

      {!data ? <Spinner /> : (
        <>
          <div className="stats-grid">
            <Stat icon="users" label="Students" value={data.summary.students} />
            <Stat icon="book" label="Courses" value={data.summary.courses} tone="purple" />
            <Stat icon="check" label="Average attendance" value={formatPercent(data.summary.average_percent)} tone="green" />
            <Stat icon="alert" label={`Below ${minimum}%`} value={data.summary.at_risk} hint={`${data.summary.absences} absences in total`}
                  tone={data.summary.at_risk ? 'red' : 'green'} />
          </div>
          {data.rows.length === 0 ? (
            <EmptyState icon="check" title="No attendance recorded for these filters">Closed sessions appear here.</EmptyState>
          ) : (
            <Card padded={false} className={loading ? 'is-loading' : ''}>
              <table className="table">
                <thead>
                  <tr>
                    <th>Student</th><th>Course</th><th>Department</th><th className="num">Held</th><th className="num">Present</th>
                    <th className="num">Late</th><th className="num">Excused</th><th className="num">Absent</th><th>Attendance</th>
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((r) => (
                    <tr key={`${r.student_id}-${r.offering_id}`}>
                      <td>
                        <button className="link-button cell-title" onClick={() => setStudent({ id: r.student_id, name: r.student_name })}
                                title="Show only this student">
                          {r.student_name}
                        </button>
                        <div className="muted small mono">{r.matric_number}</div>
                      </td>
                      <td><div className="cell-title">{r.course_code}</div><div className="muted small">{r.course_title}</div></td>
                      <td className="small">{r.department}</td>
                      <td className="num">{r.held}</td>
                      <td className="num">{r.present}</td>
                      <td className="num">{r.late}</td>
                      <td className="num">{r.excused}</td>
                      <td className="num">{r.absent}</td>
                      <td><PercentBar value={r.percent} minimum={minimum} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {data.truncated && <p className="muted small table-note">Showing the first 500 rows. Narrow the filters, or export for the full report.</p>}
            </Card>
          )}
        </>
      )}
    </div>
  )
}

function DecisionModal({ correction, approve, onClose, onDone }) {
  const [note, setNote] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      await api.post(`/attendance/corrections/${correction.id}/decide/`, { approve, note })
      onDone(`Correction for ${correction.student_name} ${approve ? 'approved' : 'rejected'}.`)
    } catch (err) {
      setError(errorMessage(err))
      setSaving(false)
    }
  }

  return (
    <Modal
      title={approve ? 'Approve correction' : 'Reject correction'}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className={`btn ${approve ? 'btn-primary' : 'btn-danger-ghost'}`} form="decision-form" disabled={saving}>
            {saving ? 'Saving…' : approve ? 'Approve' : 'Reject'}
          </button>
        </>
      }
    >
      <form id="decision-form" className="form" onSubmit={submit}>
        <Alert>{error}</Alert>
        <p className="muted">
          <strong className="text-strong">{correction.student_name}</strong> in {correction.course_code} on {formatDate(correction.session_date)}:{' '}
          {STATUS_LABEL[correction.from_status]} → <strong className="text-strong">{STATUS_LABEL[correction.to_status]}</strong>
        </p>
        <blockquote className="quote">{correction.reason}<span className="muted small"> · {correction.requested_by_name}</span></blockquote>
        <label className="field">
          <span>Note to the lecturer {approve ? '(optional)' : ''}</span>
          <textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} required={!approve} />
        </label>
      </form>
    </Modal>
  )
}

function Corrections({ canApprove }) {
  const [status, setStatus] = useState('pending')
  const [deciding, setDeciding] = useState(null)
  const [notice, setNotice] = useState('')
  const { data, loading, error, reload } = useApi('/attendance/corrections/', status ? { status } : {})
  const items = results(data)

  return (
    <div className="stack-lg">
      <div className="toolbar">
        <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status">
          <option value="pending">Awaiting decision</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
          <option value="">All</option>
        </select>
      </div>
      <Alert tone="success" onClose={() => setNotice('')}>{notice}</Alert>
      {error && <Alert>{error}</Alert>}
      {loading && !data ? <Spinner /> : items.length === 0 ? (
        <EmptyState icon="check" title={status === 'pending' ? 'No corrections awaiting a decision' : 'No corrections'}>
          Lecturers request corrections when a closed session needs changing.
        </EmptyState>
      ) : (
        <Card padded={false}>
          <table className="table">
            <thead>
              <tr><th>Student</th><th>Class</th><th>Change</th><th>Reason</th><th>Requested</th><th /></tr>
            </thead>
            <tbody>
              {items.map((c) => (
                <tr key={c.id}>
                  <td><div className="cell-title">{c.student_name}</div><div className="muted small mono">{c.matric_number}</div></td>
                  <td>
                    <Link to={`/portal/attendance/sessions/${c.session_id}`} className="link">{c.course_code}</Link>
                    <div className="muted small">{formatDate(c.session_date)}</div>
                  </td>
                  <td className="nowrap">
                    <Badge tone={STATUS_TONE[c.from_status]}>{STATUS_LABEL[c.from_status]}</Badge> → <Badge tone={STATUS_TONE[c.to_status]}>{STATUS_LABEL[c.to_status]}</Badge>
                  </td>
                  <td className="small">{c.reason}{c.decision_note && <div className="muted">Note: {c.decision_note}</div>}</td>
                  <td className="small">{c.requested_by_name}<div className="muted">{timeAgo(c.created_at)}</div></td>
                  <td className="align-right nowrap">
                    {c.status === 'pending' && canApprove ? (
                      <>
                        <button className="btn btn-primary btn-sm" onClick={() => setDeciding({ correction: c, approve: true })}>Approve</button>{' '}
                        <button className="btn btn-danger-ghost btn-sm" onClick={() => setDeciding({ correction: c, approve: false })}>Reject</button>
                      </>
                    ) : (
                      <Badge tone={CORRECTION_TONE[c.status]}>{c.status_label}</Badge>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
      {deciding && (
        <DecisionModal
          {...deciding}
          onClose={() => setDeciding(null)}
          onDone={(text) => { setDeciding(null); setNotice(text); reload() }}
        />
      )}
    </div>
  )
}

/** Attendance reports for administrators, and the correction approval queue. */
export default function AttendanceReports() {
  const { user } = useAuth()
  const [params, setParams] = useSearchParams()
  const seesReports = can(user, 'attendance.view')
  const canApprove = can(user, 'attendance.approve')
  const tab = params.get('tab') === 'corrections' || !seesReports ? 'corrections' : 'reports'
  const select = (next) => setParams(next === 'reports' ? {} : { tab: next }, { replace: true })

  return (
    <div className="stack-lg">
      <PageHeader
        title="Attendance"
        subtitle="Attendance across courses this semester, and corrections to closed sessions"
      />
      <div className="tabs" role="tablist">
        {seesReports && (
          <button role="tab" aria-selected={tab === 'reports'} className={`tab ${tab === 'reports' ? 'active' : ''}`} onClick={() => select('reports')}>
            Reports
          </button>
        )}
        <button role="tab" aria-selected={tab === 'corrections'} className={`tab ${tab === 'corrections' ? 'active' : ''}`} onClick={() => select('corrections')}>
          Corrections
        </button>
      </div>
      {tab === 'reports' ? <Reports /> : <Corrections canApprove={canApprove} />}
    </div>
  )
}

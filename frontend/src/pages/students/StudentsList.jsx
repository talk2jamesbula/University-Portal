import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { blobErrorMessage, downloadFile, results } from '../../api/client'
import Icon from '../../components/Icon'
import { Alert, Avatar, Badge, Card, EmptyState, PageHeader, Spinner } from '../../components/ui'
import useApi from '../../utils/useApi'
import useDebounced from '../../utils/useDebounced'
import ImportModal from './ImportModal'
import StudentFormModal from './StudentFormModal'
import { GENDERS, STATUSES, STATUS_TONE, sessions } from './studentOptions'

const BLANK = { search: '', faculty: '', department: '', programme: '', level: '', status: '', current_session: '', gender: '', is_active: '', ordering: 'name' }

/** Student records: search, filter, create, import and export. */
export default function StudentsList() {
  const navigate = useNavigate()
  const [filters, setFilters] = useState(BLANK)
  const [page, setPage] = useState(1)
  const [creating, setCreating] = useState(false)
  // /portal/manage/students?upload=1 opens bulk upload straight away (linked from the dashboard).
  const [urlParams, setUrlParams] = useSearchParams()
  const [importing, setImporting] = useState(urlParams.get('upload') === '1')
  const closeImport = () => { setImporting(false); if (urlParams.get('upload')) setUrlParams({}, { replace: true }) }
  const [exporting, setExporting] = useState('')
  const [exportError, setExportError] = useState('')
  const search = useDebounced(filters.search)
  const params = { ...filters, search, page }
  const { data, loading, error, reload } = useApi('/students/', params)
  const { data: summary, reload: reloadSummary } = useApi('/students/summary/')
  const { data: faculties } = useApi('/academics/faculties/')
  const { data: departments } = useApi('/academics/departments/', filters.faculty ? { faculty: filters.faculty } : {})
  const { data: programmes } = useApi('/academics/programmes/', filters.department ? { department: filters.department } : filters.faculty ? { department__faculty: filters.faculty } : {})
  const rows = results(data)
  const manage = summary?.can_manage
  const filtered = Object.entries(filters).some(([k, v]) => v && k !== 'ordering')

  const set = (key, reset = []) => (e) => {
    setPage(1)
    setFilters({ ...filters, [key]: e.target.value, ...Object.fromEntries(reset.map((k) => [k, ''])) })
  }
  const exportAs = async (file) => {
    setExporting(file)
    setExportError('')
    try {
      const { page: _page, ...query } = params
      await downloadFile('/students/export/', { ...query, file }, `students.${file}`)
    } catch (err) {
      setExportError(await blobErrorMessage(err))
    } finally {
      setExporting('')
    }
  }

  return (
    <div className="stack-lg">
      <PageHeader
        title="Students"
        subtitle={summary ? `${summary.total} students${summary.inactive ? ` · ${summary.inactive} without portal access` : ''}` : 'Student records'}
        actions={
          <>
            <button className="btn btn-ghost" onClick={() => exportAs('csv')} disabled={Boolean(exporting)}><Icon name="download" size={16} /> {exporting === 'csv' ? 'Exporting…' : 'CSV'}</button>
            <button className="btn btn-ghost" onClick={() => exportAs('xlsx')} disabled={Boolean(exporting)}><Icon name="download" size={16} /> {exporting === 'xlsx' ? 'Exporting…' : 'Excel'}</button>
            {manage && <button className="btn btn-ghost" onClick={() => setImporting(true)}><Icon name="register" size={16} /> Bulk upload</button>}
            {manage && <button className="btn btn-primary" onClick={() => setCreating(true)}><Icon name="plus" size={16} /> New student</button>}
          </>
        }
      />
      <Alert>{exportError}</Alert>

      {summary && (
        <div className="status-chips" role="tablist" aria-label="Filter by status">
          <button role="tab" aria-selected={!filters.status} className={`status-chip ${!filters.status ? 'active' : ''}`} onClick={() => set('status')({ target: { value: '' } })}>
            <strong>{summary.total}</strong><span>All students</span>
          </button>
          {STATUSES.filter(([v]) => summary.by_status[v]).map(([v, label, tone]) => (
            <button key={v} role="tab" aria-selected={filters.status === v} className={`status-chip tone-chip-${tone} ${filters.status === v ? 'active' : ''}`}
                    onClick={() => set('status')({ target: { value: v } })}>
              <strong>{summary.by_status[v]}</strong><span>{label}</span>
            </button>
          ))}
        </div>
      )}

      <div className="toolbar">
        <label className="search">
          <Icon name="search" />
          <input placeholder="Search name, matric no., student ID, email or phone" value={filters.search} onChange={set('search')} aria-label="Search students" />
        </label>
        <select value={filters.faculty} onChange={set('faculty', ['department', 'programme'])} aria-label="Faculty">
          <option value="">All faculties</option>
          {faculties?.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
        </select>
        <select value={filters.department} onChange={set('department', ['programme'])} aria-label="Department">
          <option value="">All departments</option>
          {departments?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
        <select value={filters.programme} onChange={set('programme')} aria-label="Programme">
          <option value="">All programmes</option>
          {results(programmes).map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
        </select>
      </div>
      <div className="toolbar">
        <select value={filters.level} onChange={set('level')} aria-label="Level">
          <option value="">All levels</option>
          {[100, 200, 300, 400, 500, 600, 700].map((l) => <option key={l} value={l}>{l} Level</option>)}
        </select>
        <select value={filters.current_session} onChange={set('current_session')} aria-label="Session">
          <option value="">All sessions</option>
          {sessions().map((s) => <option key={s}>{s}</option>)}
        </select>
        <select value={filters.gender} onChange={set('gender')} aria-label="Gender">
          <option value="">Any gender</option>
          {GENDERS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <select value={filters.is_active} onChange={set('is_active')} aria-label="Portal access">
          <option value="">Any portal access</option>
          <option value="true">Portal access active</option>
          <option value="false">Deactivated</option>
        </select>
        <select value={filters.ordering} onChange={set('ordering')} aria-label="Sort">
          <option value="name">Name (A–Z)</option>
          <option value="-name">Name (Z–A)</option>
          <option value="matric">Matric number</option>
          <option value="level">Level (lowest first)</option>
          <option value="-level">Level (highest first)</option>
          <option value="newest">Recently added</option>
        </select>
        {filtered && <button className="btn btn-ghost btn-sm" onClick={() => { setFilters(BLANK); setPage(1) }}>Clear filters</button>}
      </div>

      {error && <Alert>{error}</Alert>}
      {loading && !data ? <Spinner /> : rows.length === 0 ? (
        <EmptyState icon="users" title={filtered ? 'No students match' : 'No students yet'}>
          {filtered ? 'Try other filters.' : manage ? 'Add a student, or bulk upload a list from Excel or CSV.' : null}
        </EmptyState>
      ) : (
        <Card padded={false} className={loading ? 'is-loading' : ''}>
          <table className="table table-clickable">
            <thead>
              <tr><th>Student</th><th>Student ID</th><th>Programme</th><th className="num">Level</th><th>Session</th><th>Status</th><th>Portal</th></tr>
            </thead>
            <tbody>
              {rows.map((s) => (
                <tr key={s.id} onClick={() => navigate(`/portal/manage/students/${s.id}`)}>
                  <td>
                    <div className="person">
                      <Avatar name={s.full_name} src={s.avatar_url} size={36} />
                      <div>
                        <div className="cell-title">{s.full_name}</div>
                        <div className="muted small mono">{s.matric_number}</div>
                      </div>
                    </div>
                  </td>
                  <td className="mono small">{s.student_id}</td>
                  <td><div>{s.programme}</div><div className="muted small">{s.department}</div></td>
                  <td className="num">{s.level}</td>
                  <td className="small">{s.current_session || '—'}</td>
                  <td><Badge tone={STATUS_TONE[s.status]}>{s.status_label}</Badge></td>
                  <td>{s.is_active ? <span className="muted small">Active</span> : <Badge tone="red">Deactivated</Badge>}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="pager">
            <span className="muted small">{data.count} students{data.count > rows.length ? ` · page ${page} of ${Math.ceil(data.count / 50)}` : ''}</span>
            {(data.next || data.previous) && (
              <>
                <button className="btn btn-ghost btn-sm" disabled={!data.previous} onClick={() => setPage(page - 1)}>Previous</button>
                <button className="btn btn-ghost btn-sm" disabled={!data.next} onClick={() => setPage(page + 1)}>Next</button>
              </>
            )}
          </div>
        </Card>
      )}

      {creating && (
        <StudentFormModal onClose={() => setCreating(false)} onSaved={(s) => { setCreating(false); navigate(`/portal/manage/students/${s.id}`) }} />
      )}
      {importing && manage && <ImportModal onClose={closeImport} onImported={() => { reload(); reloadSummary() }} />}
    </div>
  )
}

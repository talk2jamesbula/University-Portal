import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api, { blobErrorMessage, downloadFile, errorMessage, results } from '../../api/client'
import Icon from '../../components/Icon'
import { Alert, Avatar, Badge, Card, EmptyState, Modal, PageHeader, Spinner } from '../../components/ui'
import { formatDate, formatMoney } from '../../utils/format'
import useApi from '../../utils/useApi'
import useDebounced from '../../utils/useDebounced'
import { ENTRY_MODES, STATUS_LABEL, STATUS_TONE } from './admissions'

const ORDERINGS = [
  ['-submitted_at', 'Newest first'],
  ['submitted_at', 'Oldest first'],
  ['-aggregate', 'Aggregate (high to low)'],
  ['-utme_score', 'UTME score (high to low)'],
  ['-screening_score', 'Screening score (high to low)'],
]
const STAGES = ['submitted', 'under_review', 'screening', 'approved', 'waitlisted', 'rejected', 'admitted', 'accepted', 'draft']
const score = (n) => (n == null ? '—' : Number(n).toFixed(1).replace(/\.0$/, ''))

function CycleModal({ cycle, onClose, onSaved }) {
  const [form, setForm] = useState(cycle ?? {
    session: '', application_fee: 10000, opens_on: '', closes_on: '', min_utme_score: 160, resumption_date: '', acceptance_deadline: '', is_active: true,
  })
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })
  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    const body = { ...form, resumption_date: form.resumption_date || null, acceptance_deadline: form.acceptance_deadline || null }
    try {
      await (cycle ? api.patch(`/admissions/cycles/${cycle.id}/`, body) : api.post('/admissions/cycles/', body))
      onSaved()
    } catch (err) {
      setError(errorMessage(err))
      setSaving(false)
    }
  }
  return (
    <Modal
      title={cycle ? `Admission ${cycle.session} settings` : 'New admission exercise'}
      onClose={onClose}
      footer={<><button className="btn btn-ghost" onClick={onClose}>Cancel</button><button className="btn btn-primary" form="cycle-form" disabled={saving}>{saving ? 'Saving…' : 'Save'}</button></>}
    >
      <form id="cycle-form" className="form" onSubmit={submit}>
        <Alert>{error}</Alert>
        <div className="form-row">
          <label className="field"><span>Session</span><input value={form.session} onChange={set('session')} placeholder="2026/2027" required disabled={Boolean(cycle)} /></label>
          <label className="field"><span>Application fee (₦)</span><input type="number" min="0" step="0.01" value={form.application_fee} onChange={set('application_fee')} required /></label>
        </div>
        <div className="form-row">
          <label className="field"><span>Applications open</span><input type="date" value={form.opens_on} onChange={set('opens_on')} required /></label>
          <label className="field"><span>Applications close</span><input type="date" value={form.closes_on} onChange={set('closes_on')} required /></label>
        </div>
        <div className="form-row">
          <label className="field"><span>Minimum UTME score</span><input type="number" min="0" max="400" value={form.min_utme_score} onChange={set('min_utme_score')} required /></label>
          <label className="field"><span>Accept offers by</span><input type="date" value={form.acceptance_deadline ?? ''} onChange={set('acceptance_deadline')} /></label>
          <label className="field"><span>Resumption date</span><input type="date" value={form.resumption_date ?? ''} onChange={set('resumption_date')} /></label>
        </div>
        <label className="check-inline"><input type="checkbox" checked={form.is_active} onChange={set('is_active')} /> Active admission exercise</label>
      </form>
    </Modal>
  )
}

/** The Admissions Office's list of applications: status overview, search, filters and export. */
export default function AdmissionsList() {
  const navigate = useNavigate()
  const [filters, setFilters] = useState({ status: '', search: '', programme__department__faculty: '', programme: '', entry_mode: '', fee_paid: '', ordering: '-submitted_at' })
  const [page, setPage] = useState(1)
  const [editingCycle, setEditingCycle] = useState(false)
  const [exportError, setExportError] = useState('')
  const [exporting, setExporting] = useState('')
  const search = useDebounced(filters.search)
  const params = { ...filters, search, page }
  const { data, loading, error } = useApi('/admissions/applications/', params)
  const { data: summary, reload: reloadSummary } = useApi('/admissions/applications/summary/')
  const { data: faculties } = useApi('/academics/faculties/')
  const { data: programmes } = useApi('/academics/programmes/', filters.programme__department__faculty ? { department__faculty: filters.programme__department__faculty } : {})
  const set = (key, reset = []) => (e) => {
    setPage(1)
    setFilters({ ...filters, [key]: e.target.value, ...Object.fromEntries(reset.map((k) => [k, ''])) })
  }
  const rows = results(data)
  const cycle = summary?.cycle

  const exportAs = async (file) => {
    setExporting(file)
    setExportError('')
    try {
      const { page: _page, ...query } = params
      await downloadFile('/admissions/applications/export/', { ...query, file }, `applications.${file}`)
    } catch (err) {
      setExportError(await blobErrorMessage(err))
    } finally {
      setExporting('')
    }
  }

  return (
    <div className="stack-lg">
      <PageHeader
        title="Admissions"
        subtitle={cycle
          ? `${cycle.session} admission · ${cycle.is_open ? `open until ${formatDate(cycle.closes_on)}` : 'closed'} · fee ${formatMoney(cycle.application_fee)}`
          : 'No active admission exercise'}
        actions={
          <>
            <button className="btn btn-ghost" onClick={() => setEditingCycle(true)}><Icon name="calendar" size={16} /> {cycle ? 'Settings' : 'New admission exercise'}</button>
            <button className="btn btn-ghost" onClick={() => exportAs('csv')} disabled={Boolean(exporting)}><Icon name="download" size={16} /> {exporting === 'csv' ? 'Exporting…' : 'CSV'}</button>
            <button className="btn btn-ghost" onClick={() => exportAs('xlsx')} disabled={Boolean(exporting)}><Icon name="download" size={16} /> {exporting === 'xlsx' ? 'Exporting…' : 'Excel'}</button>
          </>
        }
      />
      <Alert>{exportError}</Alert>

      {summary && (
        <div className="status-chips" role="tablist" aria-label="Filter by status">
          <button role="tab" aria-selected={!filters.status} className={`status-chip ${!filters.status ? 'active' : ''}`}
                  onClick={() => set('status')({ target: { value: '' } })}>
            <strong>{summary.submitted_total}</strong><span>All submitted</span>
          </button>
          {STAGES.map((s) => (
            <button key={s} role="tab" aria-selected={filters.status === s} className={`status-chip tone-chip-${STATUS_TONE[s]} ${filters.status === s ? 'active' : ''}`}
                    onClick={() => set('status')({ target: { value: s } })}>
              <strong>{summary.by_status[s]}</strong><span>{s === 'draft' ? 'Drafts' : STATUS_LABEL[s]}</span>
            </button>
          ))}
        </div>
      )}

      <div className="toolbar">
        <label className="search">
          <Icon name="search" />
          <input placeholder="Search name, email, application or JAMB number" value={filters.search} onChange={set('search')} aria-label="Search applications" />
        </label>
        <select value={filters.programme__department__faculty} onChange={set('programme__department__faculty', ['programme'])} aria-label="Faculty">
          <option value="">All faculties</option>
          {faculties?.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
        </select>
        <select value={filters.programme} onChange={set('programme')} aria-label="Programme">
          <option value="">All programmes</option>
          {results(programmes).map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
        </select>
        <select value={filters.entry_mode} onChange={set('entry_mode')} aria-label="Entry mode">
          <option value="">All entry modes</option>
          {ENTRY_MODES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <select value={filters.fee_paid} onChange={set('fee_paid')} aria-label="Fee">
          <option value="">Fee paid or not</option><option value="true">Fee paid</option><option value="false">Fee not paid</option>
        </select>
        <select value={filters.ordering} onChange={set('ordering')} aria-label="Sort">
          {ORDERINGS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </div>

      {error && <Alert>{error}</Alert>}
      {loading && !data ? <Spinner /> : rows.length === 0 ? (
        <EmptyState icon="cap" title="No applications match">Try another status or clear the filters.</EmptyState>
      ) : (
        <Card padded={false} className={loading ? 'is-loading' : ''}>
          <table className="table table-clickable">
            <thead>
              <tr>
                <th>Applicant</th><th>Programme</th><th className="num">UTME</th><th className="num">Screening</th>
                <th className="num">Aggregate</th><th>Documents</th><th>Status</th><th>Submitted</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((a) => (
                <tr key={a.id} onClick={() => navigate(`/portal/manage/admissions/${a.id}`)}>
                  <td>
                    <div className="person">
                      <Avatar name={a.applicant_name} size={34} />
                      <div>
                        <div className="cell-title">{a.applicant_name}</div>
                        <div className="muted small mono">{a.number}</div>
                      </div>
                    </div>
                  </td>
                  <td><div>{a.programme_name || '—'}</div><div className="muted small">{a.faculty_name}</div></td>
                  <td className="num">{a.utme_score ?? '—'}</td>
                  <td className="num">{score(a.screening_score)}</td>
                  <td className="num strong">{score(a.aggregate_score)}</td>
                  <td>{a.documents_pending ? <Badge tone="amber">{a.documents_pending} to verify</Badge> : <span className="muted small">—</span>}</td>
                  <td><Badge tone={STATUS_TONE[a.status]}>{a.status_label}</Badge>{!a.fee_paid && <div className="muted small">Fee not paid</div>}</td>
                  <td className="small nowrap">{a.submitted_at ? formatDate(a.submitted_at) : <span className="muted">Not submitted</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {(data.next || data.previous) && (
            <div className="pager">
              <span className="muted small">{data.count} applications · page {page}</span>
              <button className="btn btn-ghost btn-sm" disabled={!data.previous} onClick={() => setPage(page - 1)}>Previous</button>
              <button className="btn btn-ghost btn-sm" disabled={!data.next} onClick={() => setPage(page + 1)}>Next</button>
            </div>
          )}
        </Card>
      )}
      {editingCycle && (
        <CycleModal cycle={cycle} onClose={() => setEditingCycle(false)} onSaved={() => { setEditingCycle(false); reloadSummary() }} />
      )}
    </div>
  )
}

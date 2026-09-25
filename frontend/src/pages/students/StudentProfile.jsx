import { useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import api, { errorMessage } from '../../api/client'
import Icon from '../../components/Icon'
import { Alert, Avatar, Badge, Modal, Spinner } from '../../components/ui'
import useApi from '../../utils/useApi'
import {
  AcademicTab, AccommodationTab, ActivityTab, AttendanceTab, CoursesTab, DocumentsTab, FeesTab, OverviewTab, ResultsTab,
} from './ProfileTabs'
import StudentFormModal from './StudentFormModal'
import { STATUSES, STATUS_TONE } from './studentOptions'

const TABS = [
  ['overview', 'Overview'],
  ['academic', 'Academic Records'],
  ['courses', 'Courses'],
  ['attendance', 'Attendance'],
  ['results', 'Results'],
  ['fees', 'Fees'],
  ['documents', 'Documents'],
  ['accommodation', 'Accommodation'],
  ['activity', 'Activity History'],
]

function StatusModal({ student, onClose, onDone }) {
  const current = student.profile.status
  const [form, setForm] = useState({ status: STATUSES.find(([v]) => v !== current)[0], reason: '', effective_date: '' })
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      const { data } = await api.post(`/students/${student.id}/status/`, { ...form, effective_date: form.effective_date || undefined })
      onDone(data, `Status changed to ${STATUSES.find(([v]) => v === form.status)[1].toLowerCase()}. The student has been notified.`)
    } catch (err) {
      setError(errorMessage(err))
      setSaving(false)
    }
  }
  const leaving = ['withdrawn', 'expelled', 'graduated'].includes(form.status)
  return (
    <Modal title="Change academic status" onClose={onClose}
           footer={<><button className="btn btn-ghost" onClick={onClose}>Cancel</button><button className="btn btn-primary" form="status-form" disabled={saving}>{saving ? 'Saving…' : 'Change status'}</button></>}>
      <form id="status-form" className="form" onSubmit={submit}>
        <Alert>{error}</Alert>
        <p className="muted">Currently <Badge tone={STATUS_TONE[current]}>{student.profile.status_label}</Badge></p>
        <div className="form-row">
          <label className="field"><span>New status</span>
            <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
              {STATUSES.filter(([v]) => v !== current).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
          <label className="field"><span>Effective from</span>
            <input type="date" value={form.effective_date} onChange={(e) => setForm({ ...form, effective_date: e.target.value })} />
          </label>
        </div>
        <label className="field"><span>Reason (the student will see this)</span>
          <textarea rows={3} value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} minLength={5} maxLength={300} required
                    placeholder="e.g. Suspended for one semester by the Student Disciplinary Committee (ref. SDC/26/014)" />
        </label>
        {leaving && student.is_active && <p className="muted small">Consider also deactivating their portal access.</p>}
      </form>
    </Modal>
  )
}

function ActivationModal({ student, onClose, onDone }) {
  const activate = !student.is_active
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      const { data } = await api.post(`/students/${student.id}/activation/`, { active: activate, reason })
      onDone(data, activate ? 'Portal access restored.' : 'Portal access deactivated. The student can no longer sign in.')
    } catch (err) {
      setError(errorMessage(err))
      setSaving(false)
    }
  }
  return (
    <Modal title={activate ? 'Restore portal access' : 'Deactivate portal access'} onClose={onClose}
           footer={<><button className="btn btn-ghost" onClick={onClose}>Cancel</button><button className={`btn ${activate ? 'btn-primary' : 'btn-danger-ghost'}`} form="activation-form" disabled={saving}>{activate ? 'Activate' : 'Deactivate'}</button></>}>
      <form id="activation-form" className="form" onSubmit={submit}>
        <Alert>{error}</Alert>
        <p className="muted">
          {activate
            ? `${student.full_name} will be able to sign in to the student portal again.`
            : `${student.full_name} won't be able to sign in. Their records are kept, and their academic status doesn't change.`}
        </p>
        <label className="field"><span>Reason</span><input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} required={!activate} /></label>
      </form>
    </Modal>
  )
}

function PasswordModal({ student, onClose }) {
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const reset = async () => {
    setBusy(true)
    try {
      const { data } = await api.post(`/students/${student.id}/reset-password/`)
      setPassword(data.temporary_password)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }
  return (
    <Modal title="Reset password" onClose={onClose}
           footer={password ? <button className="btn btn-primary" onClick={onClose}>Done</button>
             : <><button className="btn btn-ghost" onClick={onClose}>Cancel</button><button className="btn btn-primary" onClick={reset} disabled={busy}>Reset password</button></>}>
      <div className="stack">
        <Alert>{error}</Alert>
        {password ? (
          <>
            <p>The new temporary password for <strong>{student.matric_number}</strong> is:</p>
            <p className="password-reveal mono">{password}</p>
            <p className="muted small">Give it to the student privately. It won't be shown again.</p>
          </>
        ) : <p className="muted">This replaces {student.full_name}'s password with a new temporary one. Their current password stops working.</p>}
      </div>
    </Modal>
  )
}

/** A student's full record: profile header with Registry actions, and tabs for every part of their record. */
export default function StudentProfile() {
  const { id } = useParams()
  const [params, setParams] = useSearchParams()
  const { data: student, loading, error, setData } = useApi(`/students/${id}/`)
  const [modal, setModal] = useState(null)
  const [notice, setNotice] = useState({ tone: 'success', text: '' })
  const [photoBusy, setPhotoBusy] = useState(false)
  const photoInput = useRef(null)

  if (loading && !student) return <Spinner />
  if (error && !student) return <Alert>{error}</Alert>

  const p = student.profile
  const tabs = TABS.filter(([key]) => key !== 'fees' || student.can_view_fees)
  const tab = tabs.some(([k]) => k === params.get('tab')) ? params.get('tab') : 'overview'
  const done = (data, text) => {
    setData((prev) => ({ ...prev, ...data }))
    setModal(null)
    setNotice({ tone: 'success', text })
  }
  const photo = async (file) => {
    if (!file) return
    setPhotoBusy(true)
    const body = new FormData()
    body.append('avatar', file)
    try {
      const { data } = await api.post(`/students/${id}/photo/`, body)
      done(data, 'Passport photograph updated.')
    } catch (err) {
      setNotice({ tone: 'error', text: errorMessage(err) })
    } finally {
      setPhotoBusy(false)
      photoInput.current.value = ''
    }
  }

  return (
    <div className="stack-lg">
      <Link to="/portal/manage/students" className="back-link"><Icon name="arrowLeft" size={16} /> Students</Link>
      <section className="student-header">
        <div className="student-photo">
          <Avatar name={student.full_name} src={student.avatar_url} size={112} />
          {student.can_manage && (
            <>
              <input ref={photoInput} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={(e) => photo(e.target.files[0])} />
              <button className="student-photo-btn" onClick={() => photoInput.current.click()} disabled={photoBusy} aria-label="Change passport photograph">
                <Icon name="camera" size={15} />
              </button>
            </>
          )}
        </div>
        <div className="grow">
          <div className="student-badges">
            <Badge tone={STATUS_TONE[p.status]}>{p.status_label}</Badge>
            {!student.is_active && <Badge tone="red">Portal access deactivated</Badge>}
          </div>
          <h1>{student.full_name}</h1>
          <div className="student-ids">
            <span><small>Matric no.</small><strong className="mono">{student.matric_number}</strong></span>
            <span><small>Student ID</small><strong className="mono">{p.student_id}</strong></span>
            <span><small>Level</small><strong>{p.level}</strong></span>
            <span><small>Session</small><strong>{p.current_session || '—'}</strong></span>
          </div>
          <p className="muted">{p.programme_title} · {p.department_name} · {p.faculty_name}</p>
        </div>
        {student.can_manage && (
          <div className="student-actions">
            <button className="btn btn-primary" onClick={() => setModal('edit')}><Icon name="register" size={16} /> Edit record</button>
            <button className="btn btn-ghost" onClick={() => setModal('status')}><Icon name="shield" size={16} /> Change status</button>
            <button className="btn btn-ghost" onClick={() => setModal('activation')}>
              <Icon name="lock" size={16} /> {student.is_active ? 'Deactivate access' : 'Restore access'}
            </button>
            <button className="btn btn-ghost" onClick={() => setModal('password')}><Icon name="lock" size={16} /> Reset password</button>
          </div>
        )}
      </section>
      <Alert tone={notice.tone} onClose={() => setNotice({ ...notice, text: '' })}>{notice.text}</Alert>

      <div className="tabs tabs-scroll" role="tablist">
        {tabs.map(([key, label]) => (
          <button key={key} role="tab" aria-selected={tab === key} className={`tab ${tab === key ? 'active' : ''}`}
                  onClick={() => setParams(key === 'overview' ? {} : { tab: key }, { replace: true })}>
            {label}
          </button>
        ))}
      </div>

      <div role="tabpanel">
        {tab === 'overview' && <OverviewTab student={student} />}
        {tab === 'academic' && <AcademicTab key={p.status} id={id} />}
        {tab === 'courses' && <CoursesTab id={id} />}
        {tab === 'attendance' && <AttendanceTab id={id} />}
        {tab === 'results' && <ResultsTab id={id} />}
        {tab === 'fees' && <FeesTab id={id} />}
        {tab === 'documents' && <DocumentsTab id={id} canManage={student.can_manage} />}
        {tab === 'accommodation' && <AccommodationTab />}
        {tab === 'activity' && <ActivityTab key={JSON.stringify([p.status, student.is_active, student.avatar_url])} id={id} />}
      </div>

      {modal === 'edit' && (
        <StudentFormModal student={student} onClose={() => setModal(null)} onSaved={(data) => done(data, 'Student record saved.')} />
      )}
      {modal === 'status' && <StatusModal student={student} onClose={() => setModal(null)} onDone={done} />}
      {modal === 'activation' && <ActivationModal student={student} onClose={() => setModal(null)} onDone={done} />}
      {modal === 'password' && <PasswordModal student={student} onClose={() => setModal(null)} />}
    </div>
  )
}

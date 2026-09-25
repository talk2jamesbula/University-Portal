import { useState } from 'react'
import api, { errorMessage, results } from '../../api/client'
import Icon from '../../components/Icon'
import { Alert, Modal } from '../../components/ui'
import useApi from '../../utils/useApi'
import { STATES } from '../admissions/admissions'
import { GENDERS, MODES_OF_ENTRY, levelsFor, sessions } from './studentOptions'

const BLANK = {
  first_name: '', last_name: '', email: '', phone: '', gender: '', date_of_birth: '',
  faculty: '', department: '', programme: '', level: 100, entry_session: '', current_session: '', mode_of_entry: 'utme',
  admission_date: '', jamb_reg_number: '',
  nationality: 'Nigerian', state_of_origin: '', lga: '', home_address: '', country: 'Nigeria',
  next_of_kin_name: '', next_of_kin_relationship: '', next_of_kin_phone: '', next_of_kin_address: '',
  emergency_contact_name: '', emergency_contact_relationship: '', emergency_contact_phone: '',
}

/** The form's values for an existing student (from the student detail API). */
function fromStudent(s) {
  const p = s.profile
  const pick = Object.fromEntries(Object.keys(BLANK).map((k) => [k, p[k] ?? s[k] ?? '']))
  return { ...pick, first_name: s.first_name, last_name: s.last_name, email: s.email, phone: s.phone }
}

function Field({ label, error, hint, children, wide }) {
  return (
    <label className={`field ${wide ? 'field-wide' : ''}`}>
      <span>{label}</span>
      {children}
      {hint && !error && <small className="muted">{hint}</small>}
      {error && <small className="field-error">{[].concat(error).join(' ')}</small>}
    </label>
  )
}

/**
 * Create a student (login and record together) or edit one. Faculty and department narrow the programme list;
 * the programme decides the student's department and faculty.
 */
export default function StudentFormModal({ student, onClose, onSaved }) {
  const editing = Boolean(student)
  const { data: faculties } = useApi('/academics/faculties/')
  const { data: departments } = useApi('/academics/departments/')
  const { data: programmeData } = useApi('/academics/programmes/')
  const programmes = results(programmeData)
  const [form, setForm] = useState(() => (editing ? fromStudent(student) : { ...BLANK, current_session: sessions()[1], entry_session: sessions()[1] }))
  const [errors, setErrors] = useState({})
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [created, setCreated] = useState(null)
  const [copied, setCopied] = useState(false)

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value })
  const deptList = (departments ?? []).filter((d) => !form.faculty || String(d.faculty) === String(form.faculty))
  const progList = programmes.filter((p) => (!form.department || String(p.department) === String(form.department))
    && (!form.faculty || deptList.some((d) => d.id === p.department)))
  const chosen = programmes.find((p) => String(p.id) === String(form.programme))
  const setProgramme = (e) => {
    const p = programmes.find((x) => String(x.id) === e.target.value)
    const d = departments?.find((x) => x.id === p?.department)
    setForm({ ...form, programme: e.target.value, ...(p ? { department: String(p.department), faculty: String(d?.faculty ?? form.faculty) } : {}) })
  }

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setErrors({})
    setError('')
    const { faculty: _f, department: _d, ...body } = form
    const payload = {
      ...body,
      level: Number(body.level),
      date_of_birth: body.date_of_birth || null,
      admission_date: body.admission_date || null,
    }
    try {
      const { data } = editing ? await api.put(`/students/${student.id}/`, payload) : await api.post('/students/', payload)
      if (editing) onSaved(data)
      else setCreated(data)
    } catch (err) {
      const fields = err.response?.data
      if (fields && typeof fields === 'object' && !fields.detail && !Array.isArray(fields)) {
        setErrors(fields)
        setError('Please correct the highlighted fields.')
      } else setError(errorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  if (created) {
    const copy = async () => {
      try { await navigator.clipboard.writeText(`${created.matric_number}\t${created.temporary_password}`); setCopied(true) } catch { /* no clipboard */ }
    }
    return (
      <Modal title="Student created" onClose={() => onSaved(created)}
             footer={<button className="btn btn-primary" onClick={() => onSaved(created)}>Open student profile</button>}>
        <div className="stack">
          <Alert tone="success">{created.full_name} has been added.</Alert>
          <dl className="facts">
            <div><dt>Matric number</dt><dd className="mono">{created.matric_number}</dd></div>
            <div><dt>Student ID</dt><dd className="mono">{created.profile.student_id}</dd></div>
            <div><dt>Username</dt><dd className="mono">{created.username}</dd></div>
            <div><dt>Temporary password</dt><dd className="mono">{created.temporary_password}</dd></div>
          </dl>
          <p className="muted small">
            Give the student their matric number and temporary password privately; this is the only time the password is shown.
            Ask them to change it after signing in.
          </p>
          <button className="btn btn-ghost btn-sm align-start" onClick={copy}><Icon name="check" size={14} /> {copied ? 'Copied' : 'Copy login details'}</button>
        </div>
      </Modal>
    )
  }

  const e = errors
  return (
    <Modal
      wide
      title={editing ? `Edit ${student.full_name}` : 'New student'}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" form="student-form" disabled={saving}>{saving ? 'Saving…' : editing ? 'Save changes' : 'Create student'}</button>
        </>
      }
    >
      <form id="student-form" className="form" onSubmit={submit} noValidate>
        <Alert>{error}</Alert>

        <h3 className="form-section">Personal details</h3>
        <div className="form-grid">
          <Field label="First name" error={e.first_name}><input value={form.first_name} onChange={set('first_name')} required /></Field>
          <Field label="Surname" error={e.last_name}><input value={form.last_name} onChange={set('last_name')} required /></Field>
          <Field label="Gender" error={e.gender}>
            <select value={form.gender} onChange={set('gender')} required>
              <option value="">Select…</option>
              {GENDERS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </Field>
          <Field label="Date of birth" error={e.date_of_birth}><input type="date" value={form.date_of_birth ?? ''} onChange={set('date_of_birth')} /></Field>
          <Field label="Email" error={e.email}><input type="email" value={form.email} onChange={set('email')} required /></Field>
          <Field label="Phone" error={e.phone}><input type="tel" value={form.phone} onChange={set('phone')} placeholder="08031234567" /></Field>
        </div>

        <h3 className="form-section">Programme and admission</h3>
        <div className="form-grid">
          <Field label="Faculty">
            <select value={form.faculty} onChange={(ev) => setForm({ ...form, faculty: ev.target.value, department: '', programme: '' })}>
              <option value="">All faculties</option>
              {faculties?.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
            </select>
          </Field>
          <Field label="Department">
            <select value={form.department} onChange={(ev) => setForm({ ...form, department: ev.target.value, programme: '' })}>
              <option value="">All departments</option>
              {deptList.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </Field>
          <Field label="Programme" error={e.programme}>
            <select value={form.programme} onChange={setProgramme} required>
              <option value="">Select…</option>
              {progList.map((p) => <option key={p.id} value={p.id}>{p.title}{p.is_active ? '' : ' (not admitting)'}</option>)}
            </select>
          </Field>
          <Field label="Level" error={e.level}>
            <select value={form.level} onChange={set('level')}>
              {levelsFor(chosen?.duration_years).map((l) => <option key={l} value={l}>{l} Level</option>)}
            </select>
          </Field>
          <Field label="Current session" error={e.current_session}>
            <select value={form.current_session} onChange={set('current_session')} required>
              <option value="">Select…</option>
              {sessions().map((s) => <option key={s}>{s}</option>)}
            </select>
          </Field>
          <Field label="Entry session" error={e.entry_session}>
            <select value={form.entry_session} onChange={set('entry_session')} required>
              <option value="">Select…</option>
              {sessions().map((s) => <option key={s}>{s}</option>)}
            </select>
          </Field>
          <Field label="Mode of entry" error={e.mode_of_entry}>
            <select value={form.mode_of_entry} onChange={set('mode_of_entry')}>
              {MODES_OF_ENTRY.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </Field>
          <Field label="Admission date" error={e.admission_date}><input type="date" value={form.admission_date ?? ''} onChange={set('admission_date')} /></Field>
          <Field label="JAMB registration no." error={e.jamb_reg_number}><input value={form.jamb_reg_number} onChange={set('jamb_reg_number')} placeholder="20261234AB" /></Field>
          <Field label="Matric number" hint={editing ? 'Assigned by the system; it can\'t be changed.' : 'Assigned automatically when you save.'}>
            <input value={editing ? student.matric_number : 'Automatic'} disabled readOnly />
          </Field>
        </div>

        <h3 className="form-section">Address and origin</h3>
        <div className="form-grid">
          <Field label="Home address" error={e.home_address} wide><input value={form.home_address} onChange={set('home_address')} /></Field>
          <Field label="State of origin" error={e.state_of_origin}>
            <select value={form.state_of_origin} onChange={set('state_of_origin')}>
              <option value="">Select…</option>
              {STATES.map((s) => <option key={s}>{s}</option>)}
            </select>
          </Field>
          <Field label="LGA" error={e.lga}><input value={form.lga} onChange={set('lga')} /></Field>
          <Field label="Country of residence" error={e.country}><input value={form.country} onChange={set('country')} /></Field>
          <Field label="Nationality" error={e.nationality}><input value={form.nationality} onChange={set('nationality')} /></Field>
        </div>

        <h3 className="form-section">Next of kin</h3>
        <div className="form-grid">
          <Field label="Full name" error={e.next_of_kin_name}><input value={form.next_of_kin_name} onChange={set('next_of_kin_name')} /></Field>
          <Field label="Relationship" error={e.next_of_kin_relationship}><input value={form.next_of_kin_relationship} onChange={set('next_of_kin_relationship')} /></Field>
          <Field label="Phone" error={e.next_of_kin_phone}><input type="tel" value={form.next_of_kin_phone} onChange={set('next_of_kin_phone')} /></Field>
          <Field label="Address" error={e.next_of_kin_address}><input value={form.next_of_kin_address} onChange={set('next_of_kin_address')} /></Field>
        </div>

        <h3 className="form-section">Emergency contact</h3>
        <div className="form-grid">
          <Field label="Full name" error={e.emergency_contact_name}><input value={form.emergency_contact_name} onChange={set('emergency_contact_name')} /></Field>
          <Field label="Relationship" error={e.emergency_contact_relationship}><input value={form.emergency_contact_relationship} onChange={set('emergency_contact_relationship')} /></Field>
          <Field label="Phone" error={e.emergency_contact_phone}><input type="tel" value={form.emergency_contact_phone} onChange={set('emergency_contact_phone')} /></Field>
        </div>
      </form>
    </Modal>
  )
}

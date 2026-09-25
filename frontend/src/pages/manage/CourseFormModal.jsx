import { useState } from 'react'
import api, { errorMessage } from '../../api/client'
import { Alert, Modal } from '../../components/ui'
import useApi from '../../utils/useApi'
import { EMPTY_OFFERING, LEVELS, SEMESTER_NUMBERS, offeringPayload } from './courseOptions'
import OfferingFields from './OfferingFields'

const EMPTY_COURSE = {
  code: '', title: '', department: '', units: 3, level: 100, semester_number: 1, description: '', is_active: true,
}

/**
 * Create a course (optionally adding it to programme curricula and offering it), or edit one.
 * Creation is all-or-nothing on the server.
 */
export default function CourseFormModal({ course, onClose, onSaved }) {
  const editing = Boolean(course)
  const { data: departments } = useApi('/academics/departments/')
  const { data: programmes } = useApi(editing ? null : '/academics/programmes/')
  const [form, setForm] = useState(editing ? { ...EMPTY_COURSE, ...course } : EMPTY_COURSE)
  const [curriculum, setCurriculum] = useState({}) // {programmeId: "compulsory" | "elective"}
  const [offer, setOffer] = useState(false)
  const [offering, setOffering] = useState(EMPTY_OFFERING)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })

  const toggleProgramme = (id, type) => setCurriculum((c) => {
    const next = { ...c }
    if (type) next[id] = type
    else delete next[id]
    return next
  })

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    const body = { ...form, units: Number(form.units), level: Number(form.level), semester_number: Number(form.semester_number) }
    try {
      let saved
      if (editing) {
        saved = (await api.patch(`/academics/courses/${course.id}/`, body)).data
      } else {
        body.curriculum = Object.entries(curriculum).map(([programme, type]) => ({
          programme: Number(programme), is_compulsory: type === 'compulsory',
        }))
        if (offer) body.offering = offeringPayload(offering)
        saved = (await api.post('/academics/courses/', body)).data
      }
      onSaved(saved)
    } catch (err) {
      setError(errorMessage(err))
      setSaving(false)
    }
  }

  return (
    <Modal
      title={editing ? `Edit ${course.code}` : 'New course'}
      onClose={onClose}
      wide={!editing}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" form="course-form" disabled={saving}>
            {saving ? 'Saving…' : editing ? 'Save changes' : 'Create course'}
          </button>
        </>
      }
    >
      <form id="course-form" className="form" onSubmit={submit}>
        <Alert>{error}</Alert>
        <div className="form-row">
          <label className="field field-narrow"><span>Course code</span>
            <input value={form.code} onChange={set('code')} required maxLength={12} placeholder="CSC207" autoFocus={!editing} />
          </label>
          <label className="field"><span>Title</span>
            <input value={form.title} onChange={set('title')} required maxLength={160} placeholder="Web Programming" />
          </label>
        </div>
        <div className="form-row">
          <label className="field"><span>Department</span>
            <select value={form.department} onChange={set('department')} required>
              <option value="">Select a department</option>
              {departments?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </label>
          <label className="field field-narrow"><span>Units</span>
            <input type="number" min="1" max="6" value={form.units} onChange={set('units')} required />
          </label>
        </div>
        <div className="form-row">
          <label className="field"><span>Level</span>
            <select value={form.level} onChange={set('level')}>
              {LEVELS.map((l) => <option key={l} value={l}>{l} Level</option>)}
            </select>
          </label>
          <label className="field"><span>Semester</span>
            <select value={form.semester_number} onChange={(e) => { set('semester_number')(e); setOffering({ ...offering, semester: '' }) }}>
              {SEMESTER_NUMBERS.map(([n, label]) => <option key={n} value={n}>{label}</option>)}
            </select>
          </label>
        </div>
        <label className="field"><span>Description (optional)</span>
          <textarea rows={3} value={form.description} onChange={set('description')} />
        </label>
        {editing && (
          <label className="checkbox"><input type="checkbox" checked={form.is_active} onChange={set('is_active')} /> Active (inactive courses can't be offered)</label>
        )}

        {!editing && (
          <>
            <h3 className="form-section">Add to programme curricula</h3>
            <p className="muted small">Students of these programmes will see the course at registration when they reach its level.</p>
            <div className="programme-picker">
              {programmes?.map((p) => (
                <div key={p.id} className={`programme-option ${curriculum[p.id] ? 'is-selected' : ''}`}>
                  <label className="checkbox">
                    <input type="checkbox" checked={Boolean(curriculum[p.id])}
                           onChange={(e) => toggleProgramme(p.id, e.target.checked ? 'compulsory' : null)} />
                    <span>{p.title}<span className="muted small"> · {p.department_name}</span></span>
                  </label>
                  {curriculum[p.id] && (
                    <select value={curriculum[p.id]} onChange={(e) => toggleProgramme(p.id, e.target.value)} aria-label={`${p.title}: course type`}>
                      <option value="compulsory">Compulsory</option>
                      <option value="elective">Elective</option>
                    </select>
                  )}
                </div>
              ))}
            </div>

            <h3 className="form-section">Offer the course</h3>
            <label className="checkbox"><input type="checkbox" checked={offer} onChange={(e) => setOffer(e.target.checked)} /> Offer it in a semester now</label>
            {offer && <OfferingFields value={offering} onChange={setOffering} semesterNumber={form.semester_number} />}
          </>
        )}
      </form>
    </Modal>
  )
}

import { useState } from 'react'
import api, { errorMessage } from '../../api/client'
import { Alert, Badge, Modal } from '../../components/ui'
import useApi from '../../utils/useApi'
import { MODE_OPTIONS } from './exams'

/** Schedule a course's exam, or change one (Exams Office). */
export default function ExamFormModal({ exam, semester, onClose, onSaved }) {
  const editing = Boolean(exam)
  const { data: unscheduled } = useApi(editing ? null : '/exams/timetable/unscheduled/', { semester })
  const { data: venues } = useApi('/exams/venues/', { is_active: true })
  const [form, setForm] = useState({
    offering: exam?.offering ?? '',
    date: exam?.date ?? '',
    start_time: exam?.start_time?.slice(0, 5) ?? '09:00',
    duration_minutes: exam?.duration_minutes ?? 120,
    mode: exam?.mode ?? 'paper',
    venues: exam?.venues ?? [],
    late_entry_minutes: exam?.late_entry_minutes ?? 30,
    instructions: exam?.instructions ?? '',
  })
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value })
  const toggleVenue = (id) =>
    setForm({ ...form, venues: form.venues.includes(id) ? form.venues.filter((v) => v !== id) : [...form.venues, id] })

  const course = editing ? exam : unscheduled?.find((o) => o.id === Number(form.offering))
  const students = course?.registered_count ?? null
  const seats = (venues ?? []).filter((v) => form.venues.includes(v.id)).reduce((sum, v) => sum + v.capacity, 0)

  const save = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      const payload = { ...form, offering: Number(form.offering) }
      const { data } = editing
        ? await api.patch(`/exams/timetable/${exam.id}/`, payload)
        : await api.post('/exams/timetable/', payload)
      onSaved(data)
    } catch (err) {
      setError(errorMessage(err))
      setSaving(false)
    }
  }

  return (
    <Modal
      wide
      title={editing ? `Change the ${exam.code} exam` : 'Schedule an exam'}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" form="exam-form" disabled={saving}>{saving ? 'Saving…' : 'Save'}</button>
        </>
      }
    >
      <form id="exam-form" className="form" onSubmit={save}>
        <Alert>{error}</Alert>
        {editing && exam.status === 'published' && (
          <Alert tone="info">This exam is on the timetable. Changing the date, time or venue notifies every candidate by email and SMS.</Alert>
        )}
        {!editing && (
          <label className="field">
            <span>Course</span>
            <select value={form.offering} onChange={set('offering')} required>
              <option value="">{unscheduled ? (unscheduled.length ? 'Choose a course…' : 'Every course already has an exam') : 'Loading…'}</option>
              {unscheduled?.map((o) => (
                <option key={o.id} value={o.id}>{o.code} · {o.title} ({o.registered_count} students)</option>
              ))}
            </select>
          </label>
        )}
        <div className="form-row">
          <label className="field"><span>Date</span><input type="date" value={form.date} onChange={set('date')} required /></label>
          <label className="field"><span>Start time</span><input type="time" value={form.start_time} onChange={set('start_time')} required /></label>
          <label className="field">
            <span>Duration (minutes)</span>
            <input type="number" min="10" max="360" step="5" value={form.duration_minutes} onChange={set('duration_minutes')} required />
          </label>
        </div>
        <div className="form-row">
          <label className="field">
            <span>Mode</span>
            <select value={form.mode} onChange={set('mode')}>
              {MODE_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          {form.mode === 'cbt' && (
            <label className="field">
              <span>Late entry allowed for (minutes)</span>
              <input type="number" min="0" max="120" value={form.late_entry_minutes} onChange={set('late_entry_minutes')} required />
            </label>
          )}
        </div>
        <fieldset className="field">
          <span>
            Venues{' '}
            {students != null && (
              <span className={`small ${seats && seats < students ? 'text-red' : 'muted'}`}>
                · {seats} seats chosen for {students} students
              </span>
            )}
          </span>
          <div className="venue-picker">
            {venues?.length === 0 && <p className="muted small">Add venues on the Venues tab first.</p>}
            {venues?.map((v) => (
              <label key={v.id} className={`venue-option ${form.venues.includes(v.id) ? 'is-selected' : ''}`}>
                <input type="checkbox" checked={form.venues.includes(v.id)} onChange={() => toggleVenue(v.id)} />
                <span className="grow">
                  <span className="cell-title">{v.name}</span>
                  <span className="muted small"> · {v.capacity} seats{v.location && ` · ${v.location}`}</span>
                </span>
                {v.is_cbt_centre && <Badge tone="purple">CBT</Badge>}
              </label>
            ))}
          </div>
        </fieldset>
        <label className="field">
          <span>Instructions to candidates (optional)</span>
          <textarea rows={2} value={form.instructions} onChange={set('instructions')} placeholder="e.g. Answer question 1 and any three others." />
        </label>
      </form>
    </Modal>
  )
}

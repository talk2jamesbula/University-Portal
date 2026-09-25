import useApi from '../../utils/useApi'
import { WEEKDAYS } from './courseOptions'

/**
 * Semester, lecturer, capacity, lecture days/times and venue for a course offering.
 * Only semesters matching the course's semester number are listed.
 */
export default function OfferingFields({ value, onChange, semesterNumber, lockSemester = false }) {
  const { data: semesters } = useApi('/academics/semesters/')
  const { data: lecturers } = useApi('/academics/lecturers/')
  const set = (key) => (e) => onChange({ ...value, [key]: e.target.value })
  const days = value.days ? value.days.split(',') : []
  const toggleDay = (day) => {
    const next = days.includes(day) ? days.filter((d) => d !== day) : [...days, day]
    onChange({ ...value, days: WEEKDAYS.map(([d]) => d).filter((d) => next.includes(d)).join(',') })
  }
  const choices = (semesters || []).filter((s) => !semesterNumber || s.number === Number(semesterNumber))

  return (
    <>
      <div className="form-row">
        <label className="field"><span>Semester</span>
          <select value={value.semester} onChange={set('semester')} required disabled={lockSemester}>
            <option value="">Select a semester</option>
            {choices.map((s) => <option key={s.id} value={s.id}>{s.name}{s.is_current ? ' (current)' : ''}</option>)}
          </select>
        </label>
        <label className="field"><span>Lecturer</span>
          <select value={value.lecturer ?? ''} onChange={set('lecturer')}>
            <option value="">To be assigned</option>
            {lecturers?.map((l) => <option key={l.id} value={l.id}>{l.name}{l.department ? ` · ${l.department}` : ''}</option>)}
          </select>
        </label>
      </div>
      <fieldset className="field day-picker">
        <legend>Lecture days</legend>
        <div className="chips">
          {WEEKDAYS.map(([code, label]) => (
            <button type="button" key={code} className={`chip ${days.includes(code) ? 'active' : ''}`}
                    aria-pressed={days.includes(code)} onClick={() => toggleDay(code)}>
              {label}
            </button>
          ))}
        </div>
      </fieldset>
      <div className="form-row">
        <label className="field"><span>Starts</span><input type="time" value={value.start_time ?? ''} onChange={set('start_time')} step="900" /></label>
        <label className="field"><span>Ends</span><input type="time" value={value.end_time ?? ''} onChange={set('end_time')} step="900" /></label>
        <label className="field"><span>Capacity</span><input type="number" min="1" value={value.capacity} onChange={set('capacity')} /></label>
      </div>
      <label className="field"><span>Venue</span><input value={value.venue ?? ''} onChange={set('venue')} maxLength={80} placeholder="e.g. LT 1, Science Auditorium" /></label>
    </>
  )
}

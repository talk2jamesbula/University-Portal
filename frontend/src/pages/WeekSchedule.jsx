import { WEEKDAYS, formatTimeRange } from '../utils/format'

const DAY_LABELS = { MON: 'Monday', TUE: 'Tuesday', WED: 'Wednesday', THU: 'Thursday', FRI: 'Friday' }
const PALETTE = ['blue', 'purple', 'green', 'amber', 'teal', 'rose']

/** A compact Mon–Fri agenda: each day lists its classes in time order. */
export default function WeekSchedule({ courses }) {
  const colorFor = Object.fromEntries(courses.map((c, i) => [c.id, PALETTE[i % PALETTE.length]]))
  const today = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'][new Date().getDay()]

  return (
    <div className="week">
      {WEEKDAYS.map((day) => {
        const classes = courses
          .filter((c) => c.days?.split(',').includes(day))
          .sort((a, b) => (a.start_time || '').localeCompare(b.start_time || ''))
        return (
          <div key={day} className={`week-day ${day === today ? 'is-today' : ''}`}>
            <div className="week-day-name">{DAY_LABELS[day]}</div>
            {classes.length ? (
              classes.map((c) => (
                <div key={c.id} className={`week-class tone-${colorFor[c.id]}`}>
                  <strong>{c.code}</strong>
                  <span>{formatTimeRange(c.start_time, c.end_time)}</span>
                  <span className="week-class-loc">{c.venue}</span>
                </div>
              ))
            ) : (
              <div className="week-free">No classes</div>
            )}
          </div>
        )
      })}
    </div>
  )
}

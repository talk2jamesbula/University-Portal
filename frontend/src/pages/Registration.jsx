import { useState } from 'react'
import api, { errorMessage } from '../api/client'
import Icon from '../components/Icon'
import { Alert, Badge, Card, EmptyState, PageHeader, Spinner } from '../components/ui'
import { formatSchedule } from '../utils/format'
import useApi from '../utils/useApi'

const STATE = {
  not_started: { label: 'Not started', tone: 'red', text: "You haven't registered any courses for this semester." },
  incomplete: { label: 'Incomplete', tone: 'amber', text: 'Register more courses to reach the minimum unit load.' },
  complete: { label: 'Complete', tone: 'green', text: 'Your registration meets the unit requirement.' },
}

function UnitMeter({ units, min, max }) {
  const pct = Math.min(100, (units / max) * 100)
  return (
    <div className="unit-meter" aria-label={`${units} of ${max} units`}>
      <div className="unit-meter-bar">
        <span className={units < min ? 'tone-bg-amber' : 'tone-bg-green'} style={{ width: `${pct}%` }} />
        <i style={{ left: `${(min / max) * 100}%` }} title={`Minimum ${min} units`} />
      </div>
      <div className="unit-meter-labels small muted">
        <span><strong className="text-strong">{units}</strong> units registered</span>
        <span>Minimum {min} · Maximum {max}</span>
      </div>
    </div>
  )
}

function CourseType({ course }) {
  if (course.is_carryover) return <Badge tone="red">Carry-over</Badge>
  return course.is_compulsory ? <Badge tone="blue">Compulsory</Badge> : <Badge>Elective</Badge>
}

export default function Registration() {
  const { data, loading, error, reload } = useApi('/academics/registration/')
  const [busy, setBusy] = useState(null)
  const [notice, setNotice] = useState({ tone: 'success', text: '' })

  if (loading && !data) return <Spinner />
  if (error) return <Alert>{error}</Alert>

  const { semester } = data
  const state = STATE[data.state]
  const open = semester.registration_open

  const act = async (offering, action) => {
    setBusy(offering.id)
    try {
      await api.post('/academics/registration/', { offering: offering.id, action })
      setNotice({ tone: 'success', text: action === 'drop' ? `Dropped ${offering.code}.` : `Registered ${offering.code}.` })
      reload()
    } catch (err) {
      setNotice({ tone: 'error', text: errorMessage(err) })
    } finally {
      setBusy(null)
    }
  }

  const available = data.available.filter((c) => !c.is_registered)

  return (
    <div className="stack-lg">
      <PageHeader
        title="Course Registration"
        subtitle={`${semester.name} · ${open ? 'Registration is open' : 'Registration is closed'}`}
      />

      <Card>
        <div className="registration-status">
          <div>
            <Badge tone={state.tone}>{state.label}</Badge>
            <p className="muted small">{state.text}</p>
          </div>
          <UnitMeter units={data.units} min={data.min_units} max={data.max_units} />
        </div>
      </Card>

      <Alert tone={notice.tone} onClose={() => setNotice({ ...notice, text: '' })}>{notice.text}</Alert>

      <Card title={`Registered courses (${data.registered.length})`} padded={false}>
        {data.registered.length === 0 ? (
          <EmptyState icon="register" title="No courses registered">Add courses from the list below.</EmptyState>
        ) : (
          <table className="table">
            <thead>
              <tr><th>Code</th><th>Title</th><th className="num">Units</th><th>Lecturer</th><th>Timetable</th><th /></tr>
            </thead>
            <tbody>
              {data.registered.map(({ offering_detail: o, is_carryover: carryover }) => (
                <tr key={o.id}>
                  <td className="cell-title">{o.code} {carryover && <Badge tone="red">Carry-over</Badge>}</td>
                  <td>{o.title}</td>
                  <td className="num">{o.units}</td>
                  <td>{o.lecturer_name || 'TBA'}</td>
                  <td className="small">{formatSchedule(o)} · {o.venue}</td>
                  <td className="align-right">
                    {open && (
                      <button className="btn btn-danger-ghost btn-sm" disabled={busy === o.id} onClick={() => act(o, 'drop')}>
                        {busy === o.id ? 'Dropping…' : 'Drop'}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot><tr><td colSpan={2}>Total</td><td className="num">{data.units}</td><td colSpan={3} /></tr></tfoot>
          </table>
        )}
      </Card>

      <Card title="Courses available to you" padded={false}>
        {available.length === 0 ? (
          <EmptyState icon="check" title="Nothing else to add">You've registered every course available to you this semester.</EmptyState>
        ) : (
          <table className="table">
            <thead>
              <tr><th>Code</th><th>Title</th><th>Type</th><th className="num">Units</th><th className="num">Level</th><th>Timetable</th><th /></tr>
            </thead>
            <tbody>
              {available.map((c) => (
                <tr key={c.id}>
                  <td className="cell-title">{c.code}</td>
                  <td>{c.title}<div className="muted small">{c.lecturer_name || 'Lecturer TBA'}</div></td>
                  <td><CourseType course={c} /></td>
                  <td className="num">{c.units}</td>
                  <td className="num">{c.level}</td>
                  <td className="small">{formatSchedule(c)} · {c.venue}</td>
                  <td className="align-right">
                    {open && (
                      <button className="btn btn-primary btn-sm" disabled={busy === c.id} onClick={() => act(c, 'add')}>
                        <Icon name="plus" size={14} /> {busy === c.id ? 'Adding…' : 'Add'}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  )
}

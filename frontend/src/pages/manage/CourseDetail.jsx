import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import api, { errorMessage, results } from '../../api/client'
import Icon from '../../components/Icon'
import { Alert, Card, EmptyState, Modal, PageHeader, Spinner } from '../../components/ui'
import { formatSchedule } from '../../utils/format'
import useApi from '../../utils/useApi'
import CourseFormModal from './CourseFormModal'
import { EMPTY_OFFERING, offeringPayload } from './courseOptions'
import OfferingFields from './OfferingFields'

function OfferingModal({ course, offering, onClose, onSaved }) {
  const editing = Boolean(offering)
  const [form, setForm] = useState(editing ? {
    ...EMPTY_OFFERING, ...offering, lecturer: offering.lecturer ?? '',
    start_time: offering.start_time?.slice(0, 5) ?? '', end_time: offering.end_time?.slice(0, 5) ?? '',
  } : EMPTY_OFFERING)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      const body = { ...offeringPayload(form), course: course.id }
      if (editing) await api.patch(`/academics/offerings/${offering.id}/`, body)
      else await api.post('/academics/offerings/', body)
      onSaved()
    } catch (err) {
      setError(errorMessage(err))
      setSaving(false)
    }
  }

  return (
    <Modal
      title={editing ? `Edit ${course.code} · ${offering.semester_name}` : `Offer ${course.code}`}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" form="offering-form" disabled={saving}>{saving ? 'Saving…' : 'Save'}</button>
        </>
      }
    >
      <form id="offering-form" className="form" onSubmit={submit}>
        <Alert>{error}</Alert>
        <OfferingFields value={form} onChange={setForm} semesterNumber={course.semester_number} lockSemester={editing} />
      </form>
    </Modal>
  )
}

function CurriculumTab({ course }) {
  const { data: entries, reload } = useApi('/academics/curriculum/', { course: course.id })
  const { data: programmes } = useApi('/academics/programmes/')
  const [adding, setAdding] = useState({ programme: '', type: 'compulsory' })
  const [error, setError] = useState('')
  const used = new Set((entries || []).map((e) => e.programme))

  const run = async (request) => {
    setError('')
    try {
      await request()
      reload()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <Card title="Programme curricula" padded={false}>
      <Alert onClose={() => setError('')}>{error}</Alert>
      {entries?.length ? (
        <table className="table">
          <thead><tr><th>Programme</th><th>Department</th><th>Type</th><th /></tr></thead>
          <tbody>
            {entries.map((e) => (
              <tr key={e.id}>
                <td className="cell-title">{e.programme_title}</td>
                <td>{e.department_name}</td>
                <td>
                  <select value={e.is_compulsory ? 'compulsory' : 'elective'} aria-label={`${e.programme_title}: course type`}
                          onChange={(ev) => run(() => api.patch(`/academics/curriculum/${e.id}/`, { is_compulsory: ev.target.value === 'compulsory' }))}>
                    <option value="compulsory">Compulsory</option>
                    <option value="elective">Elective</option>
                  </select>
                </td>
                <td className="align-right">
                  <button className="btn btn-danger-ghost btn-sm" onClick={() => window.confirm(`Remove ${course.code} from ${e.programme_title}?`) && run(() => api.delete(`/academics/curriculum/${e.id}/`))}>Remove</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : <EmptyState icon="catalog" title="Not in any programme yet">Students only see courses that are in their programme's curriculum.</EmptyState>}
      <form className="inline-form" onSubmit={(e) => {
        e.preventDefault()
        run(async () => {
          await api.post('/academics/curriculum/', { course: course.id, programme: adding.programme, is_compulsory: adding.type === 'compulsory' })
          setAdding({ programme: '', type: 'compulsory' })
        })
      }}>
        <select value={adding.programme} onChange={(e) => setAdding({ ...adding, programme: e.target.value })} required aria-label="Programme">
          <option value="">Add to a programme…</option>
          {programmes?.filter((p) => !used.has(p.id)).map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
        </select>
        <select value={adding.type} onChange={(e) => setAdding({ ...adding, type: e.target.value })} aria-label="Course type">
          <option value="compulsory">Compulsory</option>
          <option value="elective">Elective</option>
        </select>
        <button className="btn btn-ghost" disabled={!adding.programme}><Icon name="plus" size={16} /> Add</button>
      </form>
    </Card>
  )
}

function OfferingsTab({ course }) {
  const { data, reload } = useApi('/academics/offerings/', { course: course.id })
  const [modal, setModal] = useState(null) // "new" | offering
  const [error, setError] = useState('')
  const offerings = results(data)

  const remove = async (o) => {
    if (!window.confirm(`Stop offering ${course.code} in ${o.semester_name}?`)) return
    try {
      await api.delete(`/academics/offerings/${o.id}/`)
      reload()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <Card
      title="Offerings by semester"
      padded={false}
      action={course.is_active && <button className="btn btn-primary btn-sm" onClick={() => setModal('new')}><Icon name="plus" size={14} /> Offer in a semester</button>}
    >
      <Alert onClose={() => setError('')}>{error}</Alert>
      {offerings.length ? (
        <table className="table">
          <thead><tr><th>Semester</th><th>Lecturer</th><th>Timetable</th><th>Venue</th><th className="num">Registered</th><th /></tr></thead>
          <tbody>
            {offerings.map((o) => (
              <tr key={o.id}>
                <td className="cell-title">{o.semester_name}</td>
                <td>{o.lecturer_name || <span className="muted">To be assigned</span>}</td>
                <td>{formatSchedule(o)}</td>
                <td>{o.venue || '—'}</td>
                <td className="num">{o.registered_count} / {o.capacity}</td>
                <td>
                  <div className="row-actions">
                    <button className="btn btn-ghost btn-sm" onClick={() => setModal(o)}>Edit</button>
                    <button className="btn btn-danger-ghost btn-sm" onClick={() => remove(o)}>Remove</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : <EmptyState icon="calendar" title="Not offered yet" />}
      {modal && (
        <OfferingModal
          course={course}
          offering={modal === 'new' ? null : modal}
          onClose={() => setModal(null)}
          onSaved={() => { setModal(null); reload() }}
        />
      )}
    </Card>
  )
}

export default function CourseDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { data: course, error, setData } = useApi(`/academics/courses/${id}/`)
  const [tab, setTab] = useState('curriculum')
  const [editing, setEditing] = useState(false)
  const [notice, setNotice] = useState({ tone: 'success', text: '' })

  if (error) return <Alert>{error}</Alert>
  if (!course) return <Spinner />

  const remove = async () => {
    if (!window.confirm(`Delete ${course.code} from the catalogue?`)) return
    try {
      await api.delete(`/academics/courses/${course.id}/`)
      navigate('/portal/manage/courses', { replace: true })
    } catch (err) {
      setNotice({ tone: 'error', text: errorMessage(err) })
    }
  }

  return (
    <div className="stack-lg">
      <button onClick={() => navigate('/portal/manage/courses')} className="back-link"><Icon name="arrowLeft" size={16} /> All courses</button>
      <PageHeader
        title={`${course.code} · ${course.title}`}
        subtitle={`${course.department_name} · ${course.units} units · ${course.level} Level · ${course.semester_label}`}
        actions={
          <>
            <button className="btn btn-danger-ghost" onClick={remove}>Delete</button>
            <button className="btn btn-primary" onClick={() => setEditing(true)}>Edit course</button>
          </>
        }
      />
      {!course.is_active && <Alert>This course is inactive and can't be offered.</Alert>}
      <Alert tone={notice.tone} onClose={() => setNotice({ ...notice, text: '' })}>{notice.text}</Alert>
      {course.description && <p className="muted">{course.description}</p>}
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === 'curriculum'} className={`tab ${tab === 'curriculum' ? 'active' : ''}`} onClick={() => setTab('curriculum')}>
          Curriculum
        </button>
        <button role="tab" aria-selected={tab === 'offerings'} className={`tab ${tab === 'offerings' ? 'active' : ''}`} onClick={() => setTab('offerings')}>
          Offerings
        </button>
      </div>
      {tab === 'curriculum' ? <CurriculumTab course={course} /> : <OfferingsTab course={course} />}
      {editing && (
        <CourseFormModal
          course={course}
          onClose={() => setEditing(false)}
          onSaved={(saved) => {
            setEditing(false)
            setData(saved)
            setNotice({ tone: 'success', text: 'Course updated.' })
          }}
        />
      )}
    </div>
  )
}

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api, { errorMessage } from '../../api/client'
import Icon from '../../components/Icon'
import { Alert, Badge, Card, EmptyState, Modal, PageHeader, Spinner, Stat } from '../../components/ui'
import { formatDate, formatTime } from '../../utils/format'
import useApi from '../../utils/useApi'
import ExamFormModal from './ExamFormModal'
import { EXAM_STATUS_TONE, MODE_TONE, formatDuration } from './exams'
import Venues from './Venues'

function Problems({ problems }) {
  if (!problems?.length) {
    return <Alert tone="success">No clashes or seating problems on this timetable.</Alert>
  }
  return (
    <Card title={`Problems to fix (${problems.length})`}>
      <ul className="problem-list">
        {problems.map((p) => (
          <li key={`${p.exams.join('-')}-${p.message}`} className={`problem problem-${p.level}`}>
            <Icon name="alert" size={16} /> <span>{p.message}</span>
          </li>
        ))}
      </ul>
    </Card>
  )
}

function PublishModal({ drafts, semester, errors, onClose, onDone }) {
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const publish = async () => {
    setBusy(true)
    setError('')
    try {
      const { data } = await api.post('/exams/timetable/publish/', { semester, exams: drafts.map((d) => d.id) })
      onDone(data)
    } catch (err) {
      setError(errorMessage(err))
      setBusy(false)
    }
  }
  const students = drafts.reduce((sum, d) => sum + (d.registered_count || 0), 0)
  return (
    <Modal
      title={`Publish ${drafts.length} exam${drafts.length === 1 ? '' : 's'}?`}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={publish} disabled={busy}>{busy ? 'Publishing…' : 'Publish timetable'}</button>
        </>
      }
    >
      <div className="stack">
        <Alert>{error}</Alert>
        {errors > 0 && (
          <div className="callout callout-danger">
            <Icon name="alert" />
            <span>The timetable still has {errors} serious problem{errors === 1 ? '' : 's'} (clashes or too few seats). Fix them first if you can.</span>
          </div>
        )}
        <p>
          Every student is given a seat, and the {students} student places on these exams are notified by email. Students can then
          download their exam cards.
        </p>
      </div>
    </Modal>
  )
}

/** The Examinations Office's timetable: schedule exams, check clashes, allocate seats and publish. */
export default function ExamTimetable() {
  const navigate = useNavigate()
  const { data: semesters } = useApi('/academics/semesters/')
  const [semesterId, setSemesterId] = useState('')
  const [tab, setTab] = useState('timetable')
  const [creating, setCreating] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [notice, setNotice] = useState('')
  const [query, setQuery] = useState('')

  const semester = semesterId || semesters?.find((s) => s.is_current)?.id || ''
  const { data: exams, error, reload } = useApi(semester ? '/exams/timetable/' : null, { semester })
  const { data: problems, reload: reloadProblems } = useApi(semester ? '/exams/timetable/problems/' : null, { semester })

  if (error && !exams) return <Alert>{error}</Alert>
  if (!semesters || (semester && !exams)) return <Spinner />

  const refresh = () => { reload(); reloadProblems() }
  const drafts = (exams ?? []).filter((e) => e.status === 'draft')
  const q = query.toLowerCase()
  const rows = (exams ?? []).filter((e) => !q || `${e.code} ${e.title} ${e.lecturer_name}`.toLowerCase().includes(q))
  const byDate = rows.reduce((groups, e) => ({ ...groups, [e.date]: [...(groups[e.date] || []), e] }), {})
  const errors = (problems ?? []).filter((p) => p.level === 'error').length

  return (
    <div className="stack-lg">
      <PageHeader
        title="Examination Timetable"
        subtitle="Schedule exams, check clashes and seating, then publish to students"
        actions={
          <>
            <select value={semester} onChange={(e) => setSemesterId(e.target.value)} aria-label="Semester">
              {semesters.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
            <button className="btn btn-ghost" onClick={() => setCreating(true)}><Icon name="plus" size={16} /> Schedule exam</button>
            <button className="btn btn-primary" onClick={() => setPublishing(true)} disabled={!drafts.length}>
              <Icon name="send" size={16} /> Publish {drafts.length ? `${drafts.length} draft${drafts.length === 1 ? '' : 's'}` : 'timetable'}
            </button>
          </>
        }
      />
      <Alert tone="success" onClose={() => setNotice('')}>{notice}</Alert>

      <div className="stats-grid">
        <Stat icon="calendar" label="Exams scheduled" value={exams?.length ?? 0} />
        <Stat icon="check" label="On the timetable" value={(exams?.length ?? 0) - drafts.length} tone="green" />
        <Stat icon="qr" label="Computer-based" value={(exams ?? []).filter((e) => e.mode === 'cbt').length} tone="purple" />
        <Stat icon="alert" label="Problems" value={problems?.length ?? 0} tone={errors ? 'red' : problems?.length ? 'amber' : 'green'} />
      </div>

      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === 'timetable'} className={`tab ${tab === 'timetable' ? 'active' : ''}`} onClick={() => setTab('timetable')}>Timetable</button>
        <button role="tab" aria-selected={tab === 'venues'} className={`tab ${tab === 'venues' ? 'active' : ''}`} onClick={() => setTab('venues')}>Venues</button>
      </div>

      {tab === 'venues' ? <Venues /> : (
        <>
          {problems && <Problems problems={problems} />}
          <div className="toolbar">
            <label className="search search-sm">
              <Icon name="search" size={16} />
              <input placeholder="Filter by course or lecturer" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Filter exams" />
            </label>
          </div>
          {rows.length === 0 ? (
            <EmptyState icon="calendar" title={exams?.length ? 'No matching exams' : 'No exams scheduled yet'}>
              {exams?.length ? null : 'Schedule an exam for each course offered this semester.'}
            </EmptyState>
          ) : Object.entries(byDate).map(([date, dayExams]) => (
            <Card key={date} title={formatDate(date, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })} padded={false}>
              <table className="table table-clickable">
                <thead>
                  <tr><th>Time</th><th>Course</th><th>Mode</th><th>Venues</th><th className="num">Seated</th><th>Status</th><th /></tr>
                </thead>
                <tbody>
                  {dayExams.map((e) => {
                    const short = e.seated_count < e.registered_count
                    return (
                      <tr key={e.id} onClick={() => navigate(`/portal/manage/exams/${e.id}`)}>
                        <td className="nowrap">{formatTime(e.start_time)}<div className="muted small">{formatDuration(e.duration_minutes)}</div></td>
                        <td><div className="cell-title">{e.code}</div><div className="muted small">{e.title}</div></td>
                        <td><Badge tone={MODE_TONE[e.mode]}>{e.mode === 'cbt' ? 'CBT' : 'Paper'}</Badge></td>
                        <td className="small">{e.venue_details.map((v) => v.name).join(', ') || <span className="text-red">No venue</span>}</td>
                        <td className={`num ${e.status === 'published' && short ? 'text-red' : ''}`}>{e.seated_count} / {e.registered_count}</td>
                        <td><Badge tone={EXAM_STATUS_TONE[e.status]}>{e.status_label}</Badge></td>
                        <td className="align-right"><Icon name="chevronRight" size={16} /></td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </Card>
          ))}
        </>
      )}

      {creating && (
        <ExamFormModal
          semester={semester}
          onClose={() => setCreating(false)}
          onSaved={(exam) => { setCreating(false); setNotice(`Scheduled the ${exam.code} exam as a draft.`); refresh() }}
        />
      )}
      {publishing && (
        <PublishModal
          drafts={drafts}
          semester={semester}
          errors={errors}
          onClose={() => setPublishing(false)}
          onDone={(result) => {
            setPublishing(false)
            setNotice(`Published ${result.published} exam${result.published === 1 ? '' : 's'}. ${result.students} students have been notified.`)
            refresh()
          }}
        />
      )}
    </div>
  )
}

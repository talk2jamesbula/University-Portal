import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import api, { blobErrorMessage, errorMessage } from '../../api/client'
import Icon from '../../components/Icon'
import { Alert, Badge, Card, EmptyState, Spinner, Stat } from '../../components/ui'
import { CHARGE_STATUS, formatDate, formatDateTime, formatMoney } from '../../utils/format'
import useApi from '../../utils/useApi'
import openFile from '../admissions/openFile'
import { formatSize } from '../admissions/admissions'
import { STATUS_TONE as ATTENDANCE_TONE, formatPercent } from '../attendance/attendance'
import PercentBar from '../attendance/PercentBar'
import { STATUS_TONE } from './studentOptions'

const fixed = (n) => (n == null ? '—' : Number(n).toFixed(2))
const score = (n) => (n == null ? '—' : Number(n).toFixed(1).replace(/\.0$/, ''))
const GRADE_TONE = { A: 'green', B: 'blue', C: 'blue', D: 'amber', E: 'amber', F: 'red' }

/** Loads one tab's data; shows the spinner and errors the same way for every tab. */
function TabData({ url, children }) {
  const { data, loading, error, reload } = useApi(url)
  if (error) return <Alert>{error}</Alert>
  if (loading && !data) return <Spinner />
  return children(data, reload)
}

function Facts({ rows }) {
  return (
    <dl className="facts facts-wide">
      {rows.map(([label, value], i) => <div key={i}><dt>{label}</dt><dd>{value || value === 0 ? value : <span className="muted">—</span>}</dd></div>)}
    </dl>
  )
}

export function OverviewTab({ student }) {
  const p = student.profile
  return (
    <div className="grid-2">
      <div className="stack-lg">
        <Card title="Personal details">
          <Facts rows={[
            ['Full name', student.full_name],
            ['Gender', p.gender_label],
            ['Date of birth', p.date_of_birth && formatDate(p.date_of_birth)],
            ['Nationality', p.nationality],
            ['State of origin', p.state_of_origin],
            ['LGA', p.lga],
          ]} />
        </Card>
        <Card title="Contact">
          <Facts rows={[
            ['Email', student.email && <a key="e" href={`mailto:${student.email}`} className="link">{student.email}</a>],
            ['Phone', student.phone && <a key="p" href={`tel:${student.phone}`} className="link">{student.phone}</a>],
            ['Address', p.home_address],
            ['Country', p.country],
          ]} />
        </Card>
        <Card title="Next of kin and emergency contact">
          <Facts rows={[
            ['Next of kin', [p.next_of_kin_name, p.next_of_kin_relationship].filter(Boolean).join(' · ')],
            ['Phone', p.next_of_kin_phone],
            ['Address', p.next_of_kin_address],
            ['Emergency contact', [p.emergency_contact_name, p.emergency_contact_relationship].filter(Boolean).join(' · ')],
            ['Phone', p.emergency_contact_phone],
          ]} />
        </Card>
      </div>
      <div className="stack-lg">
        <Card title="Programme">
          <Facts rows={[
            ['Programme', p.programme_title],
            ['Department', p.department_name],
            ['Faculty', p.faculty_name],
            ['Level', `${p.level} Level`],
            ['Current session', p.current_session],
            ['Academic status', <Badge key="s" tone={STATUS_TONE[p.status]}>{p.status_label}</Badge>],
          ]} />
        </Card>
        <Card title="Admission">
          <Facts rows={[
            ['Matric number', <span key="m" className="mono">{student.matric_number}</span>],
            ['Student ID', <span key="i" className="mono">{p.student_id}</span>],
            ['Entry session', p.entry_session],
            ['Mode of entry', p.mode_of_entry_label],
            ['Admission date', p.admission_date && formatDate(p.admission_date)],
            ['JAMB reg. no.', p.jamb_reg_number && <span key="j" className="mono">{p.jamb_reg_number}</span>],
          ]} />
        </Card>
        <Card title="Portal account">
          <Facts rows={[
            ['Username', <span key="u" className="mono">{student.username}</span>],
            ['Access', student.is_active ? <Badge key="a" tone="green">Active</Badge> : <Badge key="a" tone="red">Deactivated</Badge>],
            ['Last sign-in', student.last_login ? formatDateTime(student.last_login) : 'Never'],
            ['Record created', formatDate(student.date_joined)],
          ]} />
        </Card>
      </div>
    </div>
  )
}

export function AcademicTab({ id }) {
  return (
    <TabData url={`/students/${id}/academic-records/`}>
      {(data) => (
        <div className="stack-lg">
          <div className="stats-grid">
            <Stat icon="award" label="CGPA (5.00 scale)" value={fixed(data.cgpa)} tone="green" />
            <Stat icon="check" label="Units passed" value={`${data.units_passed} / ${data.units_taken}`} />
            <Stat icon="cap" label="Class of degree (current)" value={data.degree_class || '—'} tone="purple" />
            <Stat icon="shield" label="Academic standing" value={data.standing} tone={data.standing === 'Good standing' ? 'green' : 'amber'} />
          </div>
          <div className="grid-2">
            <Card title="GPA by semester" padded={false}>
              {data.semesters.length === 0 ? <EmptyState icon="award" title="No published results yet" /> : (
                <table className="table">
                  <thead><tr><th>Semester</th><th className="num">Units</th><th className="num">Passed</th><th className="num">GPA</th></tr></thead>
                  <tbody>
                    {data.semesters.map((s) => (
                      <tr key={s.semester.id}><td>{s.semester.name}</td><td className="num">{s.units_taken}</td><td className="num">{s.units_passed}</td><td className="num strong">{fixed(s.gpa)}</td></tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Card>
            <Card title="Registration history" padded={false}>
              {data.registrations.length === 0 ? <EmptyState icon="register" title="No course registrations" /> : (
                <table className="table">
                  <thead><tr><th>Semester</th><th className="num">Courses</th><th className="num">Units</th></tr></thead>
                  <tbody>
                    {data.registrations.map((r) => (
                      <tr key={r.semester.id}><td>{r.semester.name}</td><td className="num">{r.courses}</td><td className="num">{r.units}</td></tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Card>
          </div>
          <Card title="Academic status history">
            {data.status_history.length === 0 ? <p className="muted">No status changes. The student has been active since admission.</p> : (
              <ul className="timeline">
                {data.status_history.map((c) => (
                  <li key={c.id}>
                    <div className="timeline-title">
                      <Badge tone={STATUS_TONE[c.from_status]}>{c.from_label}</Badge> → <Badge tone={STATUS_TONE[c.to_status]}>{c.to_label}</Badge>
                      <span className="muted small">effective {formatDate(c.effective_date)}</span>
                    </div>
                    <div className="timeline-note">{c.reason}</div>
                    <div className="muted small">{c.changed_by_name} · {formatDateTime(c.created_at)}</div>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      )}
    </TabData>
  )
}

export function CoursesTab({ id }) {
  return (
    <TabData url={`/students/${id}/courses/`}>
      {(data) => data.semesters.length === 0 ? <EmptyState icon="book" title="No course registrations" /> : (
        <div className="stack-lg">
          {data.semesters.map((s) => (
            <Card key={s.semester.id} padded={false}
                  title={<>{s.semester.name} {s.semester.id === data.current_semester && <Badge tone="green">Current</Badge>}</>}
                  action={<span className="muted small">{s.courses.length} courses · {s.units} units</span>}>
              <table className="table">
                <thead><tr><th>Code</th><th>Title</th><th className="num">Units</th><th>Lecturer</th><th>Result</th></tr></thead>
                <tbody>
                  {s.courses.map((c) => (
                    <tr key={c.offering}>
                      <td className="cell-title">{c.code} {c.is_carryover && <Badge tone="red">Carry-over</Badge>}</td>
                      <td>{c.title}</td>
                      <td className="num">{c.units}</td>
                      <td className="small">{c.lecturer || 'TBA'}</td>
                      <td>{c.grade ? <Badge tone={GRADE_TONE[c.grade]}>{c.grade}</Badge> : <span className="muted small">{c.result_status.replaceAll('_', ' ')}</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          ))}
        </div>
      )}
    </TabData>
  )
}

export function AttendanceTab({ id }) {
  return (
    <TabData url={`/students/${id}/attendance/`}>
      {(data) => (
        <div className="stack-lg">
          <div className="stats-grid">
            <Stat icon="check" label="Overall attendance (this semester)" value={formatPercent(data.overall_percent)}
                  tone={data.overall_percent != null && data.overall_percent < data.minimum_percent ? 'red' : 'green'} />
            <Stat icon="alert" label={`Courses below ${data.minimum_percent}%`} value={data.courses.filter((c) => c.at_risk).length} tone="amber" />
          </div>
          {data.courses.length === 0 ? <EmptyState icon="calendar" title="No courses this semester" /> : (
            <Card padded={false}>
              <table className="table">
                <thead><tr><th>Course</th><th className="num">Held</th><th className="num">Present</th><th className="num">Late</th><th className="num">Excused</th><th className="num">Absent</th><th>Attendance</th><th>Last class</th></tr></thead>
                <tbody>
                  {data.courses.map((c) => (
                    <tr key={c.offering}>
                      <td><div className="cell-title">{c.course_code}</div><div className="muted small">{c.course_title}</div></td>
                      <td className="num">{c.held}</td>
                      <td className="num">{c.present}</td>
                      <td className="num">{c.late}</td>
                      <td className="num">{c.excused}</td>
                      <td className="num">{c.absent}</td>
                      <td><PercentBar value={c.percent} minimum={data.minimum_percent} /></td>
                      <td>{c.history[0] ? <Badge tone={ATTENDANCE_TONE[c.history[0].status]}>{c.history[0].status_label}</Badge> : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          )}
        </div>
      )}
    </TabData>
  )
}

export function ResultsTab({ id }) {
  return (
    <TabData url={`/students/${id}/results/`}>
      {(data) => data.semesters.length === 0 ? <EmptyState icon="award" title="No published results yet" /> : (
        <div className="stack-lg">
          {data.semesters.map((s) => (
            <Card key={s.semester.id} title={s.semester.name} padded={false}
                  action={<span className="muted small">GPA <strong className="text-strong">{fixed(s.gpa)}</strong> · {s.units_passed}/{s.units_taken} units passed</span>}>
              <table className="table">
                <thead><tr><th>Code</th><th>Title</th><th className="num">Units</th><th className="num">CA</th><th className="num">Exam</th><th className="num">Total</th><th>Grade</th><th className="num">GP</th></tr></thead>
                <tbody>
                  {s.courses.map((c) => (
                    <tr key={c.code}>
                      <td className="cell-title">{c.code} {c.is_carryover && <Badge tone="red">Carry-over</Badge>}</td>
                      <td>{c.title}</td>
                      <td className="num">{c.units}</td>
                      <td className="num">{score(c.ca_score)}</td>
                      <td className="num">{score(c.exam_score)}</td>
                      <td className="num strong">{score(c.total_score)}</td>
                      <td><Badge tone={GRADE_TONE[c.grade]}>{c.grade}</Badge></td>
                      <td className="num">{c.grade_points}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          ))}
          <p className="muted small">CGPA {fixed(data.cgpa)} · {data.standing}{data.degree_class ? ` · ${data.degree_class}` : ''}</p>
        </div>
      )}
    </TabData>
  )
}

export function FeesTab({ id }) {
  return (
    <TabData url={`/students/${id}/fees/`}>
      {(data) => (
        <div className="stack-lg">
          <div className="stats-grid">
            <Stat icon="receipt" label="Total charged" value={formatMoney(data.total_charged)} />
            <Stat icon="wallet" label="Total paid" value={formatMoney(data.total_paid)} tone="green" />
            <Stat icon="alert" label="Balance" value={formatMoney(Math.max(data.balance, 0))} tone={data.balance > 0 ? 'amber' : 'green'}
                  hint={data.overdue > 0 ? `${formatMoney(data.overdue)} overdue` : data.balance < 0 ? `${formatMoney(-data.balance)} in credit` : undefined} />
          </div>
          <Card title="Charges" padded={false} action={<Link to={`/portal/fees/students/${id}`} className="link">Full statement</Link>}>
            {data.charges.length === 0 ? <EmptyState icon="receipt" title="No charges" /> : (
              <table className="table">
                <thead><tr><th>Description</th><th>Semester</th><th>Due</th><th className="num">Amount</th><th className="num">Outstanding</th><th>Status</th></tr></thead>
                <tbody>
                  {data.charges.map((c) => (
                    <tr key={c.id}>
                      <td>{c.description}</td>
                      <td className="small">{c.semester_name || '—'}</td>
                      <td className="small">{formatDate(c.due_date)}</td>
                      <td className="num">{formatMoney(c.amount)}</td>
                      <td className="num">{formatMoney(c.amount_due)}</td>
                      <td><Badge tone={CHARGE_STATUS[c.status]?.tone}>{CHARGE_STATUS[c.status]?.label ?? c.status}</Badge></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
          <Card title="Payments" padded={false}>
            {data.payments.length === 0 ? <EmptyState icon="wallet" title="No payments" /> : (
              <table className="table">
                <thead><tr><th>Receipt</th><th>Date</th><th>Method</th><th className="num">Amount</th><th>Status</th></tr></thead>
                <tbody>
                  {data.payments.map((p) => (
                    <tr key={p.id}>
                      <td className="mono small">{p.receipt_number}</td>
                      <td className="small">{formatDate(p.paid_at)}</td>
                      <td>{p.method_label}</td>
                      <td className="num">{formatMoney(p.amount)}</td>
                      <td><Badge tone={p.status === 'completed' ? 'green' : 'red'}>{p.status}</Badge></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        </div>
      )}
    </TabData>
  )
}

const DOCUMENT_KINDS = [
  ['admission_letter', 'Admission letter'], ['olevel', 'O-Level result'], ['jamb_result', 'JAMB result slip'],
  ['birth_certificate', 'Birth certificate'], ['lga_certificate', 'Certificate of state of origin'], ['medical', 'Medical report'],
  ['transcript', 'Transcript'], ['letter', 'Official letter'], ['other', 'Other'],
]

function UploadDocument({ id, onDone }) {
  const input = useRef(null)
  const [kind, setKind] = useState('letter')
  const [title, setTitle] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const upload = async (file) => {
    if (!file) return
    setBusy(true)
    setError('')
    const body = new FormData()
    body.append('kind', kind)
    body.append('title', title)
    body.append('file', file)
    try {
      await api.post(`/students/${id}/documents/`, body)
      setTitle('')
      onDone()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
      input.current.value = ''
    }
  }
  return (
    <div className="stack">
      <div className="toolbar">
        <select value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Document type">
          {DOCUMENT_KINDS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <label className="search"><input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title (optional), e.g. Suspension letter" maxLength={120} aria-label="Title" /></label>
        <input ref={input} type="file" accept="application/pdf,image/jpeg,image/png" hidden onChange={(e) => upload(e.target.files[0])} />
        <button className="btn btn-primary" disabled={busy} onClick={() => input.current.click()}><Icon name="plus" size={16} /> {busy ? 'Uploading…' : 'Upload document'}</button>
      </div>
      <Alert>{error}</Alert>
      <p className="muted small">PDF, JPG or PNG up to 5 MB. Documents are visible only to the Registry and staff who can see this student.</p>
    </div>
  )
}

export function DocumentsTab({ id, canManage }) {
  const [error, setError] = useState('')
  const view = (url) => openFile(url).catch(async (e) => setError(await blobErrorMessage(e)))
  return (
    <TabData url={`/students/${id}/documents/`}>
      {(data, reload) => {
        const remove = async (doc) => {
          if (!window.confirm(`Remove ${doc.title || doc.kind_label}?`)) return
          try { await api.delete(`/students/documents/${doc.id}/`); reload() } catch (err) { setError(errorMessage(err)) }
        }
        return (
          <div className="stack-lg">
            <Alert>{error}</Alert>
            {canManage && <Card><UploadDocument id={id} onDone={reload} /></Card>}
            <Card title="Student documents" padded={false}>
              {data.documents.length === 0 ? <EmptyState icon="receipt" title="No documents on file" /> : (
                <ul className="list list-padded">
                  {data.documents.map((d) => (
                    <li key={d.id} className="document-row">
                      <div className="list-icon"><Icon name="receipt" /></div>
                      <div className="grow">
                        <div className="list-title">{d.title || d.kind_label} {d.title && <span className="muted small">· {d.kind_label}</span>}</div>
                        <div className="list-meta">
                          <button className="link-button link" onClick={() => view(`/students/documents/${d.id}/`)}>{d.original_filename}</button>
                          {' '}· {formatSize(d.size)} · added by {d.uploaded_by_name} on {formatDate(d.uploaded_at)}
                        </div>
                      </div>
                      {canManage && <button className="btn btn-danger-ghost btn-sm" onClick={() => remove(d)}>Remove</button>}
                    </li>
                  ))}
                </ul>
              )}
            </Card>
            {data.admission_documents.length > 0 && (
              <Card title="From the online admission application" padded={false}>
                <ul className="list list-padded">
                  {data.admission_documents.map((d) => (
                    <li key={d.id} className="document-row">
                      <div className="list-icon"><Icon name="cap" /></div>
                      <div className="grow">
                        <div className="list-title">{d.kind_label}</div>
                        <div className="list-meta">
                          <button className="link-button link" onClick={() => view(`/admissions/documents/${d.id}/file/`)}>{d.original_filename}</button>
                          {' '}· {d.status_label} · {formatDate(d.uploaded_at)}
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              </Card>
            )}
          </div>
        )
      }}
    </TabData>
  )
}

export function AccommodationTab() {
  return (
    <EmptyState icon="building" title="No accommodation records">
      Hostel allocations will appear here once the accommodation module is set up.
    </EmptyState>
  )
}

const ACTIVITY_ICON = { record: 'shield', student: 'user', login: 'lock' }

export function ActivityTab({ id }) {
  const [kind, setKind] = useState('')
  return (
    <TabData url={`/students/${id}/activity/`}>
      {(events) => {
        const shown = events.filter((e) => !kind || e.kind === kind)
        return (
          <Card
            title="Activity history"
            action={
              <select value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Show">
                <option value="">Everything</option>
                <option value="record">Changes to the record</option>
                <option value="student">The student's actions</option>
                <option value="login">Sign-ins</option>
              </select>
            }
          >
            {shown.length === 0 ? <p className="muted">Nothing recorded yet.</p> : (
              <ul className="activity">
                {shown.map((e, i) => (
                  <li key={i} className={`activity-${e.kind} ${e.action === 'login_failed' ? 'is-failed' : ''}`}>
                    <span className="activity-icon"><Icon name={ACTIVITY_ICON[e.kind]} size={14} /></span>
                    <div className="grow">
                      <div>{e.summary}</div>
                      <div className="muted small">{e.actor} · {formatDateTime(e.at)} · <span className="mono">{e.action}</span></div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        )
      }}
    </TabData>
  )
}

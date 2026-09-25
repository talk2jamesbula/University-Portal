import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import api, { errorMessage } from '../../api/client'
import Icon from '../../components/Icon'
import { Alert, Avatar, Badge, Card, EmptyState, Modal, PageHeader, Spinner } from '../../components/ui'
import { formatDateTime } from '../../utils/format'
import useApi from '../../utils/useApi'
import {
  APPROVE_LABEL, GRADES, RESULT_STAGES, RESULT_STATUS_TONE, formatScore, gradeFor,
} from './results'

/** Where the course's results are in the approval chain. */
function StageTracker({ status }) {
  const current = status === 'pending' ? 0 : RESULT_STAGES.findIndex(([s]) => s === status)
  return (
    <ol className="tracker" aria-label="Results approval progress">
      {RESULT_STAGES.map(([stage, label], i) => {
        const state = i < current || status === 'published' ? 'done' : i === current ? 'current' : 'todo'
        return (
          <li key={stage} className={`tracker-step is-${state}`}>
            <span className="tracker-dot">{state === 'done' ? <Icon name="check" size={14} strokeWidth={2.4} /> : i + 1}</span>
            <span className="tracker-label">{label}</span>
          </li>
        )
      })}
    </ol>
  )
}

/** Average, pass rate and grade spread, so reviewers can spot an odd sheet at a glance. */
function Summary({ rows }) {
  const totals = rows.map((r) => r.total).filter((t) => t != null)
  if (!totals.length) return null
  const average = totals.reduce((a, b) => a + b, 0) / totals.length
  const passed = totals.filter((t) => t >= 40).length
  const counts = Object.fromEntries(GRADES.map((g) => [g, 0]))
  totals.forEach((t) => { counts[gradeFor(t)] += 1 })
  return (
    <div className="stats-inline">
      <div><strong>{formatScore(average)}</strong><span>Average total</span></div>
      <div><strong>{Math.round((passed * 100) / totals.length)}%</strong><span>Pass rate</span></div>
      {GRADES.map((g) => <div key={g}><strong>{counts[g]}</strong><span>Grade {g}</span></div>)}
    </div>
  )
}

function ActionModal({ kind, status, onClose, onDone, offeringId }) {
  const [note, setNote] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const titles = { submit: 'Submit results to the HOD', approve: APPROVE_LABEL[status], return: 'Return to the lecturer' }

  const send = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const { data } = await api.post(`/academics/result-sheets/${offeringId}/${kind}/`, { note })
      onDone(data)
    } catch (err) {
      setError(errorMessage(err))
      setBusy(false)
    }
  }

  return (
    <Modal
      title={titles[kind]}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className={`btn ${kind === 'return' ? 'btn-danger' : 'btn-primary'}`} form="result-action" disabled={busy}>
            {busy ? 'Sending…' : titles[kind]}
          </button>
        </>
      }
    >
      <form id="result-action" className="form" onSubmit={send}>
        <Alert>{error}</Alert>
        <p className="muted">
          {kind === 'submit' && 'Once submitted, scores can no longer be changed unless a reviewer returns them to you.'}
          {kind === 'approve' && status === 'faculty_approved' && 'Students will see these results straight away and be notified by email.'}
          {kind === 'approve' && status !== 'faculty_approved' && 'The results move to the next approver.'}
          {kind === 'return' && 'The lecturer can correct the scores and submit them again.'}
        </p>
        <label className="field">
          <span>{kind === 'return' ? 'What needs changing?' : 'Note (optional)'}</span>
          <textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} required={kind === 'return'} />
        </label>
      </form>
    </Modal>
  )
}

const inRange = (value, max) => value === '' || (/^\d{1,2}(\.\d)?$/.test(value) && Number(value) <= max)

/** A course's result sheet: the lecturer enters scores; HOD, Dean and Exams Office approve and publish. */
export default function ResultSheet() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { data, error, setData } = useApi(`/academics/result-sheets/${id}/`)
  const [edits, setEdits] = useState({})
  const [saving, setSaving] = useState(false)
  const [notice, setNotice] = useState({ text: '', tone: 'success' })
  const [modal, setModal] = useState(null)

  if (error && !data) return <Alert>{error}</Alert>
  if (!data) return <Spinner />

  const { offering, status, actions, ca_max: caMax, exam_max: examMax } = data
  const canEdit = actions.includes('edit')
  const value = (row, field) => edits[row.id]?.[field] ?? (row[field] == null ? '' : formatScore(row[field]))
  const rows = data.rows.map((r) => {
    const ca = value(r, 'ca_score')
    const exam = value(r, 'exam_score')
    const total = ca !== '' && exam !== '' && inRange(ca, caMax) && inRange(exam, examMax) ? Number(ca) + Number(exam) : null
    return { ...r, ca, exam, total }
  })
  const dirty = Object.keys(edits).length
  const invalid = rows.some((r) => !inRange(r.ca, caMax) || !inRange(r.exam, examMax))
  const incomplete = rows.filter((r) => r.ca === '' || r.exam === '').length

  const edit = (row, field, text) => {
    const next = { ...edits, [row.id]: { ...edits[row.id], [field]: text.trim() } }
    const original = (f) => (row[f] == null ? '' : formatScore(row[f]))
    if (['ca_score', 'exam_score'].every((f) => (next[row.id][f] ?? original(f)) === original(f))) delete next[row.id]
    setEdits(next)
  }

  const save = async () => {
    setSaving(true)
    setNotice({ text: '' })
    const scores = Object.entries(edits).map(([enrollment, change]) => ({
      enrollment: Number(enrollment),
      ...Object.fromEntries(Object.entries(change).map(([k, v]) => [k, v === '' ? null : v])),
    }))
    try {
      const { data: sheet } = await api.patch(`/academics/result-sheets/${id}/`, { scores })
      setData(sheet)
      setEdits({})
      setNotice({ text: `Saved scores for ${scores.length} student${scores.length === 1 ? '' : 's'}.`, tone: 'success' })
      return true
    } catch (err) {
      setNotice({ text: errorMessage(err), tone: 'error' })
      return false
    } finally {
      setSaving(false)
    }
  }

  const openSubmit = async () => {
    if (dirty && !(await save())) return
    setModal('submit')
  }

  const done = (sheet) => {
    setData(sheet)
    const text = {
      submit: 'Submitted. The HOD has been notified.',
      approve: sheet.status === 'published' ? 'Published. Students have been notified.' : 'Approved and passed to the next approver.',
      return: 'Returned to the lecturer.',
    }[modal]
    setModal(null)
    setNotice({ text, tone: 'success' })
  }

  return (
    <div className="stack-lg">
      <button onClick={() => navigate(-1)} className="back-link"><Icon name="arrowLeft" size={16} /> Back</button>
      <PageHeader
        title={`Results · ${offering.code}`}
        subtitle={`${offering.title} · ${offering.semester_name} · ${offering.lecturer_name || 'No lecturer assigned'}`}
        actions={
          <>
            {canEdit && dirty > 0 && (
              <button className="btn btn-ghost" onClick={save} disabled={saving || invalid}>{saving ? 'Saving…' : `Save ${dirty} change${dirty === 1 ? '' : 's'}`}</button>
            )}
            {actions.includes('submit') && (
              <button className="btn btn-primary" onClick={openSubmit} disabled={saving || invalid || incomplete > 0}
                      title={incomplete ? `${incomplete} student${incomplete === 1 ? ' has' : 's have'} missing scores` : undefined}>
                <Icon name="send" size={16} /> Submit to HOD
              </button>
            )}
            {actions.includes('return') && <button className="btn btn-danger-ghost" onClick={() => setModal('return')}>Return to lecturer</button>}
            {actions.includes('approve') && (
              <button className="btn btn-primary" onClick={() => setModal('approve')}><Icon name="check" size={16} /> {APPROVE_LABEL[status]}</button>
            )}
          </>
        }
      />
      <Alert tone={notice.tone} onClose={() => setNotice({ text: '' })}>{notice.text}</Alert>
      {status && <Card><StageTracker status={status} /></Card>}
      {canEdit && (
        <div className="callout callout-info">
          <Icon name="alert" />
          <span>
            Enter the CA out of {caMax} and the examination out of {examMax}, then save.{' '}
            {incomplete > 0 ? `${incomplete} student${incomplete === 1 ? ' still needs' : 's still need'} both scores before you can submit.` : 'Every student has both scores: you can submit.'}
          </span>
        </div>
      )}
      <Summary rows={rows} />
      <Card title={`Class list (${rows.length})`} padded={false}>
        {rows.length === 0 ? <EmptyState icon="users" title="No students are registered for this course" /> : (
          <table className="table table-compact">
            <thead>
              <tr>
                <th>#</th><th>Student</th><th>Matric no.</th>
                <th className="num">CA /{caMax}</th><th className="num">Exam /{examMax}</th><th className="num">Total</th><th>Grade</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={r.id}>
                  <td className="muted">{i + 1}</td>
                  <td>
                    <div className="person">
                      <Avatar name={r.student_name} src={r.student_avatar_url} size={28} />
                      <span className="cell-title">{r.student_name} {r.is_carryover && <Badge tone="red">Carry-over</Badge>}</span>
                    </div>
                  </td>
                  <td className="mono">{r.matric_number}</td>
                  {canEdit ? (
                    <>
                      {[['ca_score', r.ca, caMax], ['exam_score', r.exam, examMax]].map(([field, v, max]) => (
                        <td key={field} className="num">
                          <input
                            className="score-input" inputMode="decimal" value={v} aria-label={`${field === 'ca_score' ? 'CA' : 'Exam'} score for ${r.student_name}`}
                            aria-invalid={!inRange(v, max)} onChange={(e) => edit(r, field, e.target.value)}
                          />
                        </td>
                      ))}
                    </>
                  ) : (
                    <><td className="num">{formatScore(r.ca)}</td><td className="num">{formatScore(r.exam)}</td></>
                  )}
                  <td className="num strong">{formatScore(r.total)}</td>
                  <td>{r.total != null ? <Badge tone={gradeFor(r.total) === 'F' ? 'red' : 'neutral'}>{gradeFor(r.total)}</Badge> : <span className="muted">—</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      {data.history.length > 0 && (
        <Card title="History">
          <ul className="timeline">
            {data.history.map((h) => (
              <li key={h.id}>
                <div className="timeline-title">
                  <Badge tone={h.action === 'return' ? 'red' : RESULT_STATUS_TONE[h.to_status]}>{h.action_label}</Badge>
                </div>
                {h.note && <div className="timeline-note">{h.note}</div>}
                <div className="muted small">{h.by_name || 'Someone'} · {formatDateTime(h.at)}</div>
              </li>
            ))}
          </ul>
        </Card>
      )}
      {canEdit && (
        <p className="muted small">
          Sat a computer-based test? <Link className="link" to={`/portal/teaching/${offering.id}/exam`}>Send the CBT scores here</Link> from the exam page.
        </p>
      )}
      {modal && <ActionModal kind={modal} status={status} offeringId={id} onClose={() => setModal(null)} onDone={done} />}
    </div>
  )
}

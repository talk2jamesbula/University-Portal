import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import api, { blobErrorMessage, downloadFile, errorMessage } from '../../api/client'
import Icon from '../../components/Icon'
import { Alert, Badge, Card, Modal, PageHeader, Spinner } from '../../components/ui'
import { formatDate, formatDateTime, formatMoney } from '../../utils/format'
import useApi from '../../utils/useApi'
import { DOCUMENT_STATUS_TONE, STATUS_TONE, formatSize } from './admissions'
import Timeline from './Timeline'
import openFile from './openFile'

const DECISION = {
  approve: { title: 'Approve application', button: 'Approve', done: 'approved', tone: 'btn-primary', noteLabel: 'Note (optional)' },
  waitlist: { title: 'Put on the waiting list', button: 'Waitlist', done: 'waitlisted', tone: 'btn-ghost', noteLabel: 'Reason (the applicant will see this)' },
  reject: { title: 'Reject application', button: 'Reject', done: 'rejected', tone: 'btn-danger-ghost', noteLabel: 'Reason (the applicant will see this)' },
}

function DecisionModal({ decision, app, onClose, onDone }) {
  const config = DECISION[decision]
  const [note, setNote] = useState('')
  const [programme, setProgramme] = useState(app.programme)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      const { data } = await api.post(`/admissions/applications/${app.id}/decide/`, { decision, note, ...(decision === 'approve' ? { programme } : {}) })
      onDone(data, `${app.applicant_name}: ${config.done}.`)
    } catch (err) {
      setError(errorMessage(err))
      setSaving(false)
    }
  }
  return (
    <Modal title={config.title} onClose={onClose}
           footer={<><button className="btn btn-ghost" onClick={onClose}>Cancel</button><button className={`btn ${config.tone}`} form="decision-form" disabled={saving}>{saving ? 'Saving…' : config.button}</button></>}>
      <form id="decision-form" className="form" onSubmit={submit}>
        <Alert>{error}</Alert>
        <p className="muted"><strong className="text-strong">{app.applicant_name}</strong> · {app.number} · aggregate {app.aggregate_score ?? '—'}</p>
        {decision === 'approve' && (
          <fieldset className="amount-options">
            <legend>Offer admission into</legend>
            {[[app.programme, app.programme_name, 'First choice'], [app.second_choice, app.second_choice_name, 'Second choice']].filter(([id]) => id).map(([id, name, label]) => (
              <label key={id} className={`amount-option ${programme === id ? 'active' : ''}`}>
                <input type="radio" name="programme" checked={programme === id} onChange={() => setProgramme(id)} />
                <span><strong>{name}</strong><span className="muted small">{label}</span></span>
              </label>
            ))}
          </fieldset>
        )}
        <label className="field">
          <span>{config.noteLabel}</span>
          <textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} required={decision !== 'approve'} />
        </label>
        {decision === 'approve' && <p className="muted small">Approving doesn't notify the applicant of an offer yet. Issue the admission letter next.</p>}
      </form>
    </Modal>
  )
}

function RejectDocumentModal({ document, onClose, onDone }) {
  const [note, setNote] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      const { data } = await api.post(`/admissions/documents/${document.id}/review/`, { verified: false, note })
      onDone(data, `${document.kind_label} rejected. The applicant has been asked for a new copy.`)
    } catch (err) {
      setError(errorMessage(err))
      setSaving(false)
    }
  }
  return (
    <Modal title={`Reject ${document.kind_label.toLowerCase()}`} onClose={onClose}
           footer={<><button className="btn btn-ghost" onClick={onClose}>Cancel</button><button className="btn btn-danger-ghost" form="reject-doc" disabled={saving}>Reject document</button></>}>
      <form id="reject-doc" className="form" onSubmit={submit}>
        <Alert>{error}</Alert>
        <label className="field">
          <span>What's wrong? The applicant will see this and can upload a replacement.</span>
          <textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} required placeholder="e.g. The scan is blurred; the grades can't be read." />
        </label>
      </form>
    </Modal>
  )
}

/** One application, for the Admissions Office: details, document verification, screening and decision. */
export default function ApplicationReview() {
  const { id } = useParams()
  const { data, loading, error, setData } = useApi(`/admissions/applications/${id}/`)
  const [notice, setNotice] = useState({ tone: 'success', text: '' })
  const [busy, setBusy] = useState('')
  const [deciding, setDeciding] = useState(null)
  const [rejectingDoc, setRejectingDoc] = useState(null)
  const [screening, setScreening] = useState(null)
  const [note, setNote] = useState('')

  if (loading && !data) return <Spinner />
  if (error && !data) return <Alert>{error}</Alert>

  const { application: app, actions } = data
  const can = (a) => actions.includes(a)
  const done = (payload, text) => {
    setData(payload)
    setNotice({ tone: 'success', text })
    setDeciding(null)
    setRejectingDoc(null)
  }
  const act = async (key, url, body, text) => {
    setBusy(key)
    try {
      const { data: payload } = await api.post(url, body)
      done(payload, text)
      return true
    } catch (err) {
      setNotice({ tone: 'error', text: errorMessage(err) })
      return false
    } finally {
      setBusy('')
    }
  }
  const base = `/admissions/applications/${app.id}/`
  const scoreForm = screening ?? { score: app.screening_score ?? '', remarks: app.screening_remarks ?? '' }
  const letter = () => downloadFile(`${base}letter/`, null, 'admission-letter.pdf').catch(async (e) => setNotice({ tone: 'error', text: await blobErrorMessage(e) }))
  const view = (doc) => openFile(`/admissions/documents/${doc.id}/file/`).catch(async (e) => setNotice({ tone: 'error', text: await blobErrorMessage(e) }))
  const payment = data.payments.find((p) => p.status === 'success')

  return (
    <div className="stack-lg">
      <Link to="/portal/manage/admissions" className="back-link"><Icon name="arrowLeft" size={16} /> Applications</Link>
      <PageHeader
        title={app.applicant_name}
        subtitle={`${app.number} · ${app.entry_mode_label} · ${app.submitted_at ? `submitted ${formatDateTime(app.submitted_at)}` : 'not submitted'}`}
        actions={<Badge tone={STATUS_TONE[app.status]}>{app.status_label}</Badge>}
      />
      <Alert tone={notice.tone} onClose={() => setNotice({ ...notice, text: '' })}>{notice.text}</Alert>

      <div className="grid-2-1">
        <div className="stack-lg">
          <Card title="Documents" padded={false}>
            <ul className="list list-padded">
              {data.documents.length === 0 && <li className="muted">No documents uploaded.</li>}
              {data.documents.map((d) => (
                <li key={d.id} className="document-row">
                  <div className="list-icon"><Icon name={d.kind === 'passport' ? 'user' : 'receipt'} /></div>
                  <div className="grow">
                    <div className="list-title">{d.kind_label} {!data.required_documents.includes(d.kind) && <span className="muted small">(optional)</span>}</div>
                    <div className="list-meta">
                      <button className="link-button link" onClick={() => view(d)}>{d.original_filename}</button> · {formatSize(d.size)} · uploaded {formatDate(d.uploaded_at)}
                    </div>
                    {d.review_note && <div className="small text-red">{d.review_note}</div>}
                    {d.reviewed_by_name && <div className="muted small">{d.status_label} by {d.reviewed_by_name}</div>}
                  </div>
                  <Badge tone={DOCUMENT_STATUS_TONE[d.status]}>{d.status_label}</Badge>
                  {can('review_documents') && d.status !== 'verified' && (
                    <div className="toolbar">
                      <button className="btn btn-primary btn-sm" disabled={Boolean(busy)}
                              onClick={() => act(`doc-${d.id}`, `/admissions/documents/${d.id}/review/`, { verified: true }, `${d.kind_label} verified.`)}>Verify</button>
                      {d.status !== 'rejected' && <button className="btn btn-danger-ghost btn-sm" onClick={() => setRejectingDoc(d)}>Reject</button>}
                    </div>
                  )}
                </li>
              ))}
            </ul>
            {data.required_documents.filter((k) => !data.documents.some((d) => d.kind === k)).length > 0 && (
              <p className="muted small table-note">Missing required documents: {data.required_documents.filter((k) => !data.documents.some((d) => d.kind === k)).join(', ')}</p>
            )}
          </Card>

          <Card title="Academic record">
            <dl className="facts facts-wide">
              {app.entry_mode === 'utme' ? (
                <>
                  <div><dt>JAMB reg. no.</dt><dd className="mono">{app.jamb_reg_number || '—'}</dd></div>
                  <div><dt>UTME score</dt><dd>{app.utme_score ?? '—'} {app.utme_score != null && app.utme_score < app.min_utme_score && <Badge tone="red">Below {app.min_utme_score}</Badge>}</dd></div>
                </>
              ) : (
                <>
                  <div><dt>Previous institution</dt><dd>{app.previous_institution || '—'}</dd></div>
                  <div><dt>Qualification</dt><dd>{app.previous_qualification || '—'}</dd></div>
                </>
              )}
            </dl>
            {data.olevel_problems.length > 0 && <div className="callout callout-danger"><Icon name="alert" /><span>{data.olevel_problems.join(' ')}</span></div>}
            <table className="table table-compact">
              <thead><tr><th>Exam</th><th>Year</th><th>Subject</th><th>Grade</th></tr></thead>
              <tbody>
                {app.olevel_results.map((r) => (
                  <tr key={r.subject}><td>{r.exam}</td><td>{r.year}</td><td>{r.subject}</td><td><Badge tone={['D7', 'E8', 'F9'].includes(r.grade) ? 'red' : 'green'}>{r.grade}</Badge></td></tr>
                ))}
              </tbody>
            </table>
          </Card>

          <Card title="Personal details">
            <dl className="facts facts-wide">
              <div><dt>Email</dt><dd>{app.email}</dd></div>
              <div><dt>Phone</dt><dd>{app.phone || app.applicant_phone}</dd></div>
              <div><dt>Gender</dt><dd className="capitalize">{app.gender || '—'}</dd></div>
              <div><dt>Date of birth</dt><dd>{app.date_of_birth ? formatDate(app.date_of_birth) : '—'}</dd></div>
              <div><dt>State / LGA</dt><dd>{[app.state_of_origin, app.lga].filter(Boolean).join(' · ') || '—'}</dd></div>
              <div><dt>Nationality</dt><dd>{app.nationality}</dd></div>
              <div><dt>NIN</dt><dd className="mono">{app.nin || '—'}</dd></div>
              <div><dt>Address</dt><dd>{app.address || '—'}</dd></div>
              <div><dt>Next of kin</dt><dd>{[app.next_of_kin_name, app.next_of_kin_relationship, app.next_of_kin_phone].filter(Boolean).join(' · ') || '—'}</dd></div>
            </dl>
          </Card>

          <Card title="History and audit trail">
            <Timeline events={data.timeline} />
            <form className="note-form" onSubmit={async (e) => { e.preventDefault(); if (await act('note', `${base}note/`, { note }, 'Note added.')) setNote('') }}>
              <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Add an internal note (not shown to the applicant)" maxLength={300} aria-label="Internal note" />
              <button className="btn btn-ghost btn-sm" disabled={!note.trim() || busy === 'note'}>Add note</button>
            </form>
          </Card>
        </div>

        <div className="stack-lg">
          <Card title="Decision">
            <div className="stack">
              <dl className="facts">
                <div><dt>First choice</dt><dd>{app.programme_name || '—'}</dd></div>
                <div><dt>Second choice</dt><dd>{app.second_choice_name || '—'}</dd></div>
                {app.admitted_programme_name && <div><dt>Offered</dt><dd><strong>{app.admitted_programme_name}</strong></dd></div>}
                {app.reviewer_name && <div><dt>Reviewer</dt><dd>{app.reviewer_name}</dd></div>}
                {app.decision_note && <div><dt>Decision note</dt><dd>{app.decision_note}</dd></div>}
                {app.decided_by_name && <div><dt>Decided</dt><dd>{app.decided_by_name} · {formatDate(app.decided_at)}</dd></div>}
                {app.letter_number && <div><dt>Letter</dt><dd className="mono">{app.letter_number}</dd></div>}
                {app.accepted_at && <div><dt>Accepted</dt><dd>{formatDateTime(app.accepted_at)}</dd></div>}
              </dl>
              {actions.length === 0 && app.status === 'draft' && <p className="muted small">The applicant hasn't submitted this application yet.</p>}
              {actions.length === 0 && app.status === 'rejected' && <p className="muted small">This application was rejected. No further action.</p>}
              {can('start_review') && (
                <button className="btn btn-primary" disabled={Boolean(busy)} onClick={() => act('review', `${base}start-review/`, {}, 'Review started. The applicant has been notified.')}>
                  Start review
                </button>
              )}
              {app.status === 'under_review' && !can('to_screening') && <p className="muted small">Verify all required documents to move this application to screening.</p>}
              {can('to_screening') && (
                <button className="btn btn-primary" disabled={Boolean(busy)} onClick={() => act('screen', `${base}to-screening/`, {}, 'Moved to screening. The applicant has been notified.')}>
                  Move to screening
                </button>
              )}
              {can('issue_letter') && (
                <button className="btn btn-primary" disabled={Boolean(busy)} onClick={() => act('letter', `${base}issue-letter/`, {}, 'Admission letter issued and the applicant notified.')}>
                  <Icon name="award" size={16} /> Issue admission letter
                </button>
              )}
              {can('download_letter') && <button className="btn btn-ghost" onClick={letter}><Icon name="download" size={16} /> Admission letter</button>}
              {(can('approve') || can('waitlist') || can('reject')) && (
                <div className="toolbar">
                  {can('approve') && <button className="btn btn-primary" onClick={() => setDeciding('approve')}>Approve</button>}
                  {can('waitlist') && <button className="btn btn-ghost" onClick={() => setDeciding('waitlist')}>Waitlist</button>}
                  {can('reject') && <button className="btn btn-danger-ghost" onClick={() => setDeciding('reject')}>Reject</button>}
                </div>
              )}
            </div>
          </Card>

          <Card title="Scores">
            <div className="score-grid">
              <div><span>UTME</span><strong>{app.utme_score ?? '—'}</strong><small>of 400</small></div>
              <div><span>Screening</span><strong>{app.screening_score ?? '—'}</strong><small>of 100</small></div>
              <div><span>Aggregate</span><strong>{app.aggregate_score ?? '—'}</strong><small>of 100</small></div>
            </div>
            <p className="muted small">Aggregate = UTME ÷ 8 + screening ÷ 2.{app.screened_by_name && ` Screening recorded by ${app.screened_by_name}.`}</p>
            {can('record_screening') && (
              <form className="form" onSubmit={async (e) => {
                e.preventDefault()
                if (await act('score', `${base}screening/`, scoreForm, 'Screening result saved.')) setScreening(null)
              }}>
                <div className="form-row">
                  <label className="field"><span>Screening score</span>
                    <input type="number" min="0" max="100" step="0.5" value={scoreForm.score} onChange={(e) => setScreening({ ...scoreForm, score: e.target.value })} required />
                  </label>
                </div>
                <label className="field"><span>Remarks</span>
                  <input value={scoreForm.remarks} onChange={(e) => setScreening({ ...scoreForm, remarks: e.target.value })} maxLength={300} />
                </label>
                <button className="btn btn-ghost align-start" disabled={busy === 'score'}>Save screening result</button>
              </form>
            )}
          </Card>

          <Card title="Application fee">
            {payment
              ? <p><Badge tone="green">Paid</Badge> {formatMoney(payment.amount)} · {formatDate(payment.paid_at)}<br /><span className="muted small mono">{payment.reference}</span></p>
              : <p className="muted">Not paid</p>}
          </Card>
        </div>
      </div>

      {deciding && <DecisionModal decision={deciding} app={app} onClose={() => setDeciding(null)} onDone={done} />}
      {rejectingDoc && <RejectDocumentModal document={rejectingDoc} onClose={() => setRejectingDoc(null)} onDone={done} />}
    </div>
  )
}

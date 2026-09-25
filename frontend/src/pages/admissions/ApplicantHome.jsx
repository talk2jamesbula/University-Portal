import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import api, { blobErrorMessage, downloadFile, errorMessage } from '../../api/client'
import { useAuth } from '../../auth/useAuth'
import Icon from '../../components/Icon'
import { Alert, Badge, Card, EmptyState, PageHeader, Spinner } from '../../components/ui'
import { formatDate, formatDateTime, formatMoney } from '../../utils/format'
import useApi from '../../utils/useApi'
import { JOURNEY, STATUS_LABEL, STATUS_TONE } from './admissions'
import Timeline from './Timeline'

/** Where the application is on its way from draft to accepted. */
function Tracker({ status }) {
  const offPath = status === 'rejected' || status === 'waitlisted'
  // Rejected and waitlisted applications stop after screening.
  const steps = offPath ? [...JOURNEY.slice(0, 4), status] : JOURNEY
  const current = steps.indexOf(status)
  return (
    <ol className="tracker" aria-label="Application progress">
      {steps.map((step, i) => {
        const state = i < current ? 'done' : i === current ? 'current' : 'todo'
        return (
          <li key={step} className={`tracker-step is-${state} ${offPath && i === current ? `is-${status}` : ''}`}>
            <span className="tracker-dot">{state === 'done' ? <Icon name="check" size={14} strokeWidth={2.4} /> : i + 1}</span>
            <span className="tracker-label">{STATUS_LABEL[step]}</span>
          </li>
        )
      })}
    </ol>
  )
}

function NextStep({ data, onChanged }) {
  const { application: app, cycle, checklist } = data
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')

  const download = async (url, name) => {
    setBusy(url)
    try {
      await downloadFile(url, null, name)
    } catch (err) {
      setError(await blobErrorMessage(err))
    } finally {
      setBusy('')
    }
  }
  const accept = async () => {
    if (!window.confirm(`Accept the offer of admission into ${app.admitted_programme_name}?`)) return
    setBusy('accept')
    try {
      await api.post('/admissions/me/accept/')
      onChanged()
    } catch (err) {
      setError(errorMessage(err))
      setBusy('')
    }
  }
  const rejectedDocs = data.documents.filter((d) => d.status === 'rejected')

  const content = {
    draft: (
      <>
        <h2>Complete your application</h2>
        <ul className="checklist">
          {checklist.map((c) => (
            <li key={c.key} className={c.done ? 'is-done' : ''}>
              <Icon name={c.done ? 'check' : 'clock'} size={16} />
              <span><strong>{c.label}</strong>{!c.done && <span className="muted small"> · {c.problems[0]}</span>}</span>
            </li>
          ))}
        </ul>
        <p className="muted small">Applications close on {formatDate(cycle?.closes_on)}.</p>
        <Link to="/portal/application" className="btn btn-primary">Continue application <Icon name="arrowRight" size={16} /></Link>
      </>
    ),
    submitted: (
      <>
        <h2>Application received</h2>
        <p className="muted">Submitted {formatDateTime(app.submitted_at)}. The Admissions Office will review your details and verify your documents. We'll email you at each step.</p>
      </>
    ),
    under_review: (
      <>
        <h2>Your application is being reviewed</h2>
        <p className="muted">The Admissions Office is verifying your documents.</p>
      </>
    ),
    screening: (
      <>
        <h2>You're at the screening stage</h2>
        <p className="muted">Your documents have been verified. Your screening result and UTME score decide the admission offer.</p>
      </>
    ),
    approved: (
      <>
        <h2>Your application has been approved</h2>
        <p className="muted">You have been approved for admission into <strong className="text-strong">{app.admitted_programme_name}</strong>. Your admission letter will be issued shortly.</p>
      </>
    ),
    waitlisted: (
      <>
        <h2>You're on the waiting list</h2>
        <p className="muted">{app.decision_note || 'We will contact you if a place becomes available.'}</p>
      </>
    ),
    rejected: (
      <>
        <h2>Your application was not successful</h2>
        <p className="muted">{app.decision_note}</p>
        <p className="muted small">You may apply again in a future admission exercise.</p>
      </>
    ),
    admitted: (
      <>
        <h2>Congratulations, you've been offered admission!</h2>
        <p className="muted">
          Provisional admission into <strong className="text-strong">{app.admitted_programme_name}</strong> for the {app.session} session.
          {cycle?.acceptance_deadline && <> Accept the offer by <strong className="text-strong">{formatDate(cycle.acceptance_deadline)}</strong>.</>}
        </p>
        <div className="toolbar">
          <button className="btn btn-primary" onClick={accept} disabled={Boolean(busy)}><Icon name="check" size={16} /> {busy === 'accept' ? 'Accepting…' : 'Accept offer'}</button>
          <button className="btn btn-ghost" onClick={() => download('/admissions/me/letter/', 'admission-letter.pdf')} disabled={Boolean(busy)}>
            <Icon name="download" size={16} /> Admission letter
          </button>
        </div>
      </>
    ),
    accepted: (
      <>
        <h2>Welcome to the University!</h2>
        <p className="muted">You accepted your offer of admission into <strong className="text-strong">{app.admitted_programme_name}</strong> on {formatDate(app.accepted_at)}. Bring the originals of your documents to registration.</p>
        <button className="btn btn-primary" onClick={() => download('/admissions/me/letter/', 'admission-letter.pdf')} disabled={Boolean(busy)}>
          <Icon name="download" size={16} /> Download admission letter
        </button>
      </>
    ),
  }[app.status]

  return (
    <Card className={`next-step next-step-${app.status}`}>
      <Alert>{error}</Alert>
      {rejectedDocs.length > 0 && (
        <div className="callout callout-danger">
          <Icon name="alert" />
          <span>Please replace: <strong>{rejectedDocs.map((d) => d.kind_label).join(', ')}</strong>. {rejectedDocs[0].review_note}</span>
          <Link to="/portal/application?step=documents" className="btn btn-primary btn-sm">Replace document</Link>
        </div>
      )}
      <div className="stack">{content}</div>
    </Card>
  )
}

/** The applicant's home page: where the application stands and what to do next. */
export default function ApplicantHome() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const { data, loading, error, reload } = useApi('/admissions/me/')
  const [starting, setStarting] = useState(false)
  const [startError, setStartError] = useState('')

  if (loading && !data) return <Spinner />
  if (error) return <Alert>{error}</Alert>

  const { application: app, cycle } = data
  const start = async () => {
    setStarting(true)
    try {
      await api.post('/admissions/me/')
      navigate('/portal/application')
    } catch (err) {
      setStartError(errorMessage(err))
      setStarting(false)
    }
  }

  if (!app) {
    return (
      <div className="stack-lg">
        <PageHeader title={`Welcome, ${user.first_name}`} subtitle="Admissions Portal" />
        <Alert>{startError}</Alert>
        {cycle?.is_open ? (
          <Card>
            <div className="start-application">
              <span className="list-icon"><Icon name="cap" size={28} /></span>
              <div className="grow">
                <h2>Apply for the {cycle.session} session</h2>
                <p className="muted">
                  Applications close on <strong className="text-strong">{formatDate(cycle.closes_on)}</strong>. The application fee is{' '}
                  <strong className="text-strong">{formatMoney(cycle.application_fee)}</strong>. You'll need your JAMB registration number and UTME
                  score, your O-Level results, a passport photograph, and scans of your result slips and birth certificate.
                </p>
              </div>
              <button className="btn btn-primary" onClick={start} disabled={starting}>{starting ? 'Starting…' : 'Start application'}</button>
            </div>
          </Card>
        ) : (
          <EmptyState icon="calendar" title="Applications are closed">Watch the university website for the next admission exercise.</EmptyState>
        )}
      </div>
    )
  }

  const receipt = data.payments.find((p) => p.status === 'success')
  return (
    <div className="stack-lg">
      <PageHeader
        title={`Welcome, ${user.first_name}`}
        subtitle={`Application ${app.number} · ${app.session} session`}
        actions={<Badge tone={STATUS_TONE[app.status]}>{app.status_label}</Badge>}
      />
      <Card><Tracker status={app.status} /></Card>
      <div className="grid-2-1">
        <div className="stack-lg">
          <NextStep data={data} onChanged={reload} />
          <Card title="Application history"><Timeline events={data.timeline} /></Card>
        </div>
        <div className="stack-lg">
          <Card title="Your application" action={<Link to="/portal/application?step=review" className="link">View</Link>}>
            <dl className="facts">
              <div><dt>First choice</dt><dd>{app.programme_name || '—'}</dd></div>
              <div><dt>Second choice</dt><dd>{app.second_choice_name || '—'}</dd></div>
              <div><dt>Entry mode</dt><dd>{app.entry_mode_label}</dd></div>
              {app.utme_score != null && <div><dt>UTME score</dt><dd>{app.utme_score}</dd></div>}
              {app.letter_number && <div><dt>Admission letter</dt><dd className="mono">{app.letter_number}</dd></div>}
            </dl>
          </Card>
          <Card title="Application fee">
            {receipt ? (
              <div className="stack">
                <p><Badge tone="green">Paid</Badge> {formatMoney(receipt.amount)} on {formatDate(receipt.paid_at)}</p>
                <p className="muted small mono">{receipt.reference}</p>
                <button className="btn btn-ghost btn-sm" onClick={() => downloadFile('/admissions/me/receipt/', null, 'receipt.pdf')}>
                  <Icon name="receipt" size={14} /> Download receipt
                </button>
              </div>
            ) : (
              <div className="stack">
                <p className="muted">{formatMoney(cycle?.application_fee)} · not paid yet</p>
                {app.status === 'draft' && <Link to="/portal/application?step=payment" className="btn btn-primary btn-sm">Pay now</Link>}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}

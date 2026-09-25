import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import api, { blobErrorMessage, downloadFile, errorMessage, results } from '../../api/client'
import Icon from '../../components/Icon'
import { Alert, Badge, Card, PageHeader, Spinner } from '../../components/ui'
import { formatDate, formatDateTime, formatMoney } from '../../utils/format'
import useApi from '../../utils/useApi'
import {
  DOCUMENT_KINDS, DOCUMENT_STATUS_TONE, ENTRY_MODES, EXAMS, GRADES, STATES, STATUS_TONE, SUBJECTS, formatSize,
} from './admissions'
import openFile from './openFile'

const STEPS = [
  ['personal', 'Personal details'],
  ['programme', 'Programme choice'],
  ['academic', 'Academic record'],
  ['documents', 'Documents'],
  ['payment', 'Application fee'],
  ['review', 'Review and submit'],
]

const PERSONAL = ['middle_name', 'gender', 'date_of_birth', 'nationality', 'state_of_origin', 'lga', 'address', 'phone', 'nin',
  'next_of_kin_name', 'next_of_kin_relationship', 'next_of_kin_phone']
const PROGRAMME = ['entry_mode', 'programme', 'second_choice']
const ACADEMIC = ['jamb_reg_number', 'utme_score', 'previous_institution', 'previous_qualification', 'olevel_results']

const NULLABLE = ['date_of_birth', 'utme_score', 'programme', 'second_choice']

const pick = (app, keys) => Object.fromEntries(keys.map((k) => [k, app[k] ?? '']))

/** A step's form: local copy of its fields, saved with PATCH; shows field errors next to inputs. */
function useStepForm(app, keys, onSaved) {
  const [form, setForm] = useState(() => pick(app, keys))
  const [errors, setErrors] = useState({})
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const save = async (payload = form) => {
    setSaving(true)
    setErrors({})
    setError('')
    try {
      // Empty inputs are '' in the form; the API wants null for dates, numbers and choices.
      const body = Object.fromEntries(Object.entries(payload).map(([k, v]) => [k, v === '' && NULLABLE.includes(k) ? null : v]))
      const { data } = await api.patch('/admissions/me/', body)
      onSaved(data)
      return true
    } catch (err) {
      const fields = err.response?.data
      if (fields && typeof fields === 'object' && !fields.detail && !Array.isArray(fields)) setErrors(fields)
      else setError(errorMessage(err))
      return false
    } finally {
      setSaving(false)
    }
  }
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value })
  return { form, setForm, set, errors, error, saving, save }
}

function Field({ label, error, children, hint }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && !error && <small className="muted">{hint}</small>}
      {error && <small className="field-error">{[].concat(error).join(' ')}</small>}
    </label>
  )
}

function StepActions({ readOnly, saving, onBack }) {
  if (readOnly) return null
  return (
    <div className="step-actions">
      {onBack && <button type="button" className="btn btn-ghost" onClick={onBack}>Back</button>}
      <button className="btn btn-primary" disabled={saving}>{saving ? 'Saving…' : 'Save and continue'}</button>
    </div>
  )
}

function PersonalStep({ app, readOnly, onSaved, next }) {
  const { form, set, errors, error, saving, save } = useStepForm(app, PERSONAL, onSaved)
  const submit = async (e) => { e.preventDefault(); if (await save()) next() }
  return (
    <form className="form" onSubmit={submit}>
      <Alert>{error}</Alert>
      <fieldset disabled={readOnly} className="form">
        <div className="form-row">
          <Field label="First name"><input value={app.applicant_name.split(' ')[0]} disabled /></Field>
          <Field label="Middle name" error={errors.middle_name}><input value={form.middle_name} onChange={set('middle_name')} /></Field>
        </div>
        <p className="muted small">Your first name and surname are the ones on your account. Contact Admissions if they are wrong.</p>
        <div className="form-row">
          <Field label="Gender" error={errors.gender}>
            <select value={form.gender} onChange={set('gender')} required>
              <option value="">Select…</option><option value="female">Female</option><option value="male">Male</option>
            </select>
          </Field>
          <Field label="Date of birth" error={errors.date_of_birth}><input type="date" value={form.date_of_birth} onChange={set('date_of_birth')} required /></Field>
        </div>
        <div className="form-row">
          <Field label="Nationality" error={errors.nationality}><input value={form.nationality} onChange={set('nationality')} required /></Field>
          <Field label="State of origin" error={errors.state_of_origin}>
            <select value={form.state_of_origin} onChange={set('state_of_origin')} required>
              <option value="">Select…</option>
              {STATES.map((s) => <option key={s}>{s}</option>)}
            </select>
          </Field>
          <Field label="Local government area" error={errors.lga}><input value={form.lga} onChange={set('lga')} required /></Field>
        </div>
        <Field label="Home address" error={errors.address}><textarea rows={2} value={form.address} onChange={set('address')} required /></Field>
        <div className="form-row">
          <Field label="Phone number" error={errors.phone}><input type="tel" value={form.phone} onChange={set('phone')} required /></Field>
          <Field label="NIN (optional)" error={errors.nin} hint="National Identification Number, 11 digits">
            <input inputMode="numeric" maxLength={11} value={form.nin} onChange={set('nin')} />
          </Field>
        </div>
        <h3 className="form-heading">Next of kin</h3>
        <div className="form-row">
          <Field label="Full name" error={errors.next_of_kin_name}><input value={form.next_of_kin_name} onChange={set('next_of_kin_name')} required /></Field>
          <Field label="Relationship" error={errors.next_of_kin_relationship}>
            <input value={form.next_of_kin_relationship} onChange={set('next_of_kin_relationship')} placeholder="e.g. Mother" />
          </Field>
          <Field label="Phone number" error={errors.next_of_kin_phone}><input type="tel" value={form.next_of_kin_phone} onChange={set('next_of_kin_phone')} required /></Field>
        </div>
      </fieldset>
      <StepActions readOnly={readOnly} saving={saving} />
    </form>
  )
}

function ProgrammeStep({ app, readOnly, onSaved, next, back }) {
  const { form, set, setForm, errors, error, saving, save } = useStepForm(app, PROGRAMME, onSaved)
  const { data } = useApi('/academics/programmes/', { is_active: true })
  const programmes = results(data)
  const byFaculty = programmes.reduce((groups, p) => ({ ...groups, [p.faculty_name]: [...(groups[p.faculty_name] || []), p] }), {})
  const submit = async (e) => {
    e.preventDefault()
    if (await save()) next()
  }
  const options = (exclude) => Object.entries(byFaculty).map(([faculty, list]) => (
    <optgroup key={faculty} label={faculty}>
      {list.filter((p) => String(p.id) !== String(exclude)).map((p) => <option key={p.id} value={p.id}>{p.title} ({p.duration_years} years)</option>)}
    </optgroup>
  ))
  const chosen = programmes.find((p) => String(p.id) === String(form.programme))
  return (
    <form className="form" onSubmit={submit}>
      <Alert>{error}</Alert>
      <fieldset disabled={readOnly} className="form">
        <fieldset className="amount-options">
          <legend>Mode of entry</legend>
          {ENTRY_MODES.map(([value, label]) => (
            <label key={value} className={`amount-option ${form.entry_mode === value ? 'active' : ''}`}>
              <input type="radio" name="entry_mode" checked={form.entry_mode === value} onChange={() => setForm({ ...form, entry_mode: value })} />
              <span><strong>{label}</strong></span>
            </label>
          ))}
        </fieldset>
        <Field label="First choice" error={errors.programme}>
          <select value={form.programme} onChange={set('programme')} required>
            <option value="">Select a programme…</option>
            {options()}
          </select>
        </Field>
        {chosen && <p className="muted small">{chosen.department_name} · {chosen.faculty_name}{chosen.description ? ` · ${chosen.description}` : ''}</p>}
        <Field label="Second choice (optional)" error={errors.second_choice} hint="If your first choice is full, we may offer you your second choice.">
          <select value={form.second_choice} onChange={set('second_choice')}>
            <option value="">None</option>
            {options(form.programme)}
          </select>
        </Field>
      </fieldset>
      <StepActions readOnly={readOnly} saving={saving} onBack={back} />
    </form>
  )
}

const BLANK_RESULT = { exam: 'WAEC', year: new Date().getFullYear() - 1, subject: '', grade: '' }

function AcademicStep({ app, readOnly, onSaved, next, back, problems }) {
  const { form, set, setForm, errors, error, saving, save } = useStepForm(app, ACADEMIC, onSaved)
  const results = form.olevel_results.length ? form.olevel_results : [
    { ...BLANK_RESULT, subject: 'English Language' }, { ...BLANK_RESULT, subject: 'Mathematics' }, BLANK_RESULT, BLANK_RESULT, BLANK_RESULT,
  ]
  const setRow = (i, key, value) => setForm({ ...form, olevel_results: results.map((r, j) => (i === j ? { ...r, [key]: value } : r)) })
  const utme = app.entry_mode === 'utme'
  const submit = async (e) => {
    e.preventDefault()
    const rows = results.filter((r) => r.subject && r.grade).map((r) => ({ ...r, year: Number(r.year) }))
    const payload = { ...form, olevel_results: rows, utme_score: form.utme_score === '' ? null : Number(form.utme_score) }
    if (await save(payload)) next()
  }
  const rowErrors = Array.isArray(errors.olevel_results) ? errors.olevel_results : []
  return (
    <form className="form" onSubmit={submit}>
      <Alert>{error}</Alert>
      {problems.length > 0 && !readOnly && (
        <div className="callout"><Icon name="alert" /><span>{problems.join(' ')}</span></div>
      )}
      <fieldset disabled={readOnly} className="form">
        {utme ? (
          <div className="form-row">
            <Field label="JAMB registration number" error={errors.jamb_reg_number} hint="8 digits and 2 letters, e.g. 20261234AB">
              <input value={form.jamb_reg_number} onChange={set('jamb_reg_number')} required maxLength={10} style={{ textTransform: 'uppercase' }} />
            </Field>
            <Field label="UTME score" error={errors.utme_score} hint="Out of 400">
              <input type="number" min={0} max={400} value={form.utme_score} onChange={set('utme_score')} required />
            </Field>
          </div>
        ) : (
          <div className="form-row">
            <Field label="Previous institution" error={errors.previous_institution}><input value={form.previous_institution} onChange={set('previous_institution')} required /></Field>
            <Field label="Qualification and grade" error={errors.previous_qualification} hint="e.g. OND Computer Science, Upper Credit">
              <input value={form.previous_qualification} onChange={set('previous_qualification')} required />
            </Field>
          </div>
        )}
        <h3 className="form-heading">O-Level results</h3>
        <p className="muted small">At least five credit passes (A1–C6) including English Language and Mathematics, from at most two sittings.</p>
        {typeof errors.olevel_results === 'string' || (Array.isArray(errors.olevel_results) && typeof errors.olevel_results[0] === 'string')
          ? <Alert>{[].concat(errors.olevel_results).join(' ')}</Alert> : null}
        <datalist id="subjects">{SUBJECTS.map((s) => <option key={s} value={s} />)}</datalist>
        <div className="olevel">
          <div className="olevel-row olevel-head"><span>Exam</span><span>Year</span><span>Subject</span><span>Grade</span><span /></div>
          {results.map((r, i) => (
            <div className="olevel-row" key={i}>
              <select value={r.exam} onChange={(e) => setRow(i, 'exam', e.target.value)} aria-label="Exam">{EXAMS.map((x) => <option key={x}>{x}</option>)}</select>
              <input type="number" min={1980} max={new Date().getFullYear()} value={r.year} onChange={(e) => setRow(i, 'year', e.target.value)} aria-label="Year" />
              <input list="subjects" value={r.subject} onChange={(e) => setRow(i, 'subject', e.target.value)} placeholder="Subject" aria-label="Subject" />
              <select value={r.grade} onChange={(e) => setRow(i, 'grade', e.target.value)} aria-label="Grade">
                <option value="">—</option>{GRADES.map((g) => <option key={g}>{g}</option>)}
              </select>
              {!readOnly && (
                <button type="button" className="icon-btn" aria-label="Remove subject"
                        onClick={() => setForm({ ...form, olevel_results: results.filter((_, j) => j !== i) })}><Icon name="close" size={14} /></button>
              )}
              {rowErrors[i] && typeof rowErrors[i] === 'object' && <small className="field-error olevel-error">{Object.values(rowErrors[i]).flat().join(' ')}</small>}
            </div>
          ))}
        </div>
        {!readOnly && results.length < 12 && (
          <button type="button" className="btn btn-ghost btn-sm align-start" onClick={() => setForm({ ...form, olevel_results: [...results, BLANK_RESULT] })}>
            <Icon name="plus" size={14} /> Add subject
          </button>
        )}
      </fieldset>
      <StepActions readOnly={readOnly} saving={saving} onBack={back} />
    </form>
  )
}

function DocumentRow({ kind, label, help, document, canChange, required, onChanged }) {
  const input = useRef(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const upload = async (file) => {
    if (!file) return
    if (file.size > 5 * 1024 * 1024) return setError('The file is larger than 5 MB.')
    setBusy(true)
    setError('')
    const body = new FormData()
    body.append('kind', kind)
    body.append('file', file)
    try {
      await api.post('/admissions/me/documents/', body)
      onChanged()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
      input.current.value = ''
    }
  }
  const remove = async () => {
    setBusy(true)
    try {
      await api.delete(`/admissions/me/documents/${document.id}/`)
      onChanged()
    } catch (err) {
      setError(errorMessage(err))
      setBusy(false)
    }
  }
  return (
    <li className="document-row">
      <div className="list-icon"><Icon name={kind === 'passport' ? 'user' : 'receipt'} /></div>
      <div className="grow">
        <div className="list-title">{label} {required ? '' : <span className="muted small">(optional)</span>}</div>
        {document ? (
          <div className="list-meta">
            <button type="button" className="link-button link" onClick={() => openFile(`/admissions/documents/${document.id}/file/`).catch(async (e) => setError(await blobErrorMessage(e)))}>
              {document.original_filename}
            </button> · {formatSize(document.size)} · <Badge tone={DOCUMENT_STATUS_TONE[document.status]}>{document.status_label}</Badge>
            {document.review_note && <div className="text-red small">{document.review_note}</div>}
          </div>
        ) : <div className="list-meta">{help}</div>}
        {error && <div className="field-error">{error}</div>}
      </div>
      {canChange && (
        <div className="toolbar">
          <input ref={input} type="file" accept={kind === 'passport' ? 'image/jpeg,image/png' : 'application/pdf,image/jpeg,image/png'} hidden
                 onChange={(e) => upload(e.target.files[0])} />
          <button type="button" className={`btn btn-sm ${document ? 'btn-ghost' : 'btn-primary'}`} disabled={busy} onClick={() => input.current.click()}>
            <Icon name={document ? 'arrowRight' : 'plus'} size={14} /> {busy ? 'Uploading…' : document ? 'Replace' : 'Upload'}
          </button>
          {document && document.status !== 'rejected' && (
            <button type="button" className="btn btn-danger-ghost btn-sm" disabled={busy} onClick={remove}>Remove</button>
          )}
        </div>
      )}
    </li>
  )
}

function DocumentsStep({ data, onChanged, next, back }) {
  const draft = data.application.status === 'draft'
  const byKind = Object.fromEntries(data.documents.map((d) => [d.kind, d]))
  return (
    <div className="stack">
      <p className="muted">PDF, JPG or PNG, up to 5 MB each. Make sure every page is clear and readable; blurred or cropped scans will be rejected.</p>
      <ul className="list">
        {DOCUMENT_KINDS.map(([kind, label, help]) => (
          <DocumentRow key={kind} kind={kind} label={label} help={help} document={byKind[kind]}
                       required={data.required_documents.includes(kind)}
                       canChange={draft || (data.can_replace.includes(kind))} onChanged={onChanged} />
        ))}
      </ul>
      {draft && (
        <div className="step-actions">
          <button type="button" className="btn btn-ghost" onClick={back}>Back</button>
          <button type="button" className="btn btn-primary" onClick={next}>Continue</button>
        </div>
      )}
    </div>
  )
}

function PaymentStep({ data, next, back }) {
  const { application: app, cycle, gateway } = data
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const paid = data.payments.find((p) => p.status === 'success')
  const pay = async () => {
    setBusy(true)
    setError('')
    try {
      const { data: result } = await api.post('/admissions/me/pay/')
      window.location.assign(result.authorization_url)
    } catch (err) {
      setError(errorMessage(err))
      setBusy(false)
    }
  }
  return (
    <div className="stack">
      <Alert>{error}</Alert>
      <div className="fee-box">
        <div>
          <div className="muted small">Application fee · {app.session} admission</div>
          <div className="fee-amount">{formatMoney(cycle?.application_fee ?? paid?.amount)}</div>
        </div>
        {paid ? <Badge tone="green">Paid</Badge> : <Badge tone="amber">Not paid</Badge>}
      </div>
      {paid ? (
        <div className="stack">
          <p className="muted">Paid {formatDateTime(paid.paid_at)} · reference <span className="mono">{paid.reference}</span></p>
          <button className="btn btn-ghost align-start" onClick={() => downloadFile('/admissions/me/receipt/', null, 'receipt.pdf')}>
            <Icon name="receipt" size={16} /> Download receipt
          </button>
        </div>
      ) : app.status === 'draft' ? (
        <>
          {gateway === 'paystack' ? (
            <div className="gateway-note">
              <Icon name="lock" size={18} />
              <div><strong>Secured by Paystack</strong><p className="muted small">Pay by card, bank transfer or USSD. You'll come back here when you're done.</p></div>
            </div>
          ) : <Alert>Online payment through Paystack is not available right now. Please try again later.</Alert>}
          <button className="btn btn-primary align-start" onClick={pay} disabled={busy || gateway !== 'paystack'}>
            <Icon name="lock" size={16} /> {busy ? 'Redirecting to Paystack…' : `Pay ${formatMoney(cycle?.application_fee)} with Paystack`}
          </button>
          <p className="muted small">The application fee is not refundable.</p>
        </>
      ) : null}
      {data.payments.filter((p) => p.status === 'failed').length > 0 && (
        <details className="muted small">
          <summary>Unsuccessful attempts</summary>
          <ul>{data.payments.filter((p) => p.status === 'failed').map((p) => <li key={p.id}>{formatDateTime(p.created_at)} · {p.reference} · {p.gateway_response || 'Failed'}</li>)}</ul>
        </details>
      )}
      {app.status === 'draft' && (
        <div className="step-actions">
          <button type="button" className="btn btn-ghost" onClick={back}>Back</button>
          <button type="button" className="btn btn-primary" onClick={next}>Continue</button>
        </div>
      )}
    </div>
  )
}

function ReviewStep({ data, onSubmitted, goTo }) {
  const { application: app, checklist } = data
  const [agree, setAgree] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const incomplete = checklist.filter((c) => !c.done)
  const submit = async () => {
    setBusy(true)
    setError('')
    try {
      await api.post('/admissions/me/submit/')
      onSubmitted()
    } catch (err) {
      const problems = err.response?.data?.problems
      setError(problems ? problems.join(' ') : errorMessage(err))
      setBusy(false)
    }
  }
  const rows = [
    ['Name', `${app.applicant_name}${app.middle_name ? ` (${app.middle_name})` : ''}`],
    ['Email', app.email],
    ['Gender', app.gender && app.gender[0].toUpperCase() + app.gender.slice(1)],
    ['Date of birth', app.date_of_birth && formatDate(app.date_of_birth)],
    ['State / LGA', [app.state_of_origin, app.lga].filter(Boolean).join(' · ')],
    ['Phone', app.phone],
    ['Next of kin', [app.next_of_kin_name, app.next_of_kin_relationship, app.next_of_kin_phone].filter(Boolean).join(' · ')],
    ['Entry mode', app.entry_mode_label],
    ['First choice', app.programme_name],
    ['Second choice', app.second_choice_name],
    ...(app.entry_mode === 'utme'
      ? [['JAMB reg. no.', app.jamb_reg_number], ['UTME score', app.utme_score]]
      : [['Previous institution', app.previous_institution], ['Qualification', app.previous_qualification]]),
    ['O-Level', app.olevel_results.map((r) => `${r.subject} ${r.grade}`).join(', ')],
    ['Documents', `${data.documents.length} uploaded`],
    ['Application fee', app.fee_paid ? 'Paid' : 'Not paid'],
  ]
  return (
    <div className="stack">
      <dl className="facts facts-wide">
        {rows.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v || v === 0 ? v : <span className="muted">—</span>}</dd></div>)}
      </dl>
      {app.status === 'draft' && (
        <>
          {incomplete.length > 0 ? (
            <div className="callout callout-danger">
              <Icon name="alert" />
              <span>
                Before you submit:{' '}
                {incomplete.map((c, i) => (
                  <span key={c.key}>{i > 0 && ' · '}<button className="link-button link" onClick={() => goTo(c.key)}>{c.label}</button>: {c.problems.join(' ')}</span>
                ))}
              </span>
            </div>
          ) : (
            <label className="check-inline declaration">
              <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} />
              I confirm that the information and documents I have provided are true. I understand that any false information will lead to
              the withdrawal of admission, even after registration.
            </label>
          )}
          <Alert>{error}</Alert>
          <div className="step-actions">
            <button className="btn btn-primary" disabled={busy || incomplete.length > 0 || !agree} onClick={submit}>
              <Icon name="check" size={16} /> {busy ? 'Submitting…' : 'Submit application'}
            </button>
          </div>
          <p className="muted small">After you submit, you can't change your application.</p>
        </>
      )}
    </div>
  )
}

/** The application form: six steps, saved as you go. Read-only once submitted. */
export default function ApplicationForm() {
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const { data, loading, error, reload, setData } = useApi('/admissions/me/')
  const [notice, setNotice] = useState('')
  const verifying = useRef(false)

  // Back from Paystack: confirm the payment, then tidy the address bar.
  const reference = params.get('reference') || params.get('trxref')
  useEffect(() => {
    if (!reference || verifying.current) return
    verifying.current = true
    api.post('/admissions/me/pay/verify/', { reference })
      .then(({ data: p }) => setNotice(p.status === 'success' ? 'Payment received. Thank you!' : `Payment not completed: ${p.gateway_response || p.status}`))
      .catch((err) => setNotice(errorMessage(err)))
      .finally(() => { setParams({ step: 'payment' }, { replace: true }); reload() })
  }, [reference, reload, setParams])

  if (loading && !data) return <Spinner />
  if (error) return <Alert>{error}</Alert>
  if (!data.application) {
    return (
      <div className="stack-lg">
        <PageHeader title="My Application" />
        <Card><p className="muted">You haven't started an application. <Link to="/portal" className="link">Start one from your home page.</Link></p></Card>
      </div>
    )
  }

  const app = data.application
  const readOnly = app.status !== 'draft'
  const step = STEPS.some(([k]) => k === params.get('step')) ? params.get('step') : readOnly ? 'review' : 'personal'
  const index = STEPS.findIndex(([k]) => k === step)
  const goTo = (key) => { setParams({ step: key }); window.scrollTo(0, 0) }
  const next = () => goTo(STEPS[Math.min(index + 1, STEPS.length - 1)][0])
  const back = () => goTo(STEPS[Math.max(index - 1, 0)][0])
  const onSaved = (payload) => setData((d) => ({ ...d, ...payload }))
  const done = Object.fromEntries(data.checklist.map((c) => [c.key, c.done]))
  const problems = (key) => data.checklist.find((c) => c.key === key)?.problems ?? []
  const props = { app, readOnly, onSaved, next, back }

  return (
    <div className="stack-lg">
      <PageHeader
        title="My Application"
        subtitle={`${app.number} · ${app.session} session`}
        actions={<Badge tone={STATUS_TONE[app.status]}>{app.status_label}</Badge>}
      />
      <Alert tone="success" onClose={() => setNotice('')}>{notice}</Alert>
      {readOnly && (
        <div className="callout callout-info">
          <Icon name="lock" />
          <span>Your application was submitted on {formatDate(app.submitted_at)} and can no longer be changed.</span>
          <Link to="/portal" className="btn btn-primary btn-sm">Track status</Link>
        </div>
      )}
      <div className="wizard">
        <nav className="wizard-steps" aria-label="Application steps">
          {STEPS.map(([key, label], i) => (
            <button key={key} className={`wizard-step ${key === step ? 'active' : ''} ${done[key] ? 'is-done' : ''}`}
                    onClick={() => goTo(key)} aria-current={key === step ? 'step' : undefined}>
              <span className="wizard-dot">{done[key] ? <Icon name="check" size={13} strokeWidth={2.4} /> : i + 1}</span>
              {label}
            </button>
          ))}
        </nav>
        <Card title={STEPS[index][1]}>
          {step === 'personal' && <PersonalStep key={`p-${app.updated_at}`} {...props} />}
          {step === 'programme' && <ProgrammeStep key={`g-${app.updated_at}`} {...props} />}
          {step === 'academic' && <AcademicStep key={`a-${app.updated_at}-${app.entry_mode}`} {...props} problems={problems('academic')} />}
          {step === 'documents' && <DocumentsStep data={data} onChanged={reload} next={next} back={back} />}
          {step === 'payment' && <PaymentStep data={data} next={next} back={back} />}
          {step === 'review' && <ReviewStep data={data} goTo={goTo} onSubmitted={() => navigate('/portal')} />}
        </Card>
      </div>
    </div>
  )
}

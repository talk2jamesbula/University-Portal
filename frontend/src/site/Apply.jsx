import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import api, { errorMessage, tokens } from '../api/client'
import { useAuth } from '../auth/useAuth'
import Icon from '../components/Icon'
import { Alert } from '../components/ui'
import { formatDate, formatMoney } from '../utils/format'
import useApi from '../utils/useApi'
import { SITE } from './content'

/** Public sign-up for applicants: create an account, then continue to the application. */
export default function Apply() {
  const { user, reload } = useAuth()
  const navigate = useNavigate()
  const { data } = useApi('/admissions/cycle/')
  const [form, setForm] = useState({ first_name: '', last_name: '', email: '', phone: '', password: '', confirm: '' })
  const [errors, setErrors] = useState({})
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value })

  if (user) return <Navigate to="/portal" replace />

  const cycle = data?.cycle
  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setErrors({})
    if (form.password !== form.confirm) return setErrors({ confirm: 'The passwords do not match.' })
    setSubmitting(true)
    try {
      const { confirm: _confirm, ...payload } = form
      const { data: session } = await api.post('/admissions/register/', payload)
      tokens.set(session)
      await reload()
      navigate('/portal', { replace: true })
    } catch (err) {
      const fields = err.response?.data
      if (fields && typeof fields === 'object' && !fields.detail) {
        setErrors(Object.fromEntries(Object.entries(fields).map(([k, v]) => [k, [].concat(v).join(' ')])))
      } else {
        setError(errorMessage(err))
      }
      setSubmitting(false)
    }
  }

  const field = (key, label, props = {}) => (
    <label className="field">
      <span>{label}</span>
      <input value={form[key]} onChange={set(key)} aria-invalid={Boolean(errors[key])} required {...props} />
      {errors[key] && <small className="field-error">{errors[key]}</small>}
    </label>
  )

  return (
    <div className="login">
      <div className="login-hero">
        <Link to="/" className="brand brand-lg">
          <span className="brand-mark"><Icon name="cap" size={26} strokeWidth={2} /></span>
          <div>
            <div className="brand-name">{SITE.name}</div>
            <div className="brand-sub">Admissions Portal</div>
          </div>
        </Link>
        <div className="login-hero-copy">
          <h1>Apply for admission</h1>
          <p>
            {cycle
              ? `Applications for the ${cycle.session} session ${cycle.is_open ? `close on ${formatDate(cycle.closes_on)}` : 'are closed'}. The application fee is ${formatMoney(cycle.application_fee)}.`
              : 'Create an account to start your application.'}
          </p>
        </div>
        <ul className="login-features">
          <li><Icon name="user" /> Create your account</li>
          <li><Icon name="register" /> Fill in your details, programme choice and O-Level results</li>
          <li><Icon name="receipt" /> Upload your documents and pay the fee</li>
          <li><Icon name="award" /> Track your application and download your admission letter</li>
        </ul>
      </div>

      <div className="login-panel">
        <form className="login-form" onSubmit={submit}>
          <Link to="/admissions" className="back-link"><Icon name="arrowLeft" size={16} /> Admission requirements</Link>
          <h2>Create your applicant account</h2>
          <p className="muted">Use your own email address and phone number. We email you whenever your application moves forward.</p>
          {cycle && !cycle.is_open && <Alert tone="info">Applications are not open at the moment. You can still create an account.</Alert>}
          <Alert>{error}</Alert>
          <div className="form-row">
            {field('first_name', 'First name', { autoComplete: 'given-name', autoFocus: true })}
            {field('last_name', 'Surname', { autoComplete: 'family-name' })}
          </div>
          {field('email', 'Email address', { type: 'email', autoComplete: 'email' })}
          {field('phone', 'Phone number', { type: 'tel', autoComplete: 'tel', placeholder: '08031234567' })}
          {field('password', 'Password', { type: 'password', autoComplete: 'new-password', minLength: 8 })}
          {field('confirm', 'Confirm password', { type: 'password', autoComplete: 'new-password' })}
          <button className="btn btn-primary btn-block" disabled={submitting}>{submitting ? 'Creating account…' : 'Create account and apply'}</button>
          <p className="muted small">Already applied? <Link to="/login/applicant" className="link">Sign in to continue</Link></p>
        </form>
      </div>
    </div>
  )
}

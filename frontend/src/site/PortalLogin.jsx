import { useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { errorMessage } from '../api/client'
import { useAuth } from '../auth/useAuth'
import Icon from '../components/Icon'
import { Alert } from '../components/ui'
import { SITE } from './content'

const PORTALS = {
  student: {
    title: 'Student Portal',
    lead: 'Register courses, check results, pay fees and keep up with your department.',
    idLabel: 'Username or matric number',
    features: [['register', 'Course registration and course forms'], ['award', 'Results, GPA and CGPA'], ['wallet', 'Fees, receipts and invoices']],
    demo: [['Student', 'student']],
    other: ['staff', 'Staff? Sign in to the Staff Portal'],
  },
  applicant: {
    title: 'Admissions Portal',
    lead: 'Apply for undergraduate admission, pay your application fee and follow your application.',
    idLabel: 'Email address',
    features: [['register', 'Online application and document upload'], ['wallet', 'Pay the application fee online'], ['award', 'Track your status and download your admission letter']],
    demo: [['Applicant (draft)', 'applicant'], ['Applicant (offered)', 'applicant2']],
    other: ['student', 'Already a student? Sign in to the Student Portal'],
  },
  staff: {
    title: 'Staff Portal',
    lead: 'Lecturers, officers and administrators sign in here.',
    idLabel: 'Username',
    features: [['book', 'Courses, class lists and results'], ['users', 'Student records and registration'], ['wallet', 'Bursary and finance']],
    demo: [['Lecturer', 'lecturer'], ['HOD', 'hod'], ['Registrar', 'registrar'], ['Bursar', 'bursar'], ['Super Admin', 'admin']],
    other: ['student', 'Student? Sign in to the Student Portal'],
  },
}

/** Sign-in for the student or staff portal. Afterwards, return to the page that asked for it. */
export default function PortalLogin({ portal }) {
  const config = PORTALS[portal]
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [form, setForm] = useState({ username: '', password: '' })
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const next = location.state?.from || '/portal'

  if (user) return <Navigate to={next} replace />

  const submit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      // Matric numbers are typed with slashes; usernames are stored without them.
      await login(form.username.trim().replaceAll('/', '').toLowerCase(), form.password)
      navigate(next, { replace: true })
    } catch (err) {
      setError(err.response?.status === 401 ? 'Incorrect username or password.' : errorMessage(err))
      setSubmitting(false)
    }
  }

  return (
    <div className="login">
      <div className="login-hero">
        <Link to="/" className="brand brand-lg">
          <span className="brand-mark"><Icon name="cap" size={26} strokeWidth={2} /></span>
          <div>
            <div className="brand-name">{SITE.name}</div>
            <div className="brand-sub">{config.title}</div>
          </div>
        </Link>
        <div className="login-hero-copy">
          <h1>{config.title}</h1>
          <p>{config.lead}</p>
        </div>
        <ul className="login-features">
          {config.features.map(([icon, text]) => <li key={text}><Icon name={icon} /> {text}</li>)}
        </ul>
      </div>

      <div className="login-panel">
        <form className="login-form" onSubmit={submit}>
          <Link to="/" className="back-link"><Icon name="arrowLeft" size={16} /> Back to the website</Link>
          <h2>Sign in</h2>
          <p className="muted">
            {portal === 'applicant'
              ? 'Use the email address and password you applied with.'
              : `Use your university ${portal === 'student' ? 'matric number or username' : 'username'} and password.`}
          </p>
          <Alert>{error}</Alert>
          <label className="field">
            <span>{config.idLabel}</span>
            <input autoFocus autoComplete="username" value={form.username} required
                   onChange={(e) => setForm({ ...form, username: e.target.value })} />
          </label>
          <label className="field">
            <span>Password</span>
            <input type="password" autoComplete="current-password" value={form.password} required
                   onChange={(e) => setForm({ ...form, password: e.target.value })} />
          </label>
          <button className="btn btn-primary btn-block" disabled={submitting}>{submitting ? 'Signing in…' : 'Sign in'}</button>
          {portal === 'applicant' && <p className="muted small">New applicant? <Link to="/apply" className="link">Create an account</Link></p>}
          <Link to={`/login/${config.other[0]}`} className="link">{config.other[1]}</Link>

          {import.meta.env.DEV && (
            <div className="demo-accounts">
              <div className="demo-title">Demo accounts · password <code>Portal@2026</code></div>
              <div className="demo-list">
                {config.demo.map(([role, username]) => (
                  <button type="button" key={username} className="btn btn-ghost btn-sm"
                          onClick={() => setForm({ username, password: 'Portal@2026' })}>
                    {role}
                  </button>
                ))}
              </div>
            </div>
          )}
        </form>
      </div>
    </div>
  )
}

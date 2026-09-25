import { useState } from 'react'
import api, { errorMessage } from '../api/client'
import { useAuth } from '../auth/useAuth'
import { Alert, Card } from '../components/ui'
import { formatDate } from '../utils/format'

const EDITABLE = {
  contact: [['home_address', 'Home address']],
  next_of_kin: [
    ['next_of_kin_name', 'Full name'], ['next_of_kin_relationship', 'Relationship'],
    ['next_of_kin_phone', 'Phone number'], ['next_of_kin_address', 'Address'],
  ],
  emergency: [
    ['emergency_contact_name', 'Full name'], ['emergency_contact_relationship', 'Relationship'],
    ['emergency_contact_phone', 'Phone number'],
  ],
}

function Facts({ rows }) {
  return (
    <dl className="facts">
      {rows.map(([label, value]) => (
        <div key={label}><dt>{label}</dt><dd>{value || '—'}</dd></div>
      ))}
    </dl>
  )
}

/** The student's record: programme and personal details (read-only) and contacts (editable). */
export default function StudentRecord() {
  const { user, setUser } = useAuth()
  const profile = user.student_profile
  const initial = Object.fromEntries(Object.values(EDITABLE).flat().map(([key]) => [key, profile[key] || '']))
  const [form, setForm] = useState(initial)
  const [status, setStatus] = useState({ tone: 'success', text: '' })
  const [saving, setSaving] = useState(false)

  const save = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      const { data } = await api.patch('/auth/me/student-profile/', form)
      setUser({ ...user, student_profile: data })
      setStatus({ tone: 'success', text: 'Your contact details have been updated.' })
    } catch (err) {
      setStatus({ tone: 'error', text: errorMessage(err) })
    } finally {
      setSaving(false)
    }
  }

  const fields = (group) => EDITABLE[group].map(([key, label]) => (
    <label key={key} className="field">
      <span>{label}</span>
      <input value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} maxLength={255} />
    </label>
  ))

  return (
    <>
      <div className="grid-2">
        <Card title="Programme information">
          <Facts rows={[
            ['Programme', profile.programme_title], ['Department', profile.department_name],
            ['Faculty', profile.faculty_name], ['Level', `${profile.level} Level`],
            ['Mode of entry', profile.mode_of_entry_label], ['Entry session', profile.entry_session],
            ['Academic status', profile.status_label],
          ]} />
        </Card>
        <Card title="Personal information">
          <Facts rows={[
            ['Date of birth', formatDate(profile.date_of_birth)], ['Gender', profile.gender && profile.gender[0].toUpperCase() + profile.gender.slice(1)],
            ['Nationality', profile.nationality], ['State of origin', profile.state_of_origin], ['LGA', profile.lga],
          ]} />
          <p className="muted small">To correct these details, contact the Registry with supporting documents.</p>
        </Card>
      </div>
      <Card title="Contact, next of kin and emergency contact">
        <form className="form" onSubmit={save}>
          <Alert tone={status.tone} onClose={() => setStatus({ ...status, text: '' })}>{status.text}</Alert>
          <div className="form-grid">{fields('contact')}</div>
          <h3 className="form-section">Next of kin</h3>
          <div className="form-grid">{fields('next_of_kin')}</div>
          <h3 className="form-section">Emergency contact</h3>
          <div className="form-grid">{fields('emergency')}</div>
          <div><button className="btn btn-primary" disabled={saving}>{saving ? 'Saving…' : 'Save contact details'}</button></div>
        </form>
      </Card>
    </>
  )
}

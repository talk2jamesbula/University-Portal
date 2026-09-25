import { useRef, useState } from 'react'
import api, { errorMessage } from '../api/client'
import { useAuth } from '../auth/useAuth'
import Icon from '../components/Icon'
import { Alert, Avatar, Card, Modal, PageHeader } from '../components/ui'
import { isStudent, roleLabel } from '../auth/access'
import { formatDate } from '../utils/format'
import StudentRecord from './StudentRecord'

function ProfileForm() {
  const { user, setUser } = useAuth()
  const [form, setForm] = useState({ email: user.email, phone: user.phone, bio: user.bio })
  const [status, setStatus] = useState({ tone: 'success', text: '' })
  const [saving, setSaving] = useState(false)
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      const { data } = await api.patch('/auth/me/', form)
      setUser(data)
      setStatus({ tone: 'success', text: 'Profile updated.' })
    } catch (err) {
      setStatus({ tone: 'error', text: errorMessage(err) })
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="form" onSubmit={submit}>
      <Alert tone={status.tone} onClose={() => setStatus({ ...status, text: '' })}>{status.text}</Alert>
      <p className="muted small">Your name and university ID are maintained by the Registry. Contact them to correct them.</p>
      <div className="form-row">
        <label className="field"><span>Email</span><input type="email" value={form.email} onChange={set('email')} /></label>
        <label className="field"><span>Phone</span><input value={form.phone} onChange={set('phone')} /></label>
      </div>
      <label className="field"><span>About</span><textarea rows={3} value={form.bio} onChange={set('bio')} /></label>
      <div><button className="btn btn-primary" disabled={saving}>{saving ? 'Saving…' : 'Save changes'}</button></div>
    </form>
  )
}

function PasswordForm() {
  const [form, setForm] = useState({ current_password: '', new_password: '', confirm: '' })
  const [status, setStatus] = useState({ tone: 'success', text: '' })
  const [saving, setSaving] = useState(false)
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const submit = async (e) => {
    e.preventDefault()
    if (form.new_password !== form.confirm) {
      setStatus({ tone: 'error', text: 'New passwords do not match.' })
      return
    }
    setSaving(true)
    try {
      await api.post('/auth/change-password/', { current_password: form.current_password, new_password: form.new_password })
      setForm({ current_password: '', new_password: '', confirm: '' })
      setStatus({ tone: 'success', text: 'Password changed.' })
    } catch (err) {
      setStatus({ tone: 'error', text: errorMessage(err) })
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="form" onSubmit={submit}>
      <Alert tone={status.tone} onClose={() => setStatus({ ...status, text: '' })}>{status.text}</Alert>
      <label className="field"><span>Current password</span><input type="password" autoComplete="current-password" value={form.current_password} onChange={set('current_password')} required /></label>
      <label className="field"><span>New password</span><input type="password" autoComplete="new-password" value={form.new_password} onChange={set('new_password')} required /></label>
      <label className="field"><span>Confirm new password</span><input type="password" autoComplete="new-password" value={form.confirm} onChange={set('confirm')} required /></label>
      <div><button className="btn btn-primary" disabled={saving}>{saving ? 'Updating…' : 'Update password'}</button></div>
    </form>
  )
}

const MAX_PHOTO_BYTES = 5 * 1024 * 1024

/** Profile photo with change / remove controls. The server crops it to a square. */
function PhotoControl() {
  const { user, setUser } = useAuth()
  const input = useRef(null)
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const name = user.full_name || user.username

  const choose = (e) => {
    const f = e.target.files[0]
    e.target.value = ''
    setError('')
    if (!f) return
    if (!/^image\/(jpeg|png|webp)$/.test(f.type)) return setError('Choose a JPG, PNG or WebP image.')
    if (f.size > MAX_PHOTO_BYTES) return setError('Image is too large. The maximum size is 5 MB.')
    setFile(f)
    setPreview(URL.createObjectURL(f))
  }

  const close = () => {
    if (preview) URL.revokeObjectURL(preview)
    setFile(null)
    setPreview(null)
  }

  const save = async () => {
    setBusy(true)
    const data = new FormData()
    data.append('avatar', file)
    try {
      const res = await api.post('/auth/me/avatar/', data)
      setUser(res.data)
      close()
    } catch (err) {
      setError(errorMessage(err))
      close()
    } finally {
      setBusy(false)
    }
  }

  const remove = async () => {
    if (!window.confirm('Remove your profile photo?')) return
    setBusy(true)
    setError('')
    try {
      const res = await api.delete('/auth/me/avatar/')
      setUser(res.data)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="photo-control">
      <button className="photo-button" onClick={() => input.current.click()} disabled={busy} aria-label="Change profile photo">
        <Avatar name={name} src={user.avatar_url} size={88} />
        <span className="photo-overlay"><Icon name="camera" size={20} /></span>
      </button>
      <input ref={input} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={choose} />
      <div className="photo-actions">
        <button className="link" onClick={() => input.current.click()} disabled={busy}>
          {user.avatar_url ? 'Change photo' : 'Add photo'}
        </button>
        {user.avatar_url && <button className="link link-danger" onClick={remove} disabled={busy}>Remove</button>}
      </div>
      {error && <Alert onClose={() => setError('')}>{error}</Alert>}

      {file && (
        <Modal
          title="New profile photo"
          onClose={close}
          footer={
            <>
              <button className="btn btn-ghost" onClick={close} disabled={busy}>Cancel</button>
              <button className="btn btn-primary" onClick={save} disabled={busy}>{busy ? 'Saving…' : 'Save photo'}</button>
            </>
          }
        >
          <div className="photo-preview">
            {preview && <img src={preview} alt="Preview of your new profile photo" />}
            <p className="muted small">Your photo will be cropped to a square around the centre and shown as a circle across the portal.</p>
          </div>
        </Modal>
      )}
    </div>
  )
}

export default function Profile() {
  const { user } = useAuth()
  return (
    <div className="stack-lg">
      <PageHeader title="My Profile" />
      <div className="profile-banner">
        <PhotoControl />
        <div>
          <h2>{user.full_name || user.username}</h2>
          <p className="muted">
            {roleLabel(user)}
            {user.student_profile ? ` · ${user.student_profile.programme_title}` : user.department_name ? ` · ${user.department_name}` : ''}
          </p>
        </div>
        <dl className="profile-facts">
          {user.university_id && <div><dt>{isStudent(user) ? 'Matric no.' : 'Staff no.'}</dt><dd className="mono">{user.university_id}</dd></div>}
          <div><dt>Username</dt><dd>{user.username}</dd></div>
          <div><dt>Member since</dt><dd>{formatDate(user.date_joined)}</dd></div>
        </dl>
      </div>
      <div className="grid-2">
        <Card title="Account and contact"><ProfileForm /></Card>
        <Card title="Security"><PasswordForm /></Card>
      </div>
      {isStudent(user) && <StudentRecord />}
    </div>
  )
}

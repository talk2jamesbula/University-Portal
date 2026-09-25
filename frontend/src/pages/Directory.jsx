import { useRef, useState } from 'react'
import api, { errorMessage, results } from '../api/client'
import { can } from '../auth/access'
import { useAuth } from '../auth/useAuth'
import Icon from '../components/Icon'
import { Alert, Avatar, EmptyState, PageHeader, Spinner } from '../components/ui'
import useApi from '../utils/useApi'
import useDebounced from '../utils/useDebounced'

/** Lets the Registry set or remove a staff member's official photo (shown on the website). */
function PhotoButtons({ person, onChanged, onError }) {
  const input = useRef(null)
  const [busy, setBusy] = useState(false)
  const run = async (request) => {
    setBusy(true)
    try {
      await request()
      onChanged()
    } catch (err) {
      onError(`${person.full_name}: ${errorMessage(err)}`)
    } finally {
      setBusy(false)
    }
  }
  const upload = (e) => {
    const file = e.target.files[0]
    e.target.value = ''
    if (!file) return
    const data = new FormData()
    data.append('avatar', file)
    run(() => api.post(`/users/${person.id}/avatar/`, data))
  }
  return (
    <div className="person-photo-actions">
      <input ref={input} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={upload} />
      <button className="btn btn-ghost btn-sm" disabled={busy} onClick={() => input.current.click()}>
        <Icon name="camera" size={14} /> {busy ? 'Saving…' : person.avatar_url ? 'Change photo' : 'Add photo'}
      </button>
      {person.avatar_url && (
        <button className="btn btn-danger-ghost btn-sm" disabled={busy}
                onClick={() => window.confirm(`Remove ${person.full_name}'s photo?`) && run(() => api.delete(`/users/${person.id}/avatar/`))}>
          Remove
        </button>
      )}
    </div>
  )
}

export default function Directory() {
  const [search, setSearch] = useState('')
  const [department, setDepartment] = useState('')
  const [error, setError] = useState('')
  const { user } = useAuth()
  const managesPhotos = can(user, 'users.manage')
  const debouncedSearch = useDebounced(search)
  const { data: departments } = useApi('/academics/departments/')
  const { data, loading, error: loadError, reload } = useApi('/directory/', { search: debouncedSearch, department })
  const people = results(data)

  return (
    <div className="stack-lg">
      <PageHeader
        title="Staff Directory"
        subtitle={managesPhotos ? "Contact details for university staff. Photos you add here also appear on the website's About page for principal officers, deans and HODs." : "Contact details for university staff"}
      />
      <div className="toolbar">
        <label className="search">
          <Icon name="search" />
          <input placeholder="Search by name, email or department" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Search directory" />
        </label>
        <select value={department} onChange={(e) => setDepartment(e.target.value)} aria-label="Department">
          <option value="">All departments</option>
          {departments?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
      </div>
      {loadError && <Alert>{loadError}</Alert>}
      <Alert onClose={() => setError('')}>{error}</Alert>
      {loading && !data ? (
        <Spinner />
      ) : people.length === 0 ? (
        <EmptyState icon="users" title="No one found" />
      ) : (
        <div className="people-grid">
          {people.map((p) => (
            <article key={p.id} className="person-card">
              <Avatar name={p.full_name} src={p.avatar_url} size={48} />
              <div className="grow">
                <h3>{p.full_name}</h3>
                <div className="muted small">{p.designation || 'Staff'}{p.department_name ? ` · ${p.department_name}` : ''}</div>
                <div className="person-contact">
                  <a href={`mailto:${p.email}`}><Icon name="mail" size={14} /> {p.email}</a>
                  {p.phone && <span><Icon name="phone" size={14} /> {p.phone}</span>}
                </div>
                {managesPhotos && <PhotoButtons person={p} onChanged={reload} onError={setError} />}
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  )
}

import { useState } from 'react'
import api, { errorMessage } from '../../api/client'
import Icon from '../../components/Icon'
import { Alert, Badge, Card, EmptyState, Modal, Spinner } from '../../components/ui'
import useApi from '../../utils/useApi'

function VenueModal({ venue, onClose, onSaved }) {
  const [form, setForm] = useState({
    code: venue?.code ?? '',
    name: venue?.name ?? '',
    capacity: venue?.capacity ?? 100,
    location: venue?.location ?? '',
    is_cbt_centre: venue?.is_cbt_centre ?? false,
    is_active: venue?.is_active ?? true,
  })
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })

  const save = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      if (venue) await api.patch(`/exams/venues/${venue.id}/`, form)
      else await api.post('/exams/venues/', form)
      onSaved()
    } catch (err) {
      setError(errorMessage(err))
      setSaving(false)
    }
  }

  return (
    <Modal
      title={venue ? `Edit ${venue.name}` : 'Add a venue'}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" form="venue-form" disabled={saving}>{saving ? 'Saving…' : 'Save'}</button>
        </>
      }
    >
      <form id="venue-form" className="form" onSubmit={save}>
        <Alert>{error}</Alert>
        <div className="form-row">
          <label className="field field-narrow"><span>Code</span><input value={form.code} onChange={set('code')} maxLength={20} required /></label>
          <label className="field"><span>Name</span><input value={form.name} onChange={set('name')} maxLength={120} required /></label>
        </div>
        <div className="form-row">
          <label className="field field-narrow"><span>Seats</span><input type="number" min="1" value={form.capacity} onChange={set('capacity')} required /></label>
          <label className="field"><span>Location (optional)</span><input value={form.location} onChange={set('location')} maxLength={160} /></label>
        </div>
        <label className="check-inline"><input type="checkbox" checked={form.is_cbt_centre} onChange={set('is_cbt_centre')} /> CBT centre (has computers for online exams)</label>
        <label className="check-inline"><input type="checkbox" checked={form.is_active} onChange={set('is_active')} /> In use</label>
      </form>
    </Modal>
  )
}

/** Exam halls and CBT centres (Exams Office). */
export default function Venues() {
  const { data: venues, error, reload } = useApi('/exams/venues/')
  const [editing, setEditing] = useState(null)

  if (error && !venues) return <Alert>{error}</Alert>
  if (!venues) return <Spinner />

  return (
    <Card
      title={`Venues (${venues.length})`}
      padded={false}
      action={<button className="btn btn-primary btn-sm" onClick={() => setEditing('new')}><Icon name="plus" size={14} /> Add venue</button>}
    >
      {venues.length === 0 ? <EmptyState icon="building" title="No venues yet">Add the halls and CBT centres used for examinations.</EmptyState> : (
        <table className="table table-clickable">
          <thead><tr><th>Code</th><th>Name</th><th>Location</th><th className="num">Seats</th><th>Type</th><th /></tr></thead>
          <tbody>
            {venues.map((v) => (
              <tr key={v.id} onClick={() => setEditing(v)}>
                <td className="mono">{v.code}</td>
                <td className="cell-title">{v.name}</td>
                <td className="small">{v.location || <span className="muted">—</span>}</td>
                <td className="num">{v.capacity}</td>
                <td>{v.is_cbt_centre ? <Badge tone="purple">CBT centre</Badge> : <Badge>Hall</Badge>} {!v.is_active && <Badge tone="red">Not in use</Badge>}</td>
                <td className="align-right"><Icon name="chevronRight" size={16} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {editing && (
        <VenueModal venue={editing === 'new' ? null : editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); reload() }} />
      )}
    </Card>
  )
}

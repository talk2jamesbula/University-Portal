import { useRef, useState } from 'react'
import api, { errorMessage } from '../../../api/client'
import Icon from '../../../components/Icon'
import { Alert, Modal } from '../../../components/ui'
import { localToday as today } from '../../../utils/format'
import { ACCEPTED_FILES, MAX_PROOF_SIZE, NEEDS_BANK, PAYMENT_METHODS } from './constants'

const fileSize = (bytes) => (bytes > 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.ceil(bytes / 1024)} KB`)

export default function UploadProofModal({ balance, bank, onClose, onUploaded }) {
  const [form, setForm] = useState({
    amount: balance > 0 ? balance.toFixed(2) : '', method: 'bank_deposit', bank_name: bank?.bank_name || '',
    payment_date: today(), reference: '', note: '',
  })
  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const input = useRef(null)
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const pick = (f) => {
    setError('')
    if (!f) return
    if (!/\.(pdf|jpe?g|png)$/i.test(f.name)) return setError('Upload a PDF, JPG or PNG file.')
    if (f.size > MAX_PROOF_SIZE) return setError('File is too large. The maximum size is 5 MB.')
    setFile(f)
  }

  const submit = async (e) => {
    e.preventDefault()
    if (!file) return setError('Attach a photo or scan of your teller, transfer receipt or POS slip.')
    setSaving(true)
    setError('')
    const data = new FormData()
    Object.entries(form).forEach(([k, v]) => data.append(k, NEEDS_BANK.includes(form.method) || k !== 'bank_name' ? v : ''))
    data.append('file', file)
    try {
      const res = await api.post('/finance/payment-proofs/', data)
      onUploaded(res.data)
    } catch (err) {
      setError(errorMessage(err))
      setSaving(false)
    }
  }

  return (
    <Modal
      title="Upload proof of payment"
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" form="proof-form" disabled={saving}>
            <Icon name="check" size={16} /> {saving ? 'Uploading…' : 'Submit for review'}
          </button>
        </>
      }
    >
      <form id="proof-form" className="form" onSubmit={submit}>
        <p className="muted small">
          Paid at the bank, by transfer or at the Bursary? Submit the details and a copy of your receipt.
          Your balance is updated once the Bursary verifies it, usually within 2 working days.
        </p>
        <Alert>{error}</Alert>
        <div className="form-row">
          <label className="field"><span>Amount paid (₦)</span><input type="number" min="0.01" step="0.01" value={form.amount} onChange={set('amount')} required /></label>
          <label className="field"><span>Date paid</span><input type="date" max={today()} value={form.payment_date} onChange={set('payment_date')} required /></label>
        </div>
        <div className="form-row">
          <label className="field"><span>How did you pay?</span>
            <select value={form.method} onChange={set('method')}>{PAYMENT_METHODS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
          </label>
          {NEEDS_BANK.includes(form.method) && (
            <label className="field"><span>Bank</span><input value={form.bank_name} onChange={set('bank_name')} placeholder="e.g. First Bank" required maxLength={80} /></label>
          )}
        </div>
        <label className="field">
          <span>{form.method === 'bank_deposit' ? 'Teller number' : 'Transaction reference'}</span>
          <input value={form.reference} onChange={set('reference')} required maxLength={80} placeholder="As printed on your receipt" />
        </label>

        <div
          className={`dropzone ${dragging ? 'is-dragging' : ''} ${file ? 'has-file' : ''}`}
          onClick={() => input.current.click()}
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => { e.preventDefault(); setDragging(false); pick(e.dataTransfer.files[0]) }}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && input.current.click()}
        >
          <input ref={input} type="file" accept={ACCEPTED_FILES} hidden onChange={(e) => pick(e.target.files[0])} />
          <Icon name={file ? 'check' : 'receipt'} size={22} />
          {file ? (
            <div><strong>{file.name}</strong><div className="muted small">{fileSize(file.size)} · click to change</div></div>
          ) : (
            <div><strong>Attach your receipt</strong><div className="muted small">Drag a file here or click to browse · PDF, JPG or PNG up to 5 MB</div></div>
          )}
        </div>

        <label className="field"><span>Note to the Bursary (optional)</span><input value={form.note} onChange={set('note')} maxLength={300} /></label>
      </form>
    </Modal>
  )
}

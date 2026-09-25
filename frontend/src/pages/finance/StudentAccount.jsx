import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import api, { errorMessage, results } from '../../api/client'
import { can } from '../../auth/access'
import { useAuth } from '../../auth/useAuth'
import Icon from '../../components/Icon'
import { Alert, Avatar, Modal, Spinner } from '../../components/ui'
import { localToday as today } from '../../utils/format'
import useApi from '../../utils/useApi'
import AccountStatement, { AccountStats } from './AccountStatement'
import { ProofsTable } from './proofs'

const CATEGORIES = [
  ['housing', 'Housing'], ['lab', 'Lab / materials'], ['fine', 'Fine'], ['other', 'Other'],
]
const METHODS = [
  ['bank_transfer', 'Bank transfer'], ['cash', 'Cash'], ['card', 'Card (in person)'], ['scholarship', 'Scholarship / aid'],
]

function FormModal({ title, submitLabel, onClose, onSubmit, children }) {
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      await onSubmit(Object.fromEntries(new FormData(e.target)))
    } catch (err) {
      setError(errorMessage(err))
      setSaving(false)
    }
  }
  return (
    <Modal
      title={title}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" form="finance-form" disabled={saving}>{saving ? 'Saving…' : submitLabel}</button>
        </>
      }
    >
      <form id="finance-form" className="form" onSubmit={submit}>
        <Alert>{error}</Alert>
        {children}
      </form>
    </Modal>
  )
}

export default function StudentAccount() {
  const { id } = useParams()
  const { user } = useAuth()
  const manages = can(user, 'finance.manage')
  const navigate = useNavigate()
  const { data: account, loading, error, reload } = useApi('/finance/account/', { student: id })
  const { data: semesters } = useApi('/academics/semesters/')
  const { data: proofData, reload: reloadProofs } = useApi('/finance/payment-proofs/', { student: id })
  const proofs = results(proofData)
  const [modal, setModal] = useState(null)
  const [notice, setNotice] = useState({ tone: 'success', text: '' })

  const done = (text) => { setModal(null); setNotice({ tone: 'success', text }); reload() }
  const fail = (err) => setNotice({ tone: 'error', text: errorMessage(err) })

  if (loading && !account) return <Spinner />
  if (error) return <Alert>{error}</Alert>
  const { student } = account

  const voidPayment = async (p) => {
    const reason = window.prompt(`Void payment ${p.receipt_number}? Enter a reason:`)
    if (reason === null) return
    try {
      await api.post(`/finance/payments/${p.id}/void/`, { reason })
      done(`Payment ${p.receipt_number} voided.`)
    } catch (err) { fail(err) }
  }

  const deleteCharge = async (c) => {
    if (!window.confirm(`Remove the charge "${c.description}"?`)) return
    try {
      await api.delete(`/finance/charges/${c.id}/`)
      done('Charge removed.')
    } catch (err) { fail(err) }
  }

  return (
    <div className="stack-lg">
      <button onClick={() => navigate(-1)} className="back-link"><Icon name="arrowLeft" size={16} /> All accounts</button>

      <div className="page-header">
        <div className="person">
          <Avatar name={student.full_name} src={student.avatar_url} size={52} />
          <div>
            <h1>{student.full_name}</h1>
            <p className="muted">{student.university_id} · {student.email}</p>
          </div>
        </div>
        {manages && <div className="page-actions">
          <button className="btn btn-ghost" onClick={() => setModal('charge')}><Icon name="plus" size={16} /> Add charge</button>
          <button className="btn btn-primary" onClick={() => setModal('payment')}><Icon name="card" size={16} /> Record payment</button>
        </div>}
      </div>

      <Alert tone={notice.tone} onClose={() => setNotice({ ...notice, text: '' })}>{notice.text}</Alert>
      <AccountStats account={account} />
      <AccountStatement
        account={account}
        studentId={student.id}
        extraTab={{
          label: 'Payment proofs',
          count: proofs.length,
          highlight: proofs.some((p) => p.status === 'pending'),
          content: <ProofsTable proofs={proofs} staffView onChanged={() => { reloadProofs(); reload() }} />,
        }}
        chargeActions={(c) => manages && !c.is_automatic && (
          <button className="icon-btn" title="Remove charge" aria-label="Remove charge" onClick={() => deleteCharge(c)}><Icon name="close" size={16} /></button>
        )}
        paymentActions={(p) => manages && p.status === 'completed' && (
          <button className="btn btn-danger-ghost btn-sm" onClick={() => voidPayment(p)}>Void</button>
        )}
      />

      {modal === 'charge' && (
        <FormModal
          title={`Add charge · ${student.full_name}`}
          submitLabel="Add charge"
          onClose={() => setModal(null)}
          onSubmit={async (form) => {
            await api.post('/finance/charges/', { ...form, student: student.id, semester: form.semester || null })
            done('Charge added.')
          }}
        >
          <label className="field"><span>Description</span><input name="description" required maxLength={200} placeholder="e.g. Residence hall — Fall 2026" /></label>
          <div className="form-row">
            <label className="field"><span>Category</span>
              <select name="category">{CATEGORIES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
            </label>
            <label className="field"><span>Semester</span>
              <select name="semester" defaultValue={semesters?.find((t) => t.is_current)?.id ?? ''}>
                <option value="">No semester</option>
                {semesters?.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </label>
          </div>
          <div className="form-row">
            <label className="field"><span>Amount (₦)</span><input name="amount" type="number" min="0.01" step="0.01" required /></label>
            <label className="field"><span>Due date</span><input name="due_date" type="date" defaultValue={today()} required /></label>
          </div>
        </FormModal>
      )}

      {modal === 'payment' && (
        <FormModal
          title={`Record payment · ${student.full_name}`}
          submitLabel="Record payment"
          onClose={() => setModal(null)}
          onSubmit={async (form) => {
            await api.post('/finance/payments/', { ...form, student: student.id, paid_at: new Date(`${form.paid_at}T12:00:00`).toISOString() })
            done('Payment recorded.')
          }}
        >
          <div className="form-row">
            <label className="field"><span>Amount (₦)</span>
              <input name="amount" type="number" min="0.01" step="0.01" defaultValue={account.balance > 0 ? account.balance.toFixed(2) : ''} required />
            </label>
            <label className="field"><span>Method</span>
              <select name="method">{METHODS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
            </label>
          </div>
          <div className="form-row">
            <label className="field"><span>Payment date</span><input name="paid_at" type="date" defaultValue={today()} max={today()} required /></label>
            <label className="field"><span>Reference</span><input name="reference" maxLength={80} placeholder="Bank ref, cheque no., award…" /></label>
          </div>
          <label className="field"><span>Note (optional)</span><input name="note" maxLength={200} /></label>
        </FormModal>
      )}
    </div>
  )
}

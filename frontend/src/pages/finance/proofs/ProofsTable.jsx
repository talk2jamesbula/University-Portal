import { useState } from 'react'
import api, { errorMessage } from '../../../api/client'
import { Alert, Badge, Card, EmptyState } from '../../../components/ui'
import { formatDate, formatDateTime, formatMoney } from '../../../utils/format'
import { PROOF_STATUS } from './constants'
import ProofModal from './ProofModal'

/** Table of proofs. Students can withdraw pending ones; admins open them to review. */
/** Proofs of payment. `staffView` shows the bursary's view (with Review for finance managers). */
export default function ProofsTable({ proofs, staffView, onChanged, showStudent = false }) {
  const [open, setOpen] = useState(null)
  const [error, setError] = useState('')

  const withdraw = async (p) => {
    if (!window.confirm('Withdraw this proof of payment?')) return
    try {
      await api.delete(`/finance/payment-proofs/${p.id}/`)
      onChanged()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  if (!proofs.length) {
    return (
      <EmptyState icon="receipt" title={staffView ? 'No payment proofs here' : 'No proofs uploaded'}>
        {!staffView && 'If you pay at the bank or by transfer, upload your receipt so the Bursary can credit your account.'}
      </EmptyState>
    )
  }

  return (
    <>
      <Alert onClose={() => setError('')}>{error}</Alert>
      <Card padded={false}>
        <table className="table">
          <thead>
            <tr>
              <th>Submitted</th>
              {showStudent && <th>Student</th>}
              <th>Paid on</th><th>Method</th><th>Reference</th><th className="num">Amount</th><th>Status</th><th />
            </tr>
          </thead>
          <tbody>
            {proofs.map((p) => (
              <tr key={p.id}>
                <td>{formatDateTime(p.submitted_at)}</td>
                {showStudent && <td><div className="cell-title">{p.student_name}</div><div className="muted small">{p.student_university_id}</div></td>}
                <td>{formatDate(p.payment_date)}</td>
                <td>{p.method_label}{p.bank_name && <div className="muted small">{p.bank_name}</div>}</td>
                <td className="mono">{p.reference}</td>
                <td className="num">{formatMoney(p.amount)}</td>
                <td>
                  <Badge tone={PROOF_STATUS[p.status].tone}>{PROOF_STATUS[p.status].label}</Badge>
                  {p.status === 'rejected' && p.review_note && <div className="muted small proof-reason">{p.review_note}</div>}
                </td>
                <td>
                  <div className="row-actions">
                    <button className={`btn btn-sm ${staffView && p.status === 'pending' ? 'btn-primary' : 'btn-ghost'}`} onClick={() => setOpen(p)}>
                      {staffView && p.status === 'pending' ? 'Review' : 'View'}
                    </button>
                    {!staffView && p.status === 'pending' && (
                      <button className="btn btn-danger-ghost btn-sm" onClick={() => withdraw(p)}>Withdraw</button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      {open && (
        <ProofModal
          proof={open}
          staffView={staffView}
          onClose={() => setOpen(null)}
          onReviewed={() => { setOpen(null); onChanged() }}
        />
      )}
    </>
  )
}

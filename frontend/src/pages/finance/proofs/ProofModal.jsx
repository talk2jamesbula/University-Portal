import { useEffect, useState } from 'react'
import api, { blobErrorMessage, errorMessage } from '../../../api/client'
import { can } from '../../../auth/access'
import { useAuth } from '../../../auth/useAuth'
import Icon from '../../../components/Icon'
import { Alert, Badge, Modal, Spinner } from '../../../components/ui'
import { formatDate, formatDateTime, formatMoney } from '../../../utils/format'
import { PROOF_STATUS } from './constants'

function useProofFile(proof) {
  const [url, setUrl] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let href
    api.get(`/finance/payment-proofs/${proof.id}/file/`, { responseType: 'blob' })
      .then((res) => { href = URL.createObjectURL(res.data); setUrl(href) })
      .catch(async (err) => setError(await blobErrorMessage(err)))
    return () => href && URL.revokeObjectURL(href)
  }, [proof.id])
  return { url, error }
}

/** Shows the uploaded document. Admins can approve (optionally correcting the amount) or reject. */
export default function ProofModal({ proof, staffView, onClose, onReviewed }) {
  const { url, error: fileError } = useProofFile(proof)
  const [amount, setAmount] = useState(String(proof.amount))
  const [note, setNote] = useState('')
  const [rejecting, setRejecting] = useState(false)
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const { user } = useAuth()
  const canReview = staffView && can(user, 'finance.manage') && proof.status === 'pending'

  const review = async (action, body) => {
    setBusy(true)
    setError('')
    try {
      const { data } = await api.post(`/finance/payment-proofs/${proof.id}/${action}/`, body)
      onReviewed(data)
    } catch (err) {
      setError(errorMessage(err))
      setBusy(false)
    }
  }

  const footer = canReview ? (
    rejecting ? (
      <>
        <button className="btn btn-ghost" onClick={() => setRejecting(false)}>Back</button>
        <button className="btn btn-danger" disabled={busy || reason.trim().length < 5} onClick={() => review('reject', { reason })}>
          {busy ? 'Rejecting…' : 'Reject proof'}
        </button>
      </>
    ) : (
      <>
        <button className="btn btn-danger-ghost" onClick={() => setRejecting(true)}>Reject</button>
        <button className="btn btn-primary" disabled={busy} onClick={() => review('approve', { amount, note })}>
          <Icon name="check" size={16} /> {busy ? 'Approving…' : `Approve ${formatMoney(amount)}`}
        </button>
      </>
    )
  ) : (
    <>
      {url && <a className="btn btn-ghost" href={url} download={proof.original_filename}>Download file</a>}
      <button className="btn btn-primary" onClick={onClose}>Close</button>
    </>
  )

  return (
    <Modal title={staffView ? `Review proof · ${proof.student_name}` : 'Proof of payment'} onClose={onClose} footer={footer} wide>
      <div className="proof-review">
        <div className="proof-preview">
          {fileError ? <Alert>{fileError}</Alert> : !url ? <Spinner label="Loading file…" /> : proof.content_type === 'application/pdf'
            ? <iframe src={url} title={proof.original_filename} />
            : <img src={url} alt={`Proof of payment: ${proof.original_filename}`} />}
        </div>
        <div className="proof-side">
          <Alert>{error}</Alert>
          <Badge tone={PROOF_STATUS[proof.status].tone}>{PROOF_STATUS[proof.status].label}</Badge>
          <dl className="details details-tight">
            {staffView && <><dt>Student</dt><dd>{proof.student_name} <span className="muted">· {proof.student_university_id}</span></dd></>}
            <dt>Amount</dt><dd><strong>{formatMoney(proof.amount)}</strong></dd>
            <dt>Paid on</dt><dd>{formatDate(proof.payment_date)}</dd>
            <dt>Method</dt><dd>{proof.method_label}{proof.bank_name ? ` · ${proof.bank_name}` : ''}</dd>
            <dt>Reference</dt><dd className="mono">{proof.reference}</dd>
            <dt>Submitted</dt><dd>{formatDateTime(proof.submitted_at)}</dd>
            {proof.note && <><dt>Note</dt><dd>{proof.note}</dd></>}
            {proof.reviewed_at && <><dt>Reviewed</dt><dd>{formatDateTime(proof.reviewed_at)}{proof.reviewed_by_name ? ` by ${proof.reviewed_by_name}` : ''}</dd></>}
            {proof.review_note && <><dt>{proof.status === 'rejected' ? 'Reason' : 'Bursary note'}</dt><dd>{proof.review_note}</dd></>}
            {proof.receipt_number && <><dt>Receipt</dt><dd className="mono">{proof.receipt_number}</dd></>}
          </dl>

          {canReview && !rejecting && (
            <div className="form">
              <p className="muted small">Check the document matches the details and that the money has arrived in the university account.</p>
              <label className="field"><span>Amount to credit (₦)</span>
                <input type="number" min="0.01" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} />
              </label>
              <label className="field"><span>Note (optional)</span><input value={note} onChange={(e) => setNote(e.target.value)} maxLength={200} /></label>
            </div>
          )}
          {canReview && rejecting && (
            <label className="field">
              <span>Reason (sent to the student)</span>
              <textarea rows={4} value={reason} onChange={(e) => setReason(e.target.value)} autoFocus
                        placeholder="e.g. The teller is not legible, or no matching payment was found in the bank statement." />
            </label>
          )}
        </div>
      </div>
    </Modal>
  )
}

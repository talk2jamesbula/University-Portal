import { useState } from 'react'
import { blobErrorMessage, downloadFile } from '../../api/client'
import Icon from '../../components/Icon'
import { Alert, Badge, Modal } from '../../components/ui'
import { UNIVERSITY_NAME, formatDateTime, formatMoney } from '../../utils/format'

export function DownloadReceiptButton({ payment, className = 'btn btn-primary', label = 'Download PDF', onError }) {
  const [busy, setBusy] = useState(false)
  const download = async () => {
    setBusy(true)
    try {
      await downloadFile(`/finance/payments/${payment.id}/receipt/`, {}, `${payment.receipt_number}.pdf`)
    } catch (err) {
      onError?.(await blobErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }
  return (
    <button className={className} onClick={download} disabled={busy}>
      <Icon name="receipt" size={16} /> {busy ? 'Preparing…' : label}
    </button>
  )
}

export default function ReceiptModal({ payment, onClose, justPaid = false }) {
  const [error, setError] = useState('')
  return (
    <Modal
      title={justPaid ? 'Payment successful' : 'Payment receipt'}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={() => window.print()}><Icon name="printer" size={16} /> Print</button>
          <DownloadReceiptButton payment={payment} onError={setError} />
        </>
      }
    >
      <div className="receipt">
        <Alert onClose={() => setError('')}>{error}</Alert>
        {justPaid && (
          <Alert tone="success">Thank you. Your receipt has been generated and a copy has been emailed to you.</Alert>
        )}
        <div className="receipt-head">
          <div>
            <div className="receipt-org">{UNIVERSITY_NAME}</div>
            <div className="muted small">Office of Student Accounts</div>
          </div>
          {payment.status === 'void' ? <Badge tone="red">Void</Badge> : <Badge tone="green"><Icon name="check" size={12} /> Paid</Badge>}
        </div>
        <div className="receipt-amount">{formatMoney(payment.amount)}</div>
        <dl className="details">
          <dt>Receipt no.</dt><dd className="mono">{payment.receipt_number}</dd>
          <dt>Date</dt><dd>{formatDateTime(payment.paid_at)}</dd>
          <dt>Student</dt><dd>{payment.student_name} {payment.student_university_id && <span className="muted">· {payment.student_university_id}</span>}</dd>
          <dt>Method</dt><dd>{payment.method_label}{payment.card_last4 ? ` ending ${payment.card_last4}` : ''}</dd>
          {payment.reference && <><dt>Reference</dt><dd>{payment.reference}</dd></>}
          {payment.note && <><dt>Note</dt><dd>{payment.note}</dd></>}
        </dl>
      </div>
    </Modal>
  )
}

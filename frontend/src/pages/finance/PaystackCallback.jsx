import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import api, { errorMessage } from '../../api/client'
import Icon from '../../components/Icon'
import { Alert, Card, Spinner } from '../../components/ui'
import { formatDateTime, formatMoney } from '../../utils/format'
import ReceiptModal, { DownloadReceiptButton } from './Receipt'

/** Paystack redirects here after checkout with ?reference=...; confirm it with the API. */
export default function PaystackCallback() {
  const [params] = useSearchParams()
  const reference = params.get('reference') || params.get('trxref')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(reference ? '' : 'No payment reference was returned by Paystack.')
  const [showReceipt, setShowReceipt] = useState(false)
  const started = useRef(false)

  const check = async () => {
    setError('')
    setResult(null)
    try {
      const { data } = await api.post('/finance/paystack/verify/', { reference })
      setResult(data)
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  useEffect(() => {
    // Verify once, even under StrictMode's double effects.
    if (!reference || started.current) return
    started.current = true
    check()
  }, [reference]) // eslint-disable-line react-hooks/exhaustive-deps

  let body
  if (error) {
    body = (
      <>
        <Alert>{error}</Alert>
        {reference && <button className="btn btn-ghost" onClick={check}>Try again</button>}
      </>
    )
  } else if (!result) {
    body = <Spinner label="Confirming your payment with Paystack…" />
  } else if (result.payment) {
    const p = result.payment
    body = (
      <div className="callback-result">
        <div className="callback-icon tone-green"><Icon name="check" size={28} strokeWidth={2.4} /></div>
        <h2>Payment successful</h2>
        <p className="muted">{formatMoney(p.amount)} was paid on {formatDateTime(p.paid_at)}.</p>
        <p className="mono small">Receipt {p.receipt_number}</p>
        <p className="muted small">Your receipt has been generated and a copy has been emailed to you.</p>
        <div className="callback-actions">
          <button className="btn btn-ghost" onClick={() => setShowReceipt(true)}>View receipt</button>
          <DownloadReceiptButton payment={p} label="Download receipt (PDF)" onError={setError} />
          <Link to="/portal/fees" className="btn btn-ghost">Back to Fees & Payments</Link>
        </div>
      </div>
    )
  } else if (result.status === 'failed') {
    body = (
      <div className="callback-result">
        <div className="callback-icon tone-red"><Icon name="close" size={28} strokeWidth={2.4} /></div>
        <h2>Payment not completed</h2>
        <p className="muted">{result.message || 'The payment was declined or cancelled.'} You have not been charged.</p>
        <div className="callback-actions"><Link to="/portal/fees" className="btn btn-primary">Back to Fees & Payments</Link></div>
      </div>
    )
  } else {
    body = (
      <div className="callback-result">
        <div className="callback-icon tone-amber"><Icon name="clock" size={28} strokeWidth={2.2} /></div>
        <h2>Payment is still processing</h2>
        <p className="muted">Paystack hasn't confirmed this payment yet. It will appear on your account as soon as it does.</p>
        <div className="callback-actions">
          <button className="btn btn-ghost" onClick={check}>Check again</button>
          <Link to="/portal/fees" className="btn btn-primary">Back to Fees & Payments</Link>
        </div>
      </div>
    )
  }

  return (
    <div className="callback-page">
      <Card>{body}</Card>
      {showReceipt && result?.payment && <ReceiptModal payment={result.payment} onClose={() => setShowReceipt(false)} />}
    </div>
  )
}

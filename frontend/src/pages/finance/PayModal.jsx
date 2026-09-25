import { useState } from 'react'
import api, { errorMessage } from '../../api/client'
import Icon from '../../components/Icon'
import { Alert, Modal } from '../../components/ui'
import { formatMoney } from '../../utils/format'

/**
 * Payment dialog. Every online payment goes through Paystack: the student picks an amount and is
 * sent to Paystack's hosted checkout. Card and bank details never pass through the portal.
 */
export default function PayModal({ balance, onClose }) {
  const [amountMode, setAmountMode] = useState('full')
  const [custom, setCustom] = useState('')
  const [error, setError] = useState('')
  const [paying, setPaying] = useState(false)

  const amount = amountMode === 'full' ? balance : Number(custom)

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    if (!(amount > 0) || amount > balance) return setError(`Enter an amount between ₦0.01 and ${formatMoney(balance)}.`)
    setPaying(true)
    try {
      const { data } = await api.post('/finance/paystack/initialize/', { amount: amount.toFixed(2) })
      window.location.assign(data.authorization_url)
    } catch (err) {
      setError(errorMessage(err))
      setPaying(false)
    }
  }

  return (
    <Modal
      title="Make a payment"
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" form="pay-form" disabled={paying}>
            <Icon name="lock" size={15} />
            {paying ? 'Redirecting to Paystack…' : `Pay ${formatMoney(amount > 0 ? amount : 0)} with Paystack`}
          </button>
        </>
      }
    >
      <form id="pay-form" className="form" onSubmit={submit}>
        <Alert>{error}</Alert>
        <fieldset className="amount-options">
          <legend>Amount</legend>
          <label className={`amount-option ${amountMode === 'full' ? 'active' : ''}`}>
            <input type="radio" name="amount" checked={amountMode === 'full'} onChange={() => setAmountMode('full')} />
            <span><strong>Full balance</strong><span className="muted small">{formatMoney(balance)}</span></span>
          </label>
          <label className={`amount-option ${amountMode === 'custom' ? 'active' : ''}`}>
            <input type="radio" name="amount" checked={amountMode === 'custom'} onChange={() => setAmountMode('custom')} />
            <span><strong>Other amount</strong><span className="muted small">Pay part of your balance</span></span>
          </label>
        </fieldset>
        {amountMode === 'custom' && (
          <label className="field">
            <span>Amount (₦)</span>
            <input type="number" min="0.01" step="0.01" max={balance} value={custom} onChange={(e) => setCustom(e.target.value)} autoFocus required />
          </label>
        )}
        <div className="gateway-note">
          <Icon name="lock" size={18} />
          <div>
            <strong>Secured by Paystack</strong>
            <p className="muted small">
              You'll be taken to Paystack to pay by card, bank transfer or USSD, then brought back here with your receipt.
            </p>
          </div>
        </div>
      </form>
    </Modal>
  )
}

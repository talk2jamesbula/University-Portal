import Icon from '../../../components/Icon'

export default function BankAccountCard({ bank }) {
  if (!bank) return null
  return (
    <div className="bank-card">
      <Icon name="wallet" size={20} />
      <div className="grow">
        <div className="bank-card-title">Pay by bank deposit or transfer</div>
        <div className="bank-card-grid">
          <span className="muted">Bank</span><strong>{bank.bank_name}</strong>
          <span className="muted">Account name</span><strong>{bank.account_name}</strong>
          <span className="muted">Account number</span><strong className="mono bank-number">{bank.account_number}</strong>
        </div>
        <p className="muted small">After paying, upload your teller or transfer receipt so the Bursary can credit your account.</p>
      </div>
    </div>
  )
}

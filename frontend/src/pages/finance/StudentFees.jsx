import { useState } from 'react'
import { results } from '../../api/client'
import Icon from '../../components/Icon'
import { Alert, PageHeader, Spinner } from '../../components/ui'
import { formatDate, formatMoney } from '../../utils/format'
import useApi from '../../utils/useApi'
import AccountStatement, { AccountStats } from './AccountStatement'
import { BankAccountCard, ProofsTable, UploadProofModal } from './proofs'
import PayModal from './PayModal'

export default function StudentFees() {
  const { data: account, loading, error } = useApi('/finance/account/')
  const { data: config } = useApi('/finance/payment-config/')
  const paystack = config?.gateway === 'paystack'
  const { data: proofData, reload: reloadProofs } = useApi('/finance/payment-proofs/')
  const proofs = results(proofData)
  const pendingProofs = proofs.filter((p) => p.status === 'pending')
  const [uploading, setUploading] = useState(false)
  const [notice, setNotice] = useState('')
  const [paying, setPaying] = useState(false)

  if (loading && !account) return <Spinner />
  if (error) return <Alert>{error}</Alert>

  return (
    <div className="stack-lg">
      <PageHeader
        title="Fees & Payments"
        subtitle="Your tuition, fees and payment history"
        actions={
          <>
            <button className="btn btn-ghost" onClick={() => setUploading(true)}><Icon name="receipt" size={16} /> Upload proof of payment</button>
            {account.balance > 0 && paystack && (
              <button className="btn btn-primary" onClick={() => setPaying(true)}><Icon name="card" size={16} /> Pay online</button>
            )}
          </>
        }
      />

      <Alert tone="success" onClose={() => setNotice('')}>{notice}</Alert>

      {pendingProofs.length > 0 && (
        <div className="callout callout-info">
          <Icon name="clock" />
          <span>
            {pendingProofs.length === 1 ? 'Your proof of payment' : `${pendingProofs.length} proofs of payment`} for{' '}
            <strong>{formatMoney(pendingProofs.reduce((s, p) => s + p.amount, 0))}</strong> {pendingProofs.length === 1 ? 'is' : 'are'} awaiting
            verification by the Bursary. Your balance will update once approved.
          </span>
        </div>
      )}

      {account.overdue > 0 && (
        <Alert>
          {formatMoney(account.overdue)} of your balance is past due. Please pay as soon as possible to avoid a hold on your account.
        </Alert>
      )}

      <AccountStats account={account} />

      {account.balance > 0 && config && !paystack && (
        <div className="callout">
          <Icon name="alert" />
          <span>Online payment through Paystack is currently unavailable. Please pay at the bank or the Bursary, then upload your proof of payment.</span>
        </div>
      )}

      {account.balance > 0 && account.overdue === 0 && account.next_due_date && (
        <div className="callout">
          <Icon name="clock" />
          <span>Your next payment deadline is <strong>{formatDate(account.next_due_date)}</strong>. Payments are applied to your oldest charges first.</span>
        </div>
      )}

      {account.balance > 0 && <BankAccountCard bank={config?.bank_account} />}

      <AccountStatement
        account={account}
        extraTab={{
          label: 'Payment proofs',
          count: proofs.length,
          highlight: pendingProofs.length > 0,
          content: <ProofsTable proofs={proofs} onChanged={reloadProofs} />,
        }}
      />

      {uploading && (
        <UploadProofModal
          balance={account.balance}
          bank={config?.bank_account}
          onClose={() => setUploading(false)}
          onUploaded={() => {
            setUploading(false)
            setNotice('Proof of payment submitted. The Bursary will verify it and credit your account; you will be emailed a receipt once approved.')
            reloadProofs()
          }}
        />
      )}

      {paying && <PayModal balance={account.balance} onClose={() => setPaying(false)} />}
    </div>
  )
}

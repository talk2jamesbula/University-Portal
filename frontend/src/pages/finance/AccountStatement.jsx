import { useState } from 'react'
import { blobErrorMessage, downloadFile } from '../../api/client'
import Icon from '../../components/Icon'
import { Alert, Badge, Card, EmptyState, Stat } from '../../components/ui'
import { CHARGE_STATUS, formatDate, formatDateTime, formatMoney } from '../../utils/format'
import ReceiptModal, { DownloadReceiptButton } from './Receipt'

export function AccountStats({ account }) {
  const credit = account.balance < 0
  return (
    <div className="stats-grid">
      <Stat
        icon="wallet"
        label={credit ? 'Account credit' : 'Balance due'}
        value={formatMoney(Math.abs(account.balance))}
        tone={account.overdue > 0 ? 'red' : account.balance > 0 ? 'amber' : 'green'}
        hint={account.overdue > 0 ? `${formatMoney(account.overdue)} overdue` : account.next_due_date ? `Due ${formatDate(account.next_due_date)}` : account.balance <= 0 ? 'Nothing owed' : undefined}
      />
      <Stat icon="receipt" label="Total charged" value={formatMoney(account.total_charged)} />
      <Stat icon="check" label="Total paid" value={formatMoney(account.total_paid)} tone="green" />
    </div>
  )
}

function groupBySemester(charges) {
  const groups = new Map()
  for (const c of charges) {
    const key = c.semester_name || 'Other charges'
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key).push(c)
  }
  // Most recent semester first; payments are still applied oldest-first on the server.
  return [...groups.entries()].reverse()
}

/**
 * Statement + payment history for one student account.
 * `chargeActions` / `paymentActions` let the admin view add per-row buttons.
 */
export default function AccountStatement({ account, chargeActions, paymentActions, studentId, extraTab }) {
  const [tab, setTab] = useState('statement')
  const [receipt, setReceipt] = useState(null)
  const [downloading, setDownloading] = useState(null)
  const [error, setError] = useState('')
  const semesters = groupBySemester(account.charges)

  const downloadInvoice = async (semesterId, key) => {
    setDownloading(key)
    setError('')
    try {
      await downloadFile('/finance/invoice/', { semester: semesterId ?? 'none', ...(studentId ? { student: studentId } : {}) }, 'invoice.pdf')
    } catch (err) {
      setError(await blobErrorMessage(err))
    } finally {
      setDownloading(null)
    }
  }

  return (
    <>
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === 'statement'} className={`tab ${tab === 'statement' ? 'active' : ''}`} onClick={() => setTab('statement')}>
          Statement
        </button>
        <button role="tab" aria-selected={tab === 'payments'} className={`tab ${tab === 'payments' ? 'active' : ''}`} onClick={() => setTab('payments')}>
          Payment history <span className="tab-count">{account.payments.length}</span>
        </button>
        {extraTab && (
          <button role="tab" aria-selected={tab === 'extra'} className={`tab ${tab === 'extra' ? 'active' : ''}`} onClick={() => setTab('extra')}>
            {extraTab.label} {extraTab.count != null && <span className={`tab-count ${extraTab.highlight ? 'tab-count-alert' : ''}`}>{extraTab.count}</span>}
          </button>
        )}
      </div>

      <Alert onClose={() => setError('')}>{error}</Alert>

      {tab === 'statement' && (
        semesters.length === 0 ? (
          <EmptyState icon="receipt" title="No charges yet">Tuition and fees appear here when you register for courses.</EmptyState>
        ) : (
          semesters.map(([semester, charges]) => {
            const total = charges.reduce((s, c) => s + c.amount, 0)
            const due = charges.reduce((s, c) => s + c.amount_due, 0)
            return (
              <Card
                key={semester}
                title={semester}
                padded={false}
                action={
                  <div className="card-actions">
                    <span className="muted small">{due > 0.005 ? <>Outstanding <strong className="text-strong">{formatMoney(due)}</strong></> : <Badge tone="green">Settled</Badge>}</span>
                    <button className="btn btn-ghost btn-sm" disabled={downloading === semester} onClick={() => downloadInvoice(charges[0].semester, semester)}>
                      <Icon name="receipt" size={14} /> {downloading === semester ? 'Preparing…' : 'Invoice (PDF)'}
                    </button>
                  </div>
                }
              >
                <table className="table">
                  <thead>
                    <tr>
                      <th>Description</th><th>Due date</th><th className="num">Amount</th><th className="num">Paid</th><th>Status</th>
                      {chargeActions && <th />}
                    </tr>
                  </thead>
                  <tbody>
                    {charges.map((c) => (
                      <tr key={c.id}>
                        <td>
                          <div className="cell-title">{c.description}</div>
                          <div className="muted small">{c.category_label}</div>
                        </td>
                        <td>{formatDate(c.due_date)}</td>
                        <td className="num">{formatMoney(c.amount)}</td>
                        <td className="num">{formatMoney(c.amount_paid)}</td>
                        <td><Badge tone={CHARGE_STATUS[c.status].tone}>{CHARGE_STATUS[c.status].label}</Badge></td>
                        {chargeActions && <td className="align-right">{chargeActions(c)}</td>}
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr>
                      <td colSpan={2}>Semester total</td>
                      <td className="num">{formatMoney(total)}</td>
                      <td className="num">{formatMoney(total - due)}</td>
                      <td colSpan={chargeActions ? 2 : 1} />
                    </tr>
                  </tfoot>
                </table>
              </Card>
            )
          })
        )
      )}

      {tab === 'payments' && (
        account.payments.length === 0 ? (
          <EmptyState icon="card" title="No payments yet" />
        ) : (
          <Card padded={false}>
            <table className="table">
              <thead>
                <tr><th>Date</th><th>Receipt</th><th>Method</th><th className="num">Amount</th><th>Status</th><th /></tr>
              </thead>
              <tbody>
                {account.payments.map((p) => (
                  <tr key={p.id} className={p.status === 'void' ? 'is-void' : ''}>
                    <td>{formatDateTime(p.paid_at)}</td>
                    <td className="mono">{p.receipt_number}</td>
                    <td>{p.method_label}{p.card_last4 ? ` ···· ${p.card_last4}` : ''}</td>
                    <td className="num">{formatMoney(p.amount)}</td>
                    <td><Badge tone={p.status === 'void' ? 'red' : 'green'}>{p.status === 'void' ? 'Void' : 'Completed'}</Badge></td>
                    <td>
                      <div className="row-actions">
                        <button className="btn btn-ghost btn-sm" onClick={() => setReceipt(p)}>View</button>
                        <DownloadReceiptButton payment={p} className="btn btn-ghost btn-sm" label="PDF" onError={setError} />
                        {paymentActions?.(p)}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )
      )}

      {tab === 'extra' && extraTab?.content}

      {receipt && <ReceiptModal payment={receipt} onClose={() => setReceipt(null)} />}
    </>
  )
}

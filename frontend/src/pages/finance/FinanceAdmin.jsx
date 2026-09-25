import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { results } from '../../api/client'
import Icon from '../../components/Icon'
import { Alert, Avatar, Card, EmptyState, PageHeader, Spinner, Stat } from '../../components/ui'
import { formatMoney } from '../../utils/format'
import useApi from '../../utils/useApi'
import useDebounced from '../../utils/useDebounced'
import { ProofsTable } from './proofs'


export default function FinanceAdmin() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [balance, setBalance] = useState('outstanding')
  const [ordering, setOrdering] = useState('-balance')
  const [view, setView] = useState('accounts')
  const [proofStatus, setProofStatus] = useState('pending')
  const [proofSearch, setProofSearch] = useState('')
  const debouncedSearch = useDebounced(search)
  const debouncedProofSearch = useDebounced(proofSearch)
  const { data: summary, reload: reloadSummary } = useApi('/finance/summary/')
  const { data: proofData, loading: proofsLoading, reload: reloadProofs } = useApi(
    view === 'proofs' ? '/finance/payment-proofs/' : null,
    { status: proofStatus, search: debouncedProofSearch, ordering: proofStatus === 'pending' ? 'submitted_at' : '-submitted_at' },
  )
  const { data, loading, error } = useApi('/finance/accounts/', { search: debouncedSearch, balance, ordering })
  const rows = results(data)

  const sortHeader = (field, label) => {
    const active = ordering.replace('-', '') === field
    const next = active && ordering.startsWith('-') ? field : `-${field}`
    return (
      <th className="num">
        <button className="th-sort" onClick={() => setOrdering(next)}>
          {label}{active ? (ordering.startsWith('-') ? ' ↓' : ' ↑') : ''}
        </button>
      </th>
    )
  }

  return (
    <div className="stack-lg">
      <PageHeader title="Fees & Payments" subtitle="Student accounts and collections" />

      {summary && (
        <div className="stats-grid">
          <Stat icon="receipt" label="Total billed" value={formatMoney(summary.total_billed)} />
          <Stat icon="check" label="Collected" value={formatMoney(summary.total_collected)} tone="green"
                hint={summary.total_billed ? `${Math.round((summary.total_collected / summary.total_billed) * 100)}% of billed` : undefined} />
          <Stat icon="wallet" label="Outstanding" value={formatMoney(summary.outstanding)} tone="amber"
                hint={`${summary.students_with_balance} students with a balance`} />
          <Stat icon="trend" label="Collected today" value={formatMoney(summary.collected_today)} tone="purple" />
        </div>
      )}

      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={view === 'accounts'} className={`tab ${view === 'accounts' ? 'active' : ''}`} onClick={() => setView('accounts')}>
          Student accounts
        </button>
        <button role="tab" aria-selected={view === 'proofs'} className={`tab ${view === 'proofs' ? 'active' : ''}`} onClick={() => setView('proofs')}>
          Payment proofs {summary?.pending_proofs > 0 && <span className="tab-count tab-count-alert">{summary.pending_proofs}</span>}
        </button>
      </div>

      {view === 'proofs' && (
        <>
          <div className="toolbar">
            <label className="search">
              <Icon name="search" />
              <input placeholder="Search by student, ID, reference or bank" value={proofSearch} onChange={(e) => setProofSearch(e.target.value)} aria-label="Search proofs" />
            </label>
            <select value={proofStatus} onChange={(e) => setProofStatus(e.target.value)} aria-label="Status">
              <option value="pending">Awaiting review</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
              <option value="">All</option>
            </select>
          </div>
          {proofsLoading && !proofData ? <Spinner /> : (
            <ProofsTable proofs={results(proofData)} staffView showStudent onChanged={() => { reloadProofs(); reloadSummary() }} />
          )}
        </>
      )}

      {view === 'accounts' && (<>
      <div className="toolbar">
        <label className="search">
          <Icon name="search" />
          <input placeholder="Search students by name, ID or email" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Search students" />
        </label>
        <select value={balance} onChange={(e) => setBalance(e.target.value)} aria-label="Balance filter">
          <option value="outstanding">With a balance</option>
          <option value="clear">Paid up</option>
          <option value="">All students</option>
        </select>
      </div>

      {error && <Alert>{error}</Alert>}
      {loading && !data ? (
        <Spinner />
      ) : rows.length === 0 ? (
        <EmptyState icon="users" title="No student accounts match" />
      ) : (
        <Card padded={false}>
          <table className="table table-clickable">
            <thead>
              <tr>
                <th>Student</th>
                <th>ID</th>
                {sortHeader('total_charged', 'Charged')}
                {sortHeader('total_paid', 'Paid')}
                {sortHeader('balance', 'Balance')}
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} onClick={() => navigate(`/portal/fees/students/${r.id}`)}>
                  <td>
                    <div className="person">
                      <Avatar name={r.full_name} src={r.avatar_url} size={32} />
                      <div>
                        <div className="cell-title">{r.full_name}</div>
                        <div className="muted small">{r.email}</div>
                      </div>
                    </div>
                  </td>
                  <td className="mono">{r.university_id}</td>
                  <td className="num">{formatMoney(r.total_charged)}</td>
                  <td className="num">{formatMoney(r.total_paid)}</td>
                  <td className={`num strong ${r.balance > 0 ? 'text-amber' : r.balance < 0 ? 'text-green' : ''}`}>
                    {r.balance < 0 ? `${formatMoney(-r.balance)} CR` : formatMoney(r.balance)}
                  </td>
                  <td className="align-right"><Icon name="chevronRight" size={16} className="muted" /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
      </>)}
    </div>
  )
}

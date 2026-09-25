import { Badge } from '../../components/ui'
import { formatDateTime } from '../../utils/format'
import { STATUS_TONE } from './admissions'

/** An application's history, newest first. Internal notes are marked (officers only see them). */
export default function Timeline({ events }) {
  return (
    <ul className="timeline">
      {[...events].reverse().map((e) => (
        <li key={e.id} className={e.public ? '' : 'is-internal'}>
          <div className="timeline-title">
            {e.to_status ? <>Status: <Badge tone={STATUS_TONE[e.to_status]}>{e.to_status_label}</Badge></> : TIMELINE_ACTIONS[e.action] || e.action}
            {!e.public && <Badge>Internal</Badge>}
          </div>
          {e.note && <div className="timeline-note">{e.note}</div>}
          <div className="muted small">{e.actor_name} · {formatDateTime(e.created_at)}</div>
        </li>
      ))}
    </ul>
  )
}

const TIMELINE_ACTIONS = {
  created: 'Application started',
  fee_paid: 'Application fee paid',
  document_verified: 'Document verified',
  document_rejected: 'Document rejected',
  document_replaced: 'Document replaced',
  screening: 'Screening result recorded',
  note: 'Note',
  duplicate_payment: 'Duplicate payment received',
}

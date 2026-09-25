import { formatPercent } from './attendance'

/** Attendance percentage as a bar, with the minimum requirement marked. */
export default function PercentBar({ value, minimum }) {
  const tone = value == null ? '' : value < minimum ? 'tone-bg-red' : value < minimum + 10 ? 'tone-bg-amber' : 'tone-bg-green'
  return (
    <div className="pct" aria-label={value == null ? 'No sessions yet' : `${formatPercent(value)} attendance`}>
      <div className="pct-bar">
        <span className={tone} style={{ width: `${value ?? 0}%` }} />
        {minimum != null && <i style={{ left: `${minimum}%` }} title={`Minimum ${minimum}%`} />}
      </div>
      <strong>{formatPercent(value)}</strong>
    </div>
  )
}

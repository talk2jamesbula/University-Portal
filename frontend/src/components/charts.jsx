/**
 * Small, dependency-free charts for dashboards. Bars are HTML/CSS (crisp text at any size); the area and
 * donut charts are SVG. Colours come from the --chart-* tokens, so they follow the light/dark theme.
 * Every chart has a text summary for screen readers.
 */
import { useId, useState } from 'react'

const PALETTE = ['var(--chart-1)', 'var(--chart-2)', 'var(--chart-3)', 'var(--chart-4)', 'var(--chart-5)', 'var(--chart-6)']
const colorAt = (i) => PALETTE[i % PALETTE.length]

const plain = (v) => (typeof v === 'number' ? v.toLocaleString() : v)
const summary = (data, format) => data.map((d) => `${d.label}: ${format(d.value)}`).join(', ')

/** Horizontal bars: one row per category. `marker` draws a reference line (e.g. a 75% minimum). */
export function BarList({ data, format = plain, max, marker, color = 'var(--chart-1)', colors }) {
  const top = max ?? Math.max(...data.map((d) => d.value), 0)
  if (!data.length) return <p className="chart-empty">No data yet.</p>
  return (
    <ul className="barlist" role="img" aria-label={summary(data, format)}>
      {data.map((d, i) => (
        <li key={d.label}>
          <span className="barlist-label" title={d.label}>{d.label}</span>
          <span className="barlist-track">
            <span className="barlist-bar" style={{ width: `${top ? (d.value / top) * 100 : 0}%`, background: colors?.[i] ?? color }} />
            {marker != null && top > 0 && <i className="barlist-marker" style={{ left: `${(marker / top) * 100}%` }} />}
          </span>
          <span className="barlist-value">{format(d.value)}</span>
        </li>
      ))}
    </ul>
  )
}

/** Vertical columns for a short series (levels, grades, weeks). */
export function Columns({ data, format = plain, colors, color = 'var(--chart-1)', height = 180, max }) {
  const top = max ?? Math.max(...data.map((d) => d.value), 0)
  if (!data.length) return <p className="chart-empty">No data yet.</p>
  return (
    <div className="columns" style={{ '--chart-height': `${height}px` }} role="img" aria-label={summary(data, format)}>
      {data.map((d, i) => (
        <div key={d.label} className="columns-col" title={`${d.label}: ${format(d.value)}`}>
          {/* The bar and its value share a fixed-height track, so every label lines up underneath. */}
          <div className="columns-track">
            <span className="columns-value">{format(d.value)}</span>
            <span className="columns-bar" style={{ height: `${top ? Math.max((d.value / top) * 100, d.value ? 2 : 0) : 0}%`, background: colors?.[i] ?? color }} />
          </div>
          <span className="columns-label">{d.label}</span>
        </div>
      ))}
    </div>
  )
}

/** A filled line over time. Hover (or tap) a period to see its value. */
export function AreaChart({ data, format = plain, height = 200 }) {
  const id = useId()
  const [active, setActive] = useState(null)
  if (!data.length) return <p className="chart-empty">No data yet.</p>
  const W = 600
  const H = 200
  const top = Math.max(...data.map((d) => d.value), 1) * 1.1
  const step = data.length > 1 ? W / (data.length - 1) : W
  const points = data.map((d, i) => [i * step, H - (d.value / top) * H])
  const line = points.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  const area = `${line} L${W},${H} L0,${H} Z`
  const shown = active ?? data.length - 1
  return (
    <div className="area" role="img" aria-label={summary(data, format)}>
      <div className="area-readout">
        <strong>{format(data[shown].value)}</strong>
        <span>{data[shown].label}</span>
      </div>
      <div className="area-plot" style={{ height }}>
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <linearGradient id={`${id}-fill`} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="var(--chart-1)" stopOpacity="0.35" />
              <stop offset="100%" stopColor="var(--chart-1)" stopOpacity="0.02" />
            </linearGradient>
          </defs>
          {[0.25, 0.5, 0.75].map((f) => <line key={f} x1="0" x2={W} y1={H * f} y2={H * f} className="area-grid" />)}
          <path d={area} fill={`url(#${id}-fill)`} />
          <path d={line} className="area-line" />
        </svg>
        {/* Hover targets and the highlighted point are HTML so they don't stretch with the SVG. */}
        <div className="area-hits">
          {data.map((d, i) => (
            <button key={d.label} type="button" className={i === shown ? 'active' : ''} aria-label={`${d.label}: ${format(d.value)}`}
                    onMouseEnter={() => setActive(i)} onFocus={() => setActive(i)} onMouseLeave={() => setActive(null)}>
              {i === shown && <span className="area-dot" style={{ bottom: `${(d.value / top) * 100}%` }} />}
            </button>
          ))}
        </div>
      </div>
      <div className="area-labels">
        {data.map((d, i) => <span key={d.label} className={i % 2 && data.length > 8 ? 'area-label-minor' : ''}>{d.label}</span>)}
      </div>
    </div>
  )
}

/** Share of a whole, with a legend. */
export function Donut({ data, format = plain, colors, centerLabel = 'Total' }) {
  const total = data.reduce((s, d) => s + d.value, 0)
  if (!total) return <p className="chart-empty">No data yet.</p>
  const r = 15.915 // circumference 100, so dash lengths are percentages
  // Each segment starts where the previous one ended, beginning at 12 o'clock.
  const segments = data.map((d, i) => {
    const before = data.slice(0, i).reduce((s, x) => s + x.value, 0)
    return { ...d, pct: (d.value / total) * 100, offset: 25 - (before / total) * 100 }
  })
  return (
    <div className="donut" role="img" aria-label={summary(data, format)}>
      <svg viewBox="0 0 42 42" aria-hidden="true">
        <circle cx="21" cy="21" r={r} className="donut-track" />
        {segments.map((d, i) => (
          <circle key={d.label} cx="21" cy="21" r={r} fill="none" stroke={colors?.[i] ?? colorAt(i)} strokeWidth="6"
                  strokeDasharray={`${d.pct} ${100 - d.pct}`} strokeDashoffset={d.offset}>
            <title>{`${d.label}: ${format(d.value)} (${Math.round(d.pct)}%)`}</title>
          </circle>
        ))}
        <text x="21" y="20.5" className="donut-total">{format(total)}</text>
        <text x="21" y="25.5" className="donut-caption">{centerLabel}</text>
      </svg>
      <ul className="legend">
        {data.map((d, i) => (
          <li key={d.label}>
            <i style={{ background: colors?.[i] ?? colorAt(i) }} />
            <span>{d.label}</span>
            <strong>{format(d.value)}</strong>
            <em>{Math.round((d.value / total) * 100)}%</em>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Stages of a process; each bar shows its share of the first stage. */
export function Funnel({ data, format = plain }) {
  const first = data[0]?.value || 0
  if (!first) return <p className="chart-empty">No data yet.</p>
  return (
    <ol className="funnel" role="img" aria-label={summary(data, format)}>
      {data.map((d, i) => (
        <li key={d.label}>
          <span className="funnel-bar" style={{ width: `${Math.max((d.value / first) * 100, 4)}%`, background: colorAt(i) }}>
            <strong>{format(d.value)}</strong>
          </span>
          <span className="funnel-label">{d.label}<em>{Math.round((d.value / first) * 100)}%</em></span>
        </li>
      ))}
    </ol>
  )
}

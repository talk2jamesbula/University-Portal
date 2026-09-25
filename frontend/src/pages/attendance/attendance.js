/** Shared attendance labels and small display pieces. */

export const STATUS_OPTIONS = [
  ['present', 'Present'],
  ['late', 'Late'],
  ['excused', 'Excused'],
  ['absent', 'Absent'],
]

export const STATUS_LABEL = Object.fromEntries(STATUS_OPTIONS)
export const STATUS_TONE = { present: 'green', late: 'amber', excused: 'blue', absent: 'red' }
export const SESSION_TONE = { scheduled: 'neutral', open: 'green', closed: 'blue' }
export const CORRECTION_TONE = { pending: 'amber', approved: 'green', rejected: 'red' }

export const formatPercent = (value) => (value == null ? '—' : `${Number(value).toFixed(1).replace(/\.0$/, '')}%`)

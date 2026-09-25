const DAY_NAMES = { MON: 'Mon', TUE: 'Tue', WED: 'Wed', THU: 'Thu', FRI: 'Fri' }
export const WEEKDAYS = ['MON', 'TUE', 'WED', 'THU', 'FRI']

export function formatTime(value) {
  if (!value) return ''
  const [h, m] = value.split(':').map(Number)
  const suffix = h >= 12 ? 'PM' : 'AM'
  return `${((h + 11) % 12) + 1}:${String(m).padStart(2, '0')} ${suffix}`
}

export function formatDays(days) {
  return (days || '').split(',').filter(Boolean).map((d) => DAY_NAMES[d] ?? d).join(' · ')
}

/** "9:00–10:15 AM", or "11:00 AM–12:15 PM" when the range crosses noon. */
export function formatTimeRange(start, end) {
  if (!start || !end) return ''
  const [a, b] = [formatTime(start), formatTime(end)]
  return a.slice(-2) === b.slice(-2) ? `${a.slice(0, -3)}–${b}` : `${a}–${b}`
}

export function formatSchedule(course) {
  if (!course.days) return 'Schedule TBA'
  return `${formatDays(course.days)}  ${formatTimeRange(course.start_time, course.end_time)}`
}

/**
 * Parse API dates. A plain date ("2026-09-30") means that calendar day wherever the user is;
 * new Date() would read it as UTC midnight and show the previous day west of Greenwich.
 */
export function parseDate(value) {
  const plain = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  return plain ? new Date(Number(plain[1]), Number(plain[2]) - 1, Number(plain[3])) : new Date(value)
}

export function formatDate(value, opts = {}) {
  if (!value) return ''
  return parseDate(value).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric', ...opts })
}

export function formatDateTime(value) {
  if (!value) return ''
  return new Date(value).toLocaleString(undefined, {
    weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
  })
}

/** The time of day of a full timestamp, e.g. "9:15 AM". */
export function formatClock(value) {
  if (!value) return ''
  return new Date(value).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
}

export function timeAgo(value) {
  const seconds = Math.round((Date.now() - new Date(value).getTime()) / 1000)
  const units = [['year', 31536000], ['month', 2592000], ['week', 604800], ['day', 86400], ['hour', 3600], ['minute', 60]]
  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })
  for (const [unit, size] of units) {
    if (seconds >= size) return rtf.format(-Math.floor(seconds / size), unit)
  }
  return 'just now'
}

export const initials = (name = '') =>
  name.split(' ').filter(Boolean).slice(0, 2).map((p) => p[0].toUpperCase()).join('')

export const ROLE_LABELS = { student: 'Student', staff: 'Staff', applicant: 'Applicant', admin: 'Super Admin' }

export const UNIVERSITY_NAME = import.meta.env.VITE_UNIVERSITY_NAME || 'BULACODE UNIVERSITY'

export const PRIORITY_TONE = { urgent: 'red', important: 'amber', normal: 'neutral' }
export const CATEGORY_TONE = { academic: 'blue', career: 'green', social: 'purple', sports: 'amber', deadline: 'red' }

const money = new Intl.NumberFormat('en-NG', { style: 'currency', currency: 'NGN' })
export const formatMoney = (value) => money.format(Number(value || 0))

export const CHARGE_STATUS = {
  paid: { label: 'Paid', tone: 'green' },
  partial: { label: 'Partly paid', tone: 'amber' },
  unpaid: { label: 'Unpaid', tone: 'neutral' },
  overdue: { label: 'Overdue', tone: 'red' },
}

/** Today's date as YYYY-MM-DD in the user's own timezone (toISOString would give UTC). */
export function localToday() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

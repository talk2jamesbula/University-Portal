/** Shared examination labels and small helpers. */

export const EXAM_STATUS_TONE = { draft: 'neutral', published: 'green' }
export const MODE_TONE = { paper: 'blue', cbt: 'purple' }
export const ATTEMPT_TONE = { in_progress: 'amber', submitted: 'green', timed_out: 'blue' }

export const MODE_OPTIONS = [
  ['paper', 'Written (paper)'],
  ['cbt', 'Computer-based test'],
]

/** "2 h", "1 h 30 min", "45 min". */
export function formatDuration(minutes) {
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return [h && `${h} h`, m && `${m} min`].filter(Boolean).join(' ') || '0 min'
}

/** "1:05:09" or "4:09" from a number of seconds. */
export function formatCountdown(seconds) {
  const s = Math.max(0, Math.floor(seconds))
  const h = Math.floor(s / 3600)
  const mm = String(Math.floor((s % 3600) / 60)).padStart(h ? 2 : 1, '0')
  const ss = String(s % 60).padStart(2, '0')
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`
}

/** Reads the card code from an exam card QR link, or null if it isn't one. */
export function parseCardLink(text) {
  try {
    const url = new URL(text, window.location.origin)
    const code = url.searchParams.get('c')
    return url.pathname.endsWith('/portal/exams/verify') && code ? { code } : null
  } catch {
    return null
  }
}

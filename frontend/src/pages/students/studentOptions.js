/** Shared student-management labels and options. */

export const STATUSES = [
  ['active', 'Active', 'green'],
  ['probation', 'On probation', 'amber'],
  ['suspended', 'Suspended', 'red'],
  ['deferred', 'Deferred', 'amber'],
  ['withdrawn', 'Withdrawn', 'neutral'],
  ['expelled', 'Expelled', 'red'],
  ['completed', 'Completed', 'blue'],
  ['graduated', 'Graduated', 'purple'],
]
export const STATUS_TONE = Object.fromEntries(STATUSES.map(([v, , tone]) => [v, tone]))
export const STATUS_LABEL = Object.fromEntries(STATUSES.map(([v, label]) => [v, label]))

export const MODES_OF_ENTRY = [['utme', 'UTME'], ['de', 'Direct Entry'], ['transfer', 'Inter-university transfer']]
export const GENDERS = [['female', 'Female'], ['male', 'Male']]

/** Academic sessions from 2018/2019 to next session. */
export function sessions() {
  const now = new Date()
  const last = now.getFullYear() + (now.getMonth() >= 7 ? 1 : 0)
  const list = []
  for (let y = last; y >= 2018; y--) list.push(`${y}/${y + 1}`)
  return list
}

/** Levels for a programme: 100 to its final year, plus two spill-over years. */
export const levelsFor = (durationYears = 4) => Array.from({ length: durationYears + 2 }, (_, i) => (i + 1) * 100)

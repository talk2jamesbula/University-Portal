/** Shared labels for the results workflow (see backend/apps/academics/results.py). */

export const RESULT_STAGES = [
  ['draft', 'Scores entered'],
  ['submitted', 'With HOD'],
  ['department_approved', 'With Dean'],
  ['faculty_approved', 'With Exams Office'],
  ['published', 'Published'],
]

export const RESULT_STATUS_LABEL = {
  pending: 'Not yet entered',
  draft: 'Draft',
  submitted: 'Submitted to HOD',
  department_approved: 'Approved by HOD',
  faculty_approved: 'Approved by Dean',
  published: 'Published',
}

export const RESULT_STATUS_TONE = {
  pending: 'neutral',
  draft: 'amber',
  submitted: 'blue',
  department_approved: 'blue',
  faculty_approved: 'purple',
  published: 'green',
}

/** What approving means at each stage, for the button. */
export const APPROVE_LABEL = {
  submitted: 'Approve as HOD',
  department_approved: 'Approve as Dean',
  faculty_approved: 'Publish results',
}

export const GRADES = ['A', 'B', 'C', 'D', 'E', 'F']

/** Grade for a total out of 100, mirroring backend/apps/academics/grading.py. */
export function gradeFor(total) {
  if (total == null) return null
  if (total >= 70) return 'A'
  if (total >= 60) return 'B'
  if (total >= 50) return 'C'
  if (total >= 45) return 'D'
  if (total >= 40) return 'E'
  return 'F'
}

export const formatScore = (n) => (n == null || n === '' ? '—' : Number(n).toFixed(1).replace(/\.0$/, ''))

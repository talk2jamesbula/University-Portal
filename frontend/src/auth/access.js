/** Access helpers mirroring the backend's RBAC (see backend/apps/accounts/rbac.py). */

export const isStudent = (user) => user?.role === 'student'
export const isStaff = (user) => user?.role === 'staff'
export const isSuperAdmin = (user) => user?.role === 'admin'
export const isApplicant = (user) => user?.role === 'applicant'
/** Students, staff and admins; applicants only see their own application. */
export const isMember = (user) => Boolean(user) && !isApplicant(user)

/** True if the user holds any of the permission codes. Super admins hold them all. */
export const can = (user, ...codes) => Boolean(user?.permissions?.some((p) => codes.includes(p)))

/** A short description of who the user is, for the top bar. */
export function roleLabel(user) {
  if (isStudent(user)) {
    const level = user.student_profile?.level
    return level ? `Student · ${level} Level` : 'Student'
  }
  if (isSuperAdmin(user)) return 'Super Admin'
  if (isApplicant(user)) return 'Applicant'
  return user.assignments?.[0]?.role_name || user.staff_profile?.designation || 'Staff'
}

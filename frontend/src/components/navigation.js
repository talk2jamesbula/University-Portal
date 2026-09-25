import { can, isApplicant, isMember, isStaff, isStudent, isSuperAdmin } from '../auth/access'

/**
 * Sidebar entries. `show(user)` decides visibility, mirroring the backend's permissions,
 * so each role sees only what it can use. App.jsx guards the same routes.
 */
export const NAV = [
  { to: '/portal', label: 'Dashboard', icon: 'home', end: true, show: () => true },

  // Applicants
  { to: '/portal/application', label: 'My Application', icon: 'register', show: isApplicant },

  // Students
  { to: '/portal/registration', label: 'Course Registration', icon: 'register', show: isStudent },
  { to: '/portal/my-courses', label: 'My Courses', icon: 'book', show: isStudent },
  { to: '/portal/results', label: 'Results', icon: 'award', show: isStudent },
  { to: '/portal/attendance', label: 'Attendance', icon: 'check', show: isStudent },
  { to: '/portal/fees', label: 'Fees & Payments', icon: 'wallet', show: isStudent },

  // Staff
  { to: '/portal/teaching', label: 'My Courses', icon: 'book', show: (u) => isStaff(u) && can(u, 'courses.teach') },
  { to: '/portal/fees', label: 'Fees & Payments', icon: 'wallet', show: (u) => !isStudent(u) && can(u, 'finance.view') },

  // Administration
  { to: '/portal/manage/courses', label: 'Manage Courses', icon: 'catalog', show: (u) => can(u, 'academics.manage') },
  { to: '/portal/manage/students', label: 'Students', icon: 'users', show: (u) => can(u, 'students.view', 'students.manage') },
  { to: '/portal/manage/admissions', label: 'Admissions', icon: 'cap', show: (u) => can(u, 'admissions.manage') },
  { to: '/portal/manage/attendance', label: 'Attendance Reports', icon: 'check', show: (u) => can(u, 'attendance.view', 'attendance.approve') },

  // Everyone
  { to: '/portal/courses', label: 'Course Offerings', icon: 'catalog', show: isMember },
  { to: '/portal/announcements', label: 'Announcements', icon: 'megaphone', show: isMember },
  { to: '/portal/notifications', label: 'Notifications', icon: 'bell', show: () => true },
  { to: '/portal/events', label: 'Academic Calendar', icon: 'calendar', show: isMember },
  { to: '/portal/directory', label: 'Staff Directory', icon: 'users', show: isMember },
]

export const showsAdminConsole = isSuperAdmin

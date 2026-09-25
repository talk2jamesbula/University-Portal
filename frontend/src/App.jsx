import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { can, isApplicant, isMember, isStaff, isStudent } from './auth/access'
import { useAuth } from './auth/useAuth'
import Layout from './components/Layout'
import { Spinner } from './components/ui'
import AdmissionsList from './pages/admissions/AdmissionsList'
import ApplicantHome from './pages/admissions/ApplicantHome'
import ApplicationForm from './pages/admissions/ApplicationForm'
import ApplicationReview from './pages/admissions/ApplicationReview'
import AttendanceReports from './pages/attendance/AttendanceReports'
import StudentProfile from './pages/students/StudentProfile'
import StudentsList from './pages/students/StudentsList'
import CheckIn from './pages/attendance/CheckIn'
import CourseAttendance from './pages/attendance/CourseAttendance'
import MyAttendance from './pages/attendance/MyAttendance'
import SessionDetail from './pages/attendance/SessionDetail'
import ExamDetail, { CourseExam } from './pages/exams/ExamDetail'
import ExamTimetable from './pages/exams/ExamTimetable'
import MyExams from './pages/exams/MyExams'
import TakeExam from './pages/exams/TakeExam'
import VerifyCard from './pages/exams/VerifyCard'
import ResultSheet from './pages/results/ResultSheet'
import ResultSheets from './pages/results/ResultSheets'
import CourseDetail from './pages/manage/CourseDetail'
import Courses from './pages/manage/Courses'
import Announcements from './pages/Announcements'
import CourseOfferings from './pages/CourseOfferings'
import CourseRoster from './pages/CourseRoster'
import Dashboard from './pages/Dashboard'
import Directory from './pages/Directory'
import Events from './pages/Events'
import FinanceAdmin from './pages/finance/FinanceAdmin'
import PaystackCallback from './pages/finance/PaystackCallback'
import StudentAccount from './pages/finance/StudentAccount'
import StudentFees from './pages/finance/StudentFees'
import MyCourses from './pages/MyCourses'
import NotFound from './pages/NotFound'
import Notifications from './pages/Notifications'
import Profile from './pages/Profile'
import Registration from './pages/Registration'
import Results from './pages/Results'
import Apply from './site/Apply'
import About from './site/pages/About'
import Admissions from './site/pages/Admissions'
import Contact from './site/pages/Contact'
import Credits from './site/pages/Credits'
import SiteEvents from './site/pages/Events'
import Faculties from './site/pages/Faculties'
import Home from './site/pages/Home'
import Library from './site/pages/Library'
import News from './site/pages/News'
import NewsArticle from './site/pages/NewsArticle'
import ProgrammeDetail from './site/pages/ProgrammeDetail'
import Programmes from './site/pages/Programmes'
import Research from './site/pages/Research'
import SiteNotFound from './site/pages/SiteNotFound'
import PortalLogin from './site/PortalLogin'
import SiteLayout from './site/SiteLayout'

/** Renders the page only if `allow(user)`; otherwise back to the dashboard. */
function Guard({ allow, children }) {
  const { user } = useAuth()
  return allow(user) ? children : <Navigate to="/portal" replace />
}

const teaches = (u) => isStaff(u) && can(u, 'courses.teach')
const seesFinance = (u) => can(u, 'finance.view')
const managesAcademics = (u) => can(u, 'academics.manage')
const seesStudentRecords = (u) => can(u, 'students.view', 'students.manage')
const managesAdmissions = (u) => can(u, 'admissions.manage')
const seesAttendanceAdmin = (u) => can(u, 'attendance.view', 'attendance.approve')
const reviewsResults = (u) => can(u, 'results.approve_department', 'results.approve_faculty', 'results.publish')
const seesClassLists = (u) => teaches(u) || reviewsResults(u) || seesAttendanceAdmin(u)
const seesResultSheets = (u) => teaches(u) || reviewsResults(u)
const managesExams = (u) => can(u, 'exams.manage')
const invigilates = (u) => can(u, 'exams.invigilate', 'exams.manage')

/** The signed-in portal. Signed-out visitors are sent to sign in, then brought back. */
function Portal() {
  const { user, loading, exitTo } = useAuth()
  const location = useLocation()

  if (loading) return <div className="fullscreen-center"><Spinner /></div>
  if (!user && exitTo) return <Navigate to={exitTo} replace />
  if (!user) {
    const staffOnly = ['/portal/teaching', '/portal/manage', '/portal/attendance/sessions', '/portal/results/sheets', '/portal/exams/verify']
    const portal = location.pathname.startsWith('/portal/application') ? 'applicant'
      : staffOnly.some((p) => location.pathname.startsWith(p)) ? 'staff' : 'student'
    return <Navigate to={`/login/${portal}`} replace state={{ from: location.pathname + location.search }} />
  }

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={isApplicant(user) ? <ApplicantHome /> : <Dashboard />} />
        {/* Applicants */}
        <Route path="application" element={<Guard allow={isApplicant}><ApplicationForm /></Guard>} />
        {/* Students */}
        <Route path="registration" element={<Guard allow={isStudent}><Registration /></Guard>} />
        <Route path="my-courses" element={<Guard allow={isStudent}><MyCourses /></Guard>} />
        <Route path="results" element={<Guard allow={isStudent}><Results /></Guard>} />
        <Route path="attendance" element={<Guard allow={isStudent}><MyAttendance /></Guard>} />
        <Route path="attend" element={<Guard allow={isStudent}><CheckIn /></Guard>} />
        <Route path="exams" element={<Guard allow={isStudent}><MyExams /></Guard>} />
        <Route path="exams/attempts/:id" element={<Guard allow={isStudent}><TakeExam /></Guard>} />
        <Route path="fees" element={
          <Guard allow={(u) => isStudent(u) || seesFinance(u)}>{isStudent(user) ? <StudentFees /> : <FinanceAdmin />}</Guard>
        } />
        <Route path="fees/paystack/callback" element={<Guard allow={isStudent}><PaystackCallback /></Guard>} />
        {/* Staff */}
        <Route path="teaching" element={<Guard allow={teaches}><MyCourses /></Guard>} />
        <Route path="teaching/:id" element={<Guard allow={seesClassLists}><CourseRoster /></Guard>} />
        <Route path="teaching/:id/attendance" element={<Guard allow={seesClassLists}><CourseAttendance /></Guard>} />
        <Route path="attendance/sessions/:id" element={<Guard allow={seesClassLists}><SessionDetail /></Guard>} />
        <Route path="teaching/:id/exam" element={<Guard allow={(u) => teaches(u) || managesExams(u)}><CourseExam /></Guard>} />
        <Route path="results/sheets/:id" element={<Guard allow={seesResultSheets}><ResultSheet /></Guard>} />
        <Route path="exams/verify" element={<Guard allow={invigilates}><VerifyCard /></Guard>} />
        <Route path="fees/students/:id" element={<Guard allow={seesFinance}><StudentAccount /></Guard>} />
        {/* Administration */}
        <Route path="manage/courses" element={<Guard allow={managesAcademics}><Courses /></Guard>} />
        <Route path="manage/courses/:id" element={<Guard allow={managesAcademics}><CourseDetail /></Guard>} />
        <Route path="manage/students" element={<Guard allow={seesStudentRecords}><StudentsList /></Guard>} />
        <Route path="manage/students/:id" element={<Guard allow={seesStudentRecords}><StudentProfile /></Guard>} />
        <Route path="manage/admissions" element={<Guard allow={managesAdmissions}><AdmissionsList /></Guard>} />
        <Route path="manage/admissions/:id" element={<Guard allow={managesAdmissions}><ApplicationReview /></Guard>} />
        <Route path="manage/attendance" element={<Guard allow={seesAttendanceAdmin}><AttendanceReports /></Guard>} />
        <Route path="manage/results" element={<Guard allow={seesResultSheets}><ResultSheets /></Guard>} />
        <Route path="manage/exams" element={<Guard allow={managesExams}><ExamTimetable /></Guard>} />
        <Route path="manage/exams/:id" element={<Guard allow={(u) => managesExams(u) || teaches(u)}><ExamDetail /></Guard>} />
        {/* Everyone */}
        <Route path="courses" element={<Guard allow={isMember}><CourseOfferings /></Guard>} />
        <Route path="announcements" element={<Guard allow={isMember}><Announcements /></Guard>} />
        <Route path="notifications" element={<Notifications />} />
        <Route path="events" element={<Guard allow={isMember}><Events /></Guard>} />
        <Route path="directory" element={<Guard allow={isMember}><Directory /></Guard>} />
        <Route path="profile" element={<Profile />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}

export default function App() {
  return (
    <Routes>
      {/* Public website */}
      <Route element={<SiteLayout />}>
        <Route index element={<Home />} />
        <Route path="about" element={<About />} />
        <Route path="faculties" element={<Faculties />} />
        <Route path="programmes" element={<Programmes />} />
        <Route path="programmes/:code" element={<ProgrammeDetail />} />
        <Route path="admissions" element={<Admissions />} />
        <Route path="news" element={<News />} />
        <Route path="news/:id" element={<NewsArticle />} />
        <Route path="events" element={<SiteEvents />} />
        <Route path="research" element={<Research />} />
        <Route path="library" element={<Library />} />
        <Route path="contact" element={<Contact />} />
        <Route path="credits" element={<Credits />} />
        <Route path="*" element={<SiteNotFound />} />
      </Route>
      {/* Sign-in */}
      <Route path="login" element={<Navigate to="/login/student" replace />} />
      <Route path="login/student" element={<PortalLogin key="student" portal="student" />} />
      <Route path="login/staff" element={<PortalLogin key="staff" portal="staff" />} />
      <Route path="login/applicant" element={<PortalLogin key="applicant" portal="applicant" />} />
      <Route path="apply" element={<Apply />} />
      {/* Portal */}
      <Route path="portal/*" element={<Portal />} />
    </Routes>
  )
}

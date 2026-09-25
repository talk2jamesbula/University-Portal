# University Portal

A web portal for students, faculty, and administrators.

| Layer    | Stack |
|----------|-------|
| Frontend | React 19, React Router, Vite, Axios, hand-written CSS (no UI framework) |
| Backend  | Django 5.2, Django REST Framework, SimpleJWT, django-filter |
| Database | PostgreSQL 16 |

## Features

**Public website** (no sign-in): Home, About, Faculties & Departments, Academic Programmes (with each programme's full curriculum), Admissions, News & Announcements, Events, Research, Library, Contact Us (a rate-limited form with a spam trap), and separate Student Portal and Staff Portal sign-in pages. Faculties, programmes, curricula, statistics, news and events come live from the database. Announcements appear on the site only when marked *Publish on the website*. Written content (about, admission requirements, research centres, library hours, contact details) lives in `frontend/src/site/content.js`; **replace the placeholder address, phone and email there with the university's real ones.**

The About page lists principal officers (VC, Registrar, Bursar), deans and heads of department straight from role appointments, with each person's portal profile photo. Staff can add their own photo under My Profile, or the Registry (`users.manage`) can add official photos from the Staff Directory. Anyone without a photo is shown with a neutral silhouette.

Student photos (`frontend/src/assets/students/`) are Creative Commons images from Wikimedia Commons, credited on the site's **Photo credits** page (`/credits`). Before launch, replace them with the university's own photos and update `frontend/src/site/photos.js`.


**Applicants** (online admissions: sign up at `/apply`, sign in at `/login/applicant`)
- Create an account with email and phone, then fill a six-step application: personal details, programme choice (first and second choice), academic record (JAMB registration number, UTME score, O-Level results; previous qualification for Direct Entry or transfer), documents, application fee, review and submit
- Upload a passport photograph, O-Level result, JAMB result slip and birth certificate (checked by content, PDF/JPG/PNG up to 5 MB); replace a document if the Admissions Office rejects it
- Pay the application fee through Paystack (PDF receipt), submit, then track the application through each status with a timeline; in-app and email notifications at every step
- Download the PDF admission letter when admitted, and accept the offer online

**Students**
- Dashboard with passport photo, matric number, programme, level, current semester, CGPA, outstanding fees, course registration status, lecture timetable, announcements, notifications and the academic calendar
- Course registration from the programme curriculum: compulsory and elective courses, automatic carry-overs of failed courses, add/drop, unit limits (15–24 by default), capacity and timetable-clash checks
- Results: CA and exam scores, grades on the NUC five-point scale, GPA per semester, CGPA, class of degree and academic standing
- Student record: programme and personal details, plus editable contact, next-of-kin and emergency details
- Fees and payments: statements per semester, Paystack online payment, proof-of-payment upload for bank/POS payments, PDF receipts (also emailed) and invoices
- Attendance: check in to a class by scanning the lecturer's QR code or typing its 6-digit code; attendance percentage and full history per course, with a warning below the 75% requirement
- Examinations: personal exam timetable with venue and seat, eligibility per course (with the reason if blocked), a PDF exam card with photo and QR code, and computer-based tests sat in the browser
- In-app notifications (with email and SMS alerts for important events)

**Lecturers**
- Dashboard with assigned courses, registered students, today's classes and pending results
- Class lists with matric numbers, levels, carry-over flags and scores
- Attendance: create sessions, start check-in with a rotating QR code (with a full-screen projector view), mark students by hand, close sessions (everyone else is marked absent), request corrections to closed sessions, and per-student statistics
- Result sheets: enter CA and exam scores, submit to the HOD, and see where the results are in the approval chain
- Computer-based tests: write multiple-choice and true/false questions, see submitted papers (with how often each candidate left the page), and send the marks to the result sheet
- Announcements to the students of their courses

**Administration (by role)**
- Role-based access control: every action requires a permission; staff hold roles (Registrar, Bursar, Dean, HOD, Lecturer, Examination Officer, ...) whose permissions can be edited
- Academic structure: faculties, departments, programmes, course catalogue, curricula, sessions and semesters, course offerings
- **Manage Courses** (`academics.manage`: Registrar, super admin): create catalogue courses and, in the same step, add them to programme curricula (compulsory or elective) and offer them in a semester with a lecturer, timetable and venue. Creation is all or nothing, and codes are normalised (`csc 207` → `CSC207`). Each course has a page for editing it and managing its curricula and offerings. Courses in use can't be deleted; mark them inactive instead.
- **Student Management** (`students.manage`: Registrar, super admin; `students.view`: HODs and Deans for their department or faculty, and the VC): search and filter students (faculty, department, programme, level, status, session, gender, portal access) with pagination; create and edit students (matric number, Student ID, username and a temporary password are generated automatically); import from CSV or Excel (every row checked first, all-or-nothing) and export to CSV/Excel; change academic status with a reason (history kept, student notified); activate or deactivate portal access; reset passwords; passport photographs and private documents. Each student has a profile page with tabs for Overview, Academic Records, Courses, Attendance, Results, Fees, Documents, Accommodation and Activity History
- Bursary: collection totals, student balances, charges, payments, proof-of-payment review
- **Admissions** (`admissions.manage`: Admission Officer, Registrar): applications by status, search (name, email, application or JAMB number), filters (faculty, programme, entry mode, fee paid), sorting by aggregate score, CSV/Excel export; per application: verify or reject each document, record the post-UTME screening score (aggregate = UTME ÷ 8 + screening ÷ 2), approve for the first or second choice, waitlist or reject with a reason, issue the admission letter, internal notes, and the full history; admission exercise settings (fee, dates, UTME cut-off, acceptance deadline)
- **Examinations** (`exams.manage`: Examination Officer, super admin): venues and CBT centres; the exam timetable with clash and seating checks; seat allocation; publishing (every candidate is emailed); eligibility per candidate with waivers; printing exam cards. See [Examinations](#examinations)
- **Result approval** (HOD, Dean, Examination Officer / Registrar): approve, return with a note, or publish each course's results
- Attendance reports filtered by semester, faculty, department, course and student, with at-risk students highlighted and CSV/Excel export; HODs and the Registrar approve attendance corrections
- Announcements to the whole university, one audience, or a department
- Audit log and sign-in history
- **Analytics on the admin dashboard** (`reports.view`: VC, Registrar, Bursar, Deans, super admin): students by faculty, level, status and gender; course registration by level; grade distribution, pass rate and average GPA by department (latest published results); attendance by faculty against the 75% minimum; the admissions funnel, weekly applications and most popular programmes; and, for staff with `finance.view`, fee collections over 12 months, payments by method and outstanding fees by faculty. Deans see only their faculty. Charts are built in (`frontend/src/components/charts.jsx`, no chart library) and follow dark mode; the data comes from `GET /api/reports/analytics/` (`apps/reports`)

**Everyone**
- Staff directory, academic calendar, announcements, profile photo, password change
- JWT authentication with silent token refresh; responsive layout; dark mode that follows the OS

## Quick start

### Option A: Docker (recommended)

```bash
docker compose up --build
docker compose exec api python manage.py seed_demo
```

Open http://localhost:5173 for the public website. The portal is at `/portal` (sign in at `/login/student` or `/login/staff`).

### Option B: Run locally

You need Python 3.12+, Node 20+, and a running PostgreSQL server.

```bash
# 1. Database (example using psql)
createuser portal --pwprompt          # password: portal
createdb university_portal -O portal

# 2. Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                  # edit the DB credentials if needed
python manage.py migrate
python manage.py seed_demo
python manage.py runserver            # http://127.0.0.1:8000

# 3. Frontend (in a new terminal)
cd frontend
npm install
npm run dev                           # http://localhost:5173
```

The Vite dev server proxies `/api` and `/admin` to Django, so you don't need to configure CORS during development.

### Demo accounts

All demo accounts use the password `Portal@2026`.

| Username | Who | What they can do |
|---|---|---|
| `student` | Chinedu Okafor, 200 Level Computer Science (`BU/25/CSC/0004`) | Student portal: has results, a carry-over and an incomplete registration |
| `lecturer` | Dr. Adaeze Okonkwo | Lecturer: teaching dashboard, class lists |
| `hod` | Prof. Babatunde Ogunleye | Head of Computer Science and lecturer |
| `dean` | Prof. Ngozi Eze | Dean of the Faculty of Science |
| `registrar` | Mrs. Folasade Adeyemi | Registrar: users, roles, academic structure, announcements (also Django admin) |
| `bursar` | Mr. Emeka Nwankwo | Bursary: fees, payments, proofs of payment |
| `examofficer` | Dr. Hauwa Musa | Examination Officer |
| `vc` | Prof. Aminu Bello | Vice Chancellor: management reports |
| `admin` | System Administrator | Super admin: every permission, and the Django admin at `/admin/` |
| `admissions1` | Ms. Grace Etim | Admission Officer: reviews applications (staff sign-in) |
| `applicant` | Chioma Nwosu | Applicant with a half-finished draft (sign in at `/login/applicant`) |
| `applicant2` | Emeka Obiora | Applicant who has been offered admission: can download the letter and accept |

Other students sign in with their matric number without slashes in lower case (e.g. `bu25csc0005`). To wipe and regenerate the demo data, run `python manage.py seed_demo --flush`.

## Academic structure and grading

- **Structure:** Faculty → Department → Programme (e.g. *B.Sc. Computer Science*, 4 years). Each programme has a **curriculum** of catalogue courses marked compulsory or elective. A **course** (CSC201, 3 units, 200 Level, First Semester) is **offered** each semester with a lecturer, timetable and venue.
- **Calendar:** each academic **session** (e.g. `2026/2027`) has a **First Semester** (about September–February) and a **Second Semester** (about March–July). Mark one semester as current; *Registration open* controls course registration and add/drop, and opening it notifies every active student.
- **Registration:** students see the curriculum courses for their level and the current semester. Courses they have passed are hidden, and failed ones return as carry-overs. The limits are `MIN_UNITS_PER_SEMESTER` (15) and `MAX_UNITS_PER_SEMESTER` (24).
- **Grading (NUC five-point scale):** CA out of 30 plus examination out of 70. A 70–100 (5), B 60–69 (4), C 50–59 (3), D 45–49 (2), E 40–44 (1), F 0–39 (0). GPA and CGPA are unit-weighted and rounded half up to two decimals. Classes of degree run from First Class (4.50+) down to Pass (1.00–1.49); a CGPA below 1.00 means probation.
- **Results workflow:** each result moves *draft → submitted to HOD → approved by HOD → approved by Dean → published*. Students only ever see published results.

## Examinations

- **Timetable.** The Examinations Office adds venues (seats, and whether each is a CBT centre), then schedules one exam per course offering: date, start time, duration, mode (*paper* or *CBT*) and one or more venues. The timetable page lists problems to fix: students with two exams at once, venues too small, exams without a venue, CBTs without questions or outside a CBT centre. Drafts are invisible to students; **Publish** gives every candidate a seat and emails them once. Moving a published exam (date, time or venue) emails and texts its candidates.
- **Seating.** Seats are numbered per venue and filled in matric-number order. Allocating again only seats students who registered late (printed cards stay right), and halls shared by exams at the same time never give out the same seat twice.
- **Eligibility.** A student may sit a course's exam if they are registered for it, have at least `ATTENDANCE_MIN_PERCENT` (75%) attendance once classes have been recorded, and (if `EXAM_REQUIRE_FEES_CLEARED`) have no overdue fees. The Examinations Office can grant a waiver with a reason (audited; the student is notified). Eligibility is always worked out live, so it follows payments and attendance changes.
- **Exam cards.** Students download a PDF card listing their eligible exams with venue and seat, their photo, and a QR code signed with the server's secret key. Invigilators (`exams.invigilate`: lecturers and the Examinations Office) open **Verify Exam Cards**, scan the card or type the matric number, see the student's photo and live eligibility, and admit them to the hall; check-ins are recorded.
- **Computer-based tests.** The course lecturer writes multiple-choice or true/false questions (one correct option each) and may draw a random subset per candidate. Each candidate's paper is shuffled (questions and options) when they start. The clock runs on the server: answers are autosaved and refused once time is up (plus `EXAM_ANSWER_GRACE_SECONDS`), and papers still open are submitted automatically. One attempt per student is enforced by the database. Entry closes `late_entry_minutes` after the start. Leaving the exam page is logged, and candidates who do it `EXAM_FOCUS_FLAG_AFTER` times are flagged. Questions lock when the exam starts, and correct answers are never sent to students.
- **Into the results.** The lecturer sends CBT marks, scaled to 70, into the course's result sheet as exam scores; paper exams are entered by hand. The sheet then goes through the results workflow below.
- **Results workflow.** The lecturer enters CA and exam scores and submits (every student needs both). The HOD approves, then the Dean, then the Examinations Office or Registrar publishes, and students are emailed. At each stage the reviewer can return the sheet to the lecturer with a note. Nobody approves a course they teach, and each step is kept in the sheet's history and the audit log.
- **Demo data.** `seed_demo` includes a published timetable. To add one to an existing database, run `python manage.py seed_exams`; add `--live-cbt` to open the GST211 CBT now (sign in as `student` to sit it).

## Roles and permissions

Access is controlled by **permission codes** (e.g. `finance.manage`, `results.publish`), listed in `backend/apps/accounts/rbac.py`. Every user has an account type (*student*, *staff*, *applicant* or *super admin*). Staff get **role appointments**, and each role grants a set of permissions:

| Role | Scope | Main permissions |
|---|---|---|
| Vice Chancellor | University | reports, finance (view), audit log |
| Registrar | University | users, roles, student records, academic structure, registration, result publication, attendance (view and approve corrections), admissions, documents, announcements |
| Bursar / Finance Officer | University | finance (view and manage) |
| Dean | A faculty | approve faculty results, view attendance, announcements |
| Head of Department | A department | approve department results, view attendance and approve corrections, announcements |
| Lecturer | — | teach assigned courses, enter scores, set CBT questions, invigilate |
| Examination Officer | University | exam timetables and venues, eligibility waivers, exam cards, invigilation, result publication |
| Admission Officer, Librarian, Hostel Officer, Support Officer | University | their service areas |

The default roles are created automatically when you migrate. Their permissions can be changed through the API (`/api/roles/`) or the Django admin without touching code. Appointments are made with `/api/role-assignments/` (the Registry), and a Dean or HOD must be tied to their faculty or department. Super admins hold every permission.

## Notifications, audit log and sign-in history

- `apps/core/services.notify()` creates in-app notifications and can also send email and SMS. SMS goes through Termii when `SMS_BACKEND=termii` is set; otherwise messages are just logged. Links in emails use `PORTAL_URL`.
- `apps/core/services.audit()` records important actions: role changes, user management, semester updates and password changes.
- Every sign-in attempt, successful or not, is recorded with its IP address and browser. Users can see their own history; staff with `audit.view` can see everyone's.

## Fees and payments

- **Billing follows enrollment.** When a student registers or drops, their tuition for the semester (credits × the semester's `tuition_per_credit`) and the mandatory fees (`FeeType`) are recalculated automatically. If a student drops every course, those charges are removed, and anything already paid shows as a credit.
- **Payments are applied to the oldest charges first.** This is how each charge gets its paid, partly paid, unpaid or overdue status. A charge is overdue once its due date (the semester's `fee_due_date`) has passed.
- **Admins can change rates and fees** in the Django admin. After changing a semester's tuition rate, use the *Recalculate tuition and fees* action on Semesters to re-bill students.
- **Online payments go through Paystack.** See [Paystack setup](#paystack-setup) below.
- **Receipts and invoices.** Every completed payment, whether through Paystack or recorded by the bursary, gets a numbered PDF receipt. The receipt shows the amount in figures and words, the payment method and reference, which charges it paid, and the remaining balance. It is emailed to the student with the PDF attached, and can be downloaded from the payment history. Each semester also has a PDF invoice (`INV-<SESSION>-<SEMESTER>-<STUDENT ID>`, e.g. `INV-2627-1-S2026001` for First Semester 2026/2027) listing charges, amounts paid and the balance due. Students download their own documents; admins can download any student's from that student's account page. PDFs use the bundled DejaVu Sans font (`apps/finance/fonts/`) so the ₦ sign prints.
- **Offline payments and proof of payment.** Students who pay at the bank, by transfer, by POS or in cash upload a photo or scan of their teller or receipt, with the amount, date, bank and teller/transaction reference. The upload stays *awaiting review* and doesn't change the balance. The Bursary reviews it under **Fees & Payments → Payment proofs** with the document shown alongside the details. They can **approve** it, optionally correcting the amount, which records the payment and emails the student a PDF receipt. Or they can **reject** it with a reason, which is emailed to the student, who can then resubmit. Uploads must be real PDF, JPG or PNG files (checked by their contents) up to 5 MB. They are stored under `MEDIA_ROOT` with random names and are only served through the API to the student and admins. A teller or transaction reference can't be submitted twice. Set `BURSARY_BANK_NAME`, `BURSARY_ACCOUNT_NAME` and `BURSARY_ACCOUNT_NUMBER` to show the university's account on the Fees page and on invoices, and `BURSARY_NOTIFY_EMAIL` to email the Bursary when a proof is uploaded.
- **Email.** Set `EMAIL_HOST` and the related settings in `backend/.env` to send email through SMTP. Without them, emails (including the attached PDF) are printed to the Django console.

## Website chatbot

Every page of the public website has an **Ask us** button that opens a chat assistant. It answers questions about admissions, requirements, the application fee and dates, programmes, contacts, the library, research and portal sign-in, with links to the right pages.

- **With Claude (recommended):** set `ANTHROPIC_API_KEY` in `backend/.env` (get a key at https://console.anthropic.com) and restart Django. Answers then come from Claude (`CHATBOT_MODEL`, default `claude-sonnet-5`), given the University's facts and live data: programmes, faculties, the current admission exercise and fee, news and events (`apps/website/knowledge.py`). It is told to answer only from those facts, never to guess fees or dates, not to ask for personal information, and to send personal questions to the portals.
- **Without a key** (or if the API is unreachable), a built-in assistant (`apps/website/chatbot.py`) answers the common questions from the same data, and points everything else to the contact details.
- The conversation stays in the visitor's browser tab; nothing is stored on the server. Visitors are limited to 60 messages an hour (`CHAT_RATE`).
- Keep the fixed facts in `apps/website/knowledge.py` (address, phone, emails, requirements, library hours) in step with `frontend/src/site/content.js`.

## Student records

- **Record.** A student is a login (`accounts.User`: name, email, phone, matric number as `university_id`) plus a `StudentProfile`: Student ID (`STU0000123`, permanent), programme (which fixes department and faculty), level, current session, admission details (entry session, mode of entry, admission date, JAMB number), personal and address details, next of kin, emergency contact and academic status.
- **Academic status:** Active, On probation, Suspended, Deferred, Withdrawn, Expelled, Completed (awaiting graduation) and Graduated. Every change needs a reason and an effective date, is kept in the status history (`students.StatusChange`), and the student is notified. Portal access (sign-in) is separate: the Registry can deactivate or restore it.
- **ID numbers are assigned automatically** (`apps/accounts/numbering.py`); nobody types them in, and they can't be edited. Students get a matric number `BU/<entry year>/<programme code>/<serial>` (e.g. `BU/26/CSC/0012`) and a permanent Student ID (`STU0000123`); their username is the matric number without slashes. Staff get `SP/1001`, `SP/1002`, … and admins `SA/0001`, …; applicants get `BU/APP/<session>/<serial>` and admission letters `BU/ADM/<session>/<serial>`. Numbers are assigned whenever a record is saved (the Students page, bulk upload, the users API or the Django admin), and if two records are saved at the same moment the second takes the next free number. A temporary password is shown once to the Registry (or included in the one-time download after an upload).
- **Validation.** Unique email, phone and JAMB number formats, sessions like `2026/2027` (current not before entry), levels that fit the programme's duration (plus two spill-over years), plausible dates of birth, and only programmes that are admitting students.
- **Import.** Download the template from **Students → Import** (CSV or Excel). Every row is checked (including duplicates within the file) before anything is saved; one bad row stops the whole import, with a list of problems by row. Up to 2,000 students at a time.
- **Access.** The Registry sees and manages everyone. HODs and Deans (`students.view`) see only students in their department or faculty and can't change records; fees are shown only to staff with `finance.view` or `students.manage`. Documents are served only to staff who can see that student.
- **Audit.** Creating, editing (with each changed field, old and new value), status changes, activation, password resets, photos, documents, imports and exports are all in the audit log, and each student's Activity History tab shows changes to their record, their own actions and their sign-ins.
- The Accommodation tab is a placeholder until a hostel module is added.

## Admissions

- **Admission exercise.** One `AdmissionCycle` is active at a time (e.g. 2026/2027): application fee, opening and closing dates, minimum UTME score, acceptance deadline and resumption date. Applications can only be started, paid for and submitted while it is open.
- **Workflow.** *Draft → Submitted → Under review → Screening → Approved → Admitted → Accepted*, with *Rejected* (from review, screening or the waiting list) and *Waitlisted* (from screening). The rules live in `apps/admissions/services.py`:
  - An application can only be submitted when every section is complete and the fee is paid. O-Level results need five credits including English Language and Mathematics from at most two sittings, and UTME applicants must meet the cut-off.
  - Verifying a document starts the review. Moving to screening needs every required document verified. A rejected document (with a reason) can be replaced by the applicant, even after submission; nothing else can change once submitted.
  - Approving or waitlisting needs a screening score; rejecting or waitlisting needs a reason, which the applicant sees. Approval can be for the first or second choice.
  - Issuing the admission letter (`BU/ADM/<session>/<number>`) moves an approved application to *Admitted*; the applicant downloads the PDF letter and accepts before the deadline.
- **Audit trail.** Every step is written to the application's timeline (`ApplicationEvent`; officers' internal notes are hidden from the applicant) and to the audit log, with who did it and when. Exports are audited too.
- **Application fee.** Paid through Paystack (references start `APP-`; the existing Paystack webhook handles both student fees and application fees). The amount and currency are checked, a second payment for the same application is flagged for refund, and a PDF receipt is issued.
- **Privacy.** Uploaded documents are stored under `MEDIA_ROOT/admissions/` with random names and served only to the applicant and the Admissions Office. Applicants can't see staff pages, the staff directory or university statistics.

## Attendance

- **Sessions.** A lecturer creates an attendance session for a class of a course they teach (date, time, optional topic, how long check-in stays open, and when check-ins count as late). Sessions go *scheduled → open for check-in → closed*. Check-in can only be started on the day of the class; a past class can be marked by hand and then closed.
- **QR and code check-in.** While a session is open, the lecturer's screen shows a QR code and a 6-digit code, both of which change every `ATTENDANCE_CODE_SECONDS` (20). Students scan it with **Attendance → Scan QR code** in the portal (an in-page camera scanner), or with their phone's own camera, which opens `/portal/attend` and checks them in. The code can be typed on the same page instead. The in-page camera needs HTTPS (or `localhost`). Codes are HMAC-signed per session, so they can't be guessed or reused for another class, and a code forwarded to someone outside the room stops working within about 40 seconds.
- **Safeguards against duplicate or proxy check-ins.** One record per student per session (enforced by the database), so scanning again just confirms the existing record, even if two scans arrive at once. Only registered students can check in, only during the check-in window. Each device keeps a random ID; if one phone checks in a second student for the same class, that record is **flagged** for the lecturer. Check-ins are rate-limited to 20 a minute per student.
- **Closing.** When the lecturer closes a session, every registered student without a record is marked absent and notified. Students who drop below `ATTENDANCE_MIN_PERCENT` (75) in that course are also emailed a warning.
- **Corrections.** Once a session is closed, records can't be edited directly. The lecturer requests a correction with a reason. The HOD of the course's department (or the Registrar) approves or rejects it, and the lecturer is notified. Nobody can approve their own request.
- **Bulk upload of paper registers.** On a course's attendance page, **Upload register** lets the lecturer download the class list as an Excel/CSV register (for a chosen date), fill in `P`, `L`, `E` or `A` (or the full words) for each student, and upload it. A file can cover several classes: one row per student per class, with `date`, `matric_number`, `status` and an optional `start_time` (otherwise the course's usual time). Every row is checked first (registered student, valid status and date within the semester and not in the future, no duplicates) and nothing is saved unless the whole file is valid; a preview shows each class's totals. Classes are matched to existing sessions or created, records are marked *Uploaded register*, and by default each class is closed so students not in the file are marked absent and notified. Classes that are already closed can't be changed by upload (so a register can't be entered twice); that needs a correction. Uploads are audited. Endpoints: `POST attendance/offerings/{id}/upload/` (multipart `file`, `dry_run`, `close`) and `GET attendance/offerings/{id}/upload-template/?file=xlsx|csv&date=YYYY-MM-DD`.
- **Percentage.** Present, late and excused count as attended. The percentage is attended ÷ closed sessions for the course.

## Paystack setup

1. Get your keys from the Paystack dashboard under **Settings → API Keys & Webhooks**. Use the **test** secret key (`sk_test_…`) until you are ready to go live.
2. Add the secret key to `backend/.env`, then restart Django:
   ```
   PAYSTACK_SECRET_KEY=sk_test_xxxxxxxxxxxxxxxxxxxx
   ```
3. In the same dashboard page, set the **Webhook URL** to `https://<your-domain>/api/finance/paystack/webhook/`. Paystack can only reach a public HTTPS address; for local testing, expose Django with a tunnel such as ngrok.
4. Make sure every student has an email address, since Paystack requires one.

How a payment works:

1. The student chooses an amount. The API checks it doesn't exceed their balance, creates a pending transaction, and calls Paystack's `transaction/initialize`.
2. The student is redirected to Paystack's hosted checkout to pay by card, bank transfer or USSD. Card details never pass through the portal.
3. Paystack sends them back to `/portal/fees/paystack/callback`. The API confirms the payment with `transaction/verify`, checks that the amount and currency (NGN) match, and records it with a receipt.
4. The webhook (`charge.success`, checked against its HMAC-SHA512 signature) records the payment even if the student closes the browser before the redirect. Each payment is recorded once, however many times the redirect or webhook arrives.

Every checkout is listed under **Finance → Gateway transactions** in the Django admin, including failed and abandoned ones.

**Every online payment goes through Paystack**: school fees and the admission application fee. There is no other online checkout, even in development. Students can't record payments themselves, and staff can't enter a payment as "Paystack": Paystack payments are created only when Paystack confirms them (on return from checkout or by webhook), after checking the amount and currency. The Bursary still records offline payments (cash, POS, bank deposit or transfer, scholarships) and approves uploaded proofs of payment. With no `PAYSTACK_SECRET_KEY`, online payment is switched off: students are told to pay at the bank and upload proof, and applicants can't pay until it's configured.

If the frontend is served from a different domain than the API, set `PAYSTACK_CALLBACK_URL` to `https://<frontend-domain>/portal/fees/paystack/callback`.

## Project layout

```
backend/
  config/                   settings, root URLs (incl. public /media/avatars/)
  apps/core/                notifications, audit log, SMS, shared test factories (testing.py)
  apps/accounts/            User, StudentProfile, StaffProfile, Role, RoleAssignment, LoginEvent
    rbac.py                 permission catalogue and default roles
    permissions.py          DRF permission classes: Requires("code"), ReadOnlyOrRequires, ...
    avatars.py              profile photo processing
  apps/academics/           Faculty, Department, Programme, Course, ProgrammeCourse, Semester,
                            CourseOffering, Enrollment (with CA/exam scores and result status)
    grading.py              NUC grading scale, GPA/CGPA, degree class, standing
    services.py             course registration rules and results
    dashboard.py            role-based dashboard
    management/commands/    seed_demo
  apps/campus/              Announcement (university / audience / department / course), Event
  apps/reports/            dashboard analytics (scoped to the viewer's faculty for Deans)
  apps/students/            student records management: StatusChange, StudentDocument
    services.py             access scope, create/update, matric numbers, status changes, audit
    importer.py             CSV/Excel import with row-by-row validation
  apps/admissions/          AdmissionCycle, Application, ApplicationDocument, ApplicationPayment, ApplicationEvent
    services.py             the workflow: completeness checks, transitions, notifications, timeline and audit log
    payments.py             application fee through Paystack
    documents.py            PDF admission letters and fee receipts
  apps/attendance/          AttendanceSession, AttendanceRecord, AttendanceCorrection
  apps/exams/               Venue, Exam, Candidate (seat, waiver, check-in), CBT Question/Choice/Attempt/Answer; exam cards
    services.py             rotating codes, check-in safeguards, marking, closing, corrections, statistics
  apps/finance/             FeeType, Charge, Payment, GatewayTransaction, PaymentProof
    services.py             fees, balances, record/void payments, proof review
    paystack.py             Paystack initialize / verify / webhook signature
    documents.py            PDF receipts and invoices
    notifications.py        payment emails
    views/                  accounts.py · payments.py · gateway.py · proofs.py
  apps/*/tests/             API tests
  pyproject.toml            ruff lint and format config (pip install -r requirements-dev.txt)
frontend/
  src/site/                 public website: SiteLayout, PortalLogin, pages/, content.js (editable text)
  src/api/client.js         Axios instance, JWT refresh, error formatting, file downloads
  src/auth/                 AuthProvider, useAuth(), access.js (can(user, "perm"), role helpers)
  src/components/           Layout, navigation.js (permission-driven sidebar), NotificationBell, UI kit
  src/pages/                one file per screen
  src/pages/finance/        fees, payments, receipts; proofs/ holds proof-of-payment components
  src/pages/students/       student list, create/edit form, import, profile page with tabs
  src/pages/admissions/     applicant home and application form; Admissions Office list and review
  src/pages/attendance/     student check-in and history, lecturer sessions and live QR, reports and corrections
  src/pages/exams/          student timetable and CBT, exam timetable and venues, exam detail, card verification
  src/pages/results/        result sheets: score entry and approvals
  src/utils/                useApi (race-safe data loading), useDebounced, formatting helpers
  src/index.css             design tokens and all styles
```

**Conventions:** views stay thin, and business rules live in each app's `services.py`. Serializers validate all input. Access checks use permission codes via `accounts/permissions.py`, never role names. Anything that emails or sends SMS runs after the database commit and never raises.

## API overview

All endpoints are under `/api/` and require `Authorization: Bearer <access token>`, except the token endpoints.

| Method | Endpoint | Who | Purpose |
|---|---|---|---|
| POST | `auth/token/`, `auth/token/refresh/` | anyone | Sign in (recorded in login history) / refresh a JWT |
| GET/PATCH | `auth/me/` | all | Own account, roles, permissions and student/staff record |
| GET/PATCH | `auth/me/student-profile/` | student | Own record; only contact, next-of-kin and emergency details are editable |
| POST/DELETE | `auth/me/avatar/` | all | Upload or remove profile photo |
| GET | `auth/me/logins/` | all | Own recent sign-ins |
| POST | `auth/change-password/` | all | Change password |
| CRUD | `users/` | `users.manage` | User management; `POST/DELETE users/{id}/avatar/` sets a staff member's official photo |
| GET/PATCH | `roles/` | `roles.manage` | Roles and their permissions |
| CRUD | `role-assignments/` | `roles.manage` | Appoint staff to roles |
| GET | `permissions/` | `roles.manage` | Permission catalogue |
| GET | `login-history/`, `audit-logs/` | `audit.view` | Security review |
| GET/POST | `notifications/`, `notifications/{id}/read/`, `notifications/read_all/`, `notifications/unread_count/` | all | Own notifications |
| GET | `directory/` | all | Staff directory |
| GET | `public/overview/`, `public/leadership/`, `public/faculties/`, `public/programmes/`, `public/programmes/{code}/`, `public/news/`, `public/news/{id}/`, `public/events/` | anyone | Public website data |
| POST | `public/contact/` | anyone (5 per hour per visitor) | Contact form |
| GET/POST | `public/chat/` | anyone (60 per hour) | Website chatbot: POST `{messages: [{role, content}]}` returns `{reply, suggestions, source}` |
| CRUD | `academics/faculties/`, `departments/`, `programmes/`, `semesters/`, `courses/`, `curriculum/`, `offerings/` | read: all; write: `academics.manage` | Academic structure. `POST courses/` also accepts `curriculum` and `offering` (created together). `offerings/?mine=true` = own courses |
| GET | `academics/lecturers/` | `academics.manage` | Staff who can teach, for offering forms |
| GET | `academics/offerings/{id}/roster/` | the lecturer; result officers | Class list with scores |
| GET/POST | `academics/registration/` | student | Registration overview; POST `{offering, action: add\|drop}` |
| GET | `academics/registration/history/` | student | Past registrations |
| GET | `academics/results/` | student | Published results, GPA, CGPA, standing |
| GET | `academics/dashboard/` | all | Role-specific home screen |
| CRUD | `campus/announcements/` | read: filtered by audience; write: faculty (own courses), admin | News |
| CRUD | `campus/events/` | read: all, write: admin | Events (`?upcoming=true`) |
| GET | `finance/account/` | student (own), admin (`?student=<id>`) | Statement: totals, charges with status, payments |
| GET/POST | `finance/payments/` | student: pay by card; admin: record any payment | Payment history, new payments |
| POST | `finance/payments/{id}/void/` | admin | Void a payment |
| CRUD | `finance/charges/` | read: own/all; write: admin (manual charges only) | Charges |
| CRUD | `finance/fee-types/` | read: all; write: admin | Mandatory fees per semester |
| GET | `finance/accounts/`, `finance/summary/` | admin | Balances for every student; collection totals |
| GET | `finance/payments/{id}/receipt/` | owner, admin | PDF receipt (`?inline=1` to open in the browser) |
| GET | `finance/invoice/?semester=<id>` | student (own), admin (`&student=<id>`) | PDF invoice for a semester |
| GET/POST/DELETE | `finance/payment-proofs/` | student: upload (multipart), list, withdraw pending; admin: list all | Proofs of offline payment |
| GET | `finance/payment-proofs/{id}/file/` | owner, admin | The uploaded document |
| POST | `finance/payment-proofs/{id}/approve/`, `reject/` | admin | Approve (optional `amount`, `note`) or reject (`reason`) |
| GET | `finance/payment-config/` | all | Which payment gateway is active (`paystack`, `demo`, or none) |
| POST | `finance/paystack/initialize/`, `verify/` | student | Start a Paystack checkout; confirm it on return |
| POST | `finance/paystack/webhook/` | Paystack (signed) | Payment notifications |
| GET/POST | `students/` | `students.view` (scoped) / `students.manage` | Students (search, filters, `?ordering=`, pagination); POST creates one and returns a temporary password |
| GET/PUT | `students/{id}/` | view / manage | A student's full record; PUT edits it |
| POST | `students/{id}/status/`, `activation/`, `reset-password/`, `photo/` | `students.manage` | Change status `{status, reason, effective_date}`, activate/deactivate `{active, reason}`, new temporary password, passport photo |
| GET | `students/{id}/academic-records/`, `courses/`, `attendance/`, `results/`, `fees/`, `documents/`, `activity/` | view (fees: `finance.view` or manage) | Profile tabs; POST `documents/` uploads one (manage) |
| GET/DELETE | `students/documents/{id}/` | view / manage | Download or remove a document |
| GET | `students/summary/`, `students/export/?file=csv\|xlsx`, `students/import-template/?file=csv\|xlsx` | view / manage | Counts by status and level, export, import template |
| POST | `students/import/` | `students.manage` | Multipart `file` (+ `dry_run=true` to check only) |
| GET | `admissions/cycle/` | anyone | The current admission exercise |
| POST | `admissions/register/` | anyone (10 per hour) | Create an applicant account; returns JWTs |
| GET/POST/PATCH | `admissions/me/` | applicant | Own application with checklist, documents, payments and timeline; POST starts it, PATCH edits a draft |
| POST/DELETE | `admissions/me/documents/`, `me/documents/{id}/` | applicant | Upload (multipart `kind`, `file`) or remove a document |
| POST | `admissions/me/pay/`, `me/pay/verify/`, `me/submit/`, `me/accept/` | applicant | Pay the fee, confirm a Paystack payment, submit, accept the offer |
| GET | `admissions/me/letter/`, `me/receipt/` | applicant | PDF admission letter, fee receipt |
| GET | `admissions/documents/{id}/file/` | owner, `admissions.manage` | An uploaded document |
| GET | `admissions/applications/`, `applications/summary/`, `applications/export/?file=csv\|xlsx` | `admissions.manage` | Applications (search, filters, ordering), counts by status, export |
| GET/POST | `admissions/applications/{id}/` and `start-review/`, `to-screening/`, `screening/`, `decide/`, `issue-letter/`, `note/`, `letter/` | `admissions.manage` | Review an application and move it through the workflow |
| POST | `admissions/documents/{id}/review/` | `admissions.manage` | `{verified, note}` |
| GET/POST/PATCH | `admissions/cycles/` | `admissions.manage` | Admission exercises |
| GET/POST/DELETE | `attendance/sessions/?offering=<id>` | the lecturer; `attendance.view` (read) | Sessions for a course; DELETE only before they start. Detail includes the class list with each student's record |
| POST | `attendance/sessions/{id}/open/`, `close/` | the lecturer | Start check-in; close (marks everyone else absent) |
| GET | `attendance/sessions/{id}/qr/` | the lecturer | Current QR code (SVG), 6-digit code, seconds until it changes, live count |
| POST | `attendance/sessions/{id}/mark/` | the lecturer | `{student, status}` before the session is closed |
| POST | `attendance/check-in/` | student (20 per minute) | `{session, token}` from the QR link, or `{code}`; plus `device_id` |
| GET | `attendance/me/` | student | Own attendance per course this semester, with history |
| GET | `attendance/offerings/{id}/stats/` | the lecturer; `attendance.view` | Per-student attendance for a course |
| POST | `attendance/records/{id}/correction/` | the lecturer | Request a correction to a closed session `{to_status, reason}` |
| GET/POST | `attendance/corrections/`, `corrections/{id}/decide/` | requester; `attendance.approve` | Correction queue; `{approve, note}` |
| GET | `academics/result-sheets/?status=mine` | lecturers and result reviewers | Courses whose results the user teaches or reviews, with the actions open to them |
| GET/PATCH | `academics/result-sheets/{offering}/` | the lecturer (PATCH); reviewers in scope | The result sheet; PATCH `{scores: [{enrollment, ca_score, exam_score}]}` while in draft |
| POST | `academics/result-sheets/{offering}/submit/`, `approve/`, `return/` | lecturer; HOD, Dean, `results.publish` | `{note}` (required to return). Approve moves to the next stage; the last one publishes |
| GET/POST/PATCH/DELETE | `exams/venues/` | read: members; write: `exams.manage` | Exam halls and CBT centres |
| GET/POST/PATCH/DELETE | `exams/timetable/?semester=<id>` | `exams.manage`; lecturers see their own (read) | Exams; DELETE drafts only |
| GET | `exams/timetable/problems/`, `unscheduled/` | `exams.manage` | Clashes and seating problems; offerings without an exam |
| POST | `exams/timetable/publish/`, `timetable/{id}/allocate-seats/`, `timetable/{id}/waive/` | `exams.manage` | Publish drafts `{semester, exams?}`; seat late registrants; `{student, waived, reason}` |
| GET | `exams/timetable/{id}/candidates/`, `attempts/` | `exams.manage`; the lecturer | Eligibility, seats and check-ins; CBT papers with scores and page-leave counts |
| GET/POST, PUT/DELETE | `exams/timetable/{id}/questions/`, `exams/questions/{id}/` | the lecturer | CBT questions (locked once the exam starts) |
| PATCH/POST | `exams/timetable/{id}/settings/`, `release-scores/` | the lecturer | Instructions and questions per candidate; copy CBT marks (scaled to 70) to the result sheet |
| GET | `exams/me/`, `exams/me/card/`, `exams/cards/{student}/` | student; `exams.manage` | Own timetable and eligibility; PDF exam card |
| POST, GET, PUT, POST | `exams/timetable/{id}/start/`, `exams/attempts/{id}/`, `answer/`, `event/`, `submit/` | student | Sit a CBT: start or resume, autosave `{question, choice}`, log leaving the page, submit |
| GET/POST | `exams/verify/?code=` or `?matric=`, `exams/verify/check-in/` | `exams.invigilate`, `exams.manage` | Check an exam card; admit `{exam, student}` on the day |
| GET | `attendance/reports/`, `reports/export/?file=csv\|xlsx` | `attendance.view` (scoped) | Report per student and course; filters `semester`, `faculty`, `department`, `offering`, `student`, `search`, `at_risk=true` |

Lists support `?search=`, `?ordering=`, and the filter fields declared on each view.

## Tests

```bash
cd backend
python manage.py test apps               # against PostgreSQL
USE_SQLITE=1 python manage.py test apps  # without a database server
ruff check .                             # lint (pip install -r requirements-dev.txt)

cd ../frontend
npm run lint                             # oxlint
npm run build
```

## Configuration

- Backend settings are read from `backend/.env`. See `backend/.env.example`.
- To use your university's name in the UI, set `VITE_UNIVERSITY_NAME` in `frontend/.env.local`.
- Attendance: `ATTENDANCE_CODE_SECONDS` (how often check-in codes change, default 20) and `ATTENDANCE_MIN_PERCENT` (default 75).
- Examinations: `EXAM_REQUIRE_FEES_CLEARED` (1: overdue fees block exams), `EXAM_ANSWER_GRACE_SECONDS` (10) and `EXAM_FOCUS_FLAG_AFTER` (3).
- For students to scan attendance QR codes from their phones, the portal must be reachable from the phones, and the host must be in `DJANGO_ALLOWED_HOSTS`. The QR link uses the address the lecturer opened the portal on, so open it by the university domain (or the machine's network address during testing), not `localhost`.

## Deploying to production

- Set `DJANGO_DEBUG=False`, a strong `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, and `CORS_ALLOWED_ORIGINS`. With DEBUG off, the settings turn on HTTPS redirects, secure cookies, and HSTS.
- Profile photos are stored in `MEDIA_ROOT/avatars/` and are public at `/media/avatars/…`, so they can be used in `<img>` tags. Uploads are checked to be real JPG, PNG or WebP images up to 5 MB, turned upright, cropped to a centred square, resized to 256×256 and re-saved as JPEG, which removes all metadata including phone GPS location. Django serves them, but for speed have your web server serve `/media/avatars/` directly. Serve **only** that folder publicly, never the whole of `MEDIA_ROOT`.
- Uploaded proofs are stored in `MEDIA_ROOT` (default `backend/media/`). Put it on persistent storage and back it up. Don't publish it as a public static folder; the API serves each file only to its owner and admins.
- Serve Django with gunicorn or uvicorn behind a reverse proxy, and run `collectstatic`.
- Build the frontend with `npm run build` and serve `frontend/dist/` as static files, routing unknown paths to `index.html`. If the API is on a different origin, set `VITE_API_URL`.
- The demo account buttons on the login page only appear in development builds.

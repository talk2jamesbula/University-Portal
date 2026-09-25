"""Populate the database with a demo Nigerian university.

    python manage.py seed_demo          # add demo data (refuses if data exists)
    python manage.py seed_demo --flush  # wipe portal data first

Every demo account uses the password below.
"""

import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.academics.grading import CA_MAX, EXAM_MAX
from apps.academics.models import (
    Course,
    CourseOffering,
    Department,
    Enrollment,
    Faculty,
    Programme,
    ProgrammeCourse,
    Semester,
)
from apps.academics.services import register_course
from apps.accounts.models import Role, RoleAssignment, StaffProfile, StudentProfile
from apps.admissions import services as admission_services
from apps.admissions.models import (
    AdmissionCycle,
    Application,
    ApplicationDocument,
    ApplicationEvent,
    ApplicationPayment,
)
from apps.attendance.models import AttendanceCorrection, AttendanceRecord, AttendanceSession
from apps.campus.models import Announcement, Event
from apps.core.models import AuditLog, Notification
from apps.finance.models import Charge, FeeType, GatewayTransaction, Payment, PaymentProof
from apps.finance.services import account_summary, assess_semester_fees
from apps.students.models import StatusChange, StudentDocument

User = get_user_model()
DEMO_PASSWORD = "Portal@2026"
DEMO_EMAIL_DOMAIN = "bulacode.edu.ng"

FACULTIES = [
    ("FSC", "Faculty of Science"),
    ("FET", "Faculty of Engineering & Technology"),
    ("FMS", "Faculty of Management Sciences"),
    ("FAR", "Faculty of Arts"),
]
DEPARTMENTS = [  # code, name, faculty
    ("CSC", "Computer Science", "FSC"),
    ("MTH", "Mathematics", "FSC"),
    ("MCB", "Microbiology", "FSC"),
    ("EEE", "Electrical & Electronic Engineering", "FET"),
    ("ACC", "Accounting", "FMS"),
    ("BUS", "Business Administration", "FMS"),
    ("ENG", "English & Literary Studies", "FAR"),
]
PROGRAMMES = [  # code, name, degree, department, years
    ("CSC", "Computer Science", "B.Sc.", "CSC", 4),
    ("MTH", "Mathematics", "B.Sc.", "MTH", 4),
    ("MCB", "Microbiology", "B.Sc.", "MCB", 4),
    ("EEE", "Electrical & Electronic Engineering", "B.Eng.", "EEE", 5),
    ("ACC", "Accounting", "B.Sc.", "ACC", 4),
    ("BUS", "Business Administration", "B.Sc.", "BUS", 4),
    ("ENG", "English & Literary Studies", "B.A.", "ENG", 4),
]

# code, title, units, level, semester, department
COURSES = [
    # General studies (every programme)
    ("GST111", "Communication in English", 2, 100, 1, "ENG"),
    ("GST112", "Nigerian Peoples and Culture", 2, 100, 2, "ENG"),
    ("GST211", "Philosophy, Logic and Human Existence", 2, 200, 1, "ENG"),
    ("GST212", "Entrepreneurship and Innovation", 2, 200, 2, "BUS"),
    # Sciences
    ("MTH101", "Elementary Mathematics I", 3, 100, 1, "MTH"),
    ("MTH102", "Elementary Mathematics II", 3, 100, 2, "MTH"),
    ("PHY101", "General Physics I", 3, 100, 1, "EEE"),
    ("PHY102", "General Physics II", 3, 100, 2, "EEE"),
    ("CHM101", "General Chemistry I", 3, 100, 1, "MCB"),
    ("CHM102", "General Chemistry II", 3, 100, 2, "MCB"),
    ("BIO101", "General Biology I", 3, 100, 1, "MCB"),
    ("BIO102", "General Biology II", 3, 100, 2, "MCB"),
    ("CSC101", "Introduction to Computer Science", 3, 100, 1, "CSC"),
    ("CSC102", "Introduction to Problem Solving", 3, 100, 2, "CSC"),
    ("CSC201", "Computer Programming I", 3, 200, 1, "CSC"),
    ("CSC202", "Computer Programming II", 3, 200, 2, "CSC"),
    ("CSC203", "Discrete Structures", 3, 200, 1, "CSC"),
    ("CSC204", "Data Structures", 3, 200, 2, "CSC"),
    ("CSC205", "Introduction to Web Technologies", 2, 200, 1, "CSC"),
    ("CSC206", "Operating Systems I", 3, 200, 2, "CSC"),
    ("CSC301", "Algorithms and Complexity", 3, 300, 1, "CSC"),
    ("CSC303", "Database Design and Management", 3, 300, 1, "CSC"),
    ("CSC305", "Software Engineering", 3, 300, 1, "CSC"),
    ("CSC307", "Computer Architecture", 3, 300, 1, "CSC"),
    ("CSC309", "Artificial Intelligence", 3, 300, 1, "CSC"),
    ("MTH201", "Mathematical Methods I", 3, 200, 1, "MTH"),
    ("MTH202", "Mathematical Methods II", 3, 200, 2, "MTH"),
    ("MTH203", "Linear Algebra I", 3, 200, 1, "MTH"),
    ("MTH204", "Linear Algebra II", 3, 200, 2, "MTH"),
    ("MTH205", "Real Analysis I", 3, 200, 1, "MTH"),
    ("STA201", "Statistics for Physical Sciences", 3, 200, 1, "MTH"),
    ("STA202", "Probability Distributions", 3, 200, 2, "MTH"),
    ("MTH301", "Abstract Algebra I", 3, 300, 1, "MTH"),
    ("MTH303", "Complex Analysis I", 3, 300, 1, "MTH"),
    ("MTH305", "Numerical Analysis", 3, 300, 1, "MTH"),
    ("MCB201", "General Microbiology", 3, 200, 1, "MCB"),
    ("MCB202", "Microbial Physiology", 3, 200, 2, "MCB"),
    ("MCB203", "Introductory Virology", 3, 200, 1, "MCB"),
    ("MCB204", "Microbial Ecology", 3, 200, 2, "MCB"),
    ("MCB205", "Biochemistry for Microbiologists", 3, 200, 1, "MCB"),
    ("MCB301", "Immunology", 3, 300, 1, "MCB"),
    ("MCB303", "Industrial Microbiology", 3, 300, 1, "MCB"),
    ("MCB305", "Food Microbiology", 3, 300, 1, "MCB"),
    ("EEE201", "Circuit Theory I", 3, 200, 1, "EEE"),
    ("EEE202", "Circuit Theory II", 3, 200, 2, "EEE"),
    ("EEE203", "Engineering Drawing", 2, 200, 1, "EEE"),
    ("EEE204", "Electrical Machines I", 3, 200, 2, "EEE"),
    ("EEE205", "Applied Electricity", 3, 200, 1, "EEE"),
    ("EEE301", "Electromagnetic Fields", 3, 300, 1, "EEE"),
    ("EEE303", "Analogue Electronics", 3, 300, 1, "EEE"),
    ("EEE305", "Signals and Systems", 3, 300, 1, "EEE"),
    # Management sciences
    ("ACC101", "Principles of Accounting I", 3, 100, 1, "ACC"),
    ("ACC102", "Principles of Accounting II", 3, 100, 2, "ACC"),
    ("BUS101", "Introduction to Business", 3, 100, 1, "BUS"),
    ("BUS102", "Introduction to Management", 3, 100, 2, "BUS"),
    ("ECO101", "Principles of Economics I", 3, 100, 1, "BUS"),
    ("ECO102", "Principles of Economics II", 3, 100, 2, "BUS"),
    ("ACC201", "Financial Accounting I", 3, 200, 1, "ACC"),
    ("ACC202", "Financial Accounting II", 3, 200, 2, "ACC"),
    ("ACC203", "Cost Accounting", 3, 200, 1, "ACC"),
    ("ACC204", "Management Accounting", 3, 200, 2, "ACC"),
    ("BUS201", "Organisational Behaviour", 3, 200, 1, "BUS"),
    ("BUS202", "Business Law", 3, 200, 2, "BUS"),
    ("BUS203", "Principles of Marketing", 3, 200, 1, "BUS"),
    ("BUS204", "Human Resource Management", 3, 200, 2, "BUS"),
    ("ACC301", "Advanced Financial Reporting", 3, 300, 1, "ACC"),
    ("ACC303", "Auditing and Assurance", 3, 300, 1, "ACC"),
    ("ACC305", "Taxation I", 3, 300, 1, "ACC"),
    ("BUS301", "Strategic Management", 3, 300, 1, "BUS"),
    ("BUS303", "Operations Management", 3, 300, 1, "BUS"),
    ("BUS305", "Business Research Methods", 3, 300, 1, "BUS"),
    # Arts
    ("ENG101", "Introduction to Literature", 3, 100, 1, "ENG"),
    ("ENG102", "Introduction to Linguistics", 3, 100, 2, "ENG"),
    ("ENG103", "Nigerian Literature in English", 3, 100, 1, "ENG"),
    ("ENG104", "Creative Writing", 3, 100, 2, "ENG"),
    ("ENG201", "The African Novel", 3, 200, 1, "ENG"),
    ("ENG202", "English Phonology", 3, 200, 2, "ENG"),
    ("ENG203", "Poetry and Poetics", 3, 200, 1, "ENG"),
    ("ENG204", "English Syntax", 3, 200, 2, "ENG"),
    ("ENG205", "Drama in Performance", 3, 200, 1, "ENG"),
    ("ENG301", "Literary Theory", 3, 300, 1, "ENG"),
    ("ENG303", "Sociolinguistics", 3, 300, 1, "ENG"),
    ("ENG305", "Postcolonial Literature", 3, 300, 1, "ENG"),
]

# Programme curricula: {programme: [(course code, compulsory)]}. General studies are added to all.
GENERAL = [("GST111", True), ("GST112", True), ("GST211", True), ("GST212", True)]
SCIENCE_YEAR_ONE = [(c, True) for c in ("MTH101", "MTH102", "PHY101", "PHY102", "CHM101", "CHM102")]
CURRICULA = {
    "CSC": SCIENCE_YEAR_ONE
    + [
        (c, True)
        for c in (
            "CSC101",
            "CSC102",
            "CSC201",
            "CSC202",
            "CSC203",
            "CSC204",
            "CSC206",
            "MTH201",
            "MTH202",
            "CSC301",
            "CSC303",
            "CSC305",
            "CSC307",
        )
    ]
    + [("CSC205", False), ("STA201", False), ("STA202", False), ("CSC309", False)],
    "MTH": SCIENCE_YEAR_ONE
    + [
        (c, True)
        for c in (
            "MTH201",
            "MTH202",
            "MTH203",
            "MTH204",
            "MTH205",
            "STA201",
            "STA202",
            "MTH301",
            "MTH303",
            "MTH305",
        )
    ]
    + [("CSC101", False), ("CSC201", False)],
    "MCB": SCIENCE_YEAR_ONE
    + [("BIO101", True), ("BIO102", True)]
    + [
        (c, True)
        for c in (
            "MCB201",
            "MCB202",
            "MCB203",
            "MCB204",
            "MCB205",
            "MCB301",
            "MCB303",
            "MCB305",
        )
    ]
    + [("STA201", False)],
    "EEE": SCIENCE_YEAR_ONE
    + [
        (c, True)
        for c in (
            "EEE201",
            "EEE202",
            "EEE203",
            "EEE204",
            "EEE205",
            "MTH201",
            "MTH202",
            "EEE301",
            "EEE303",
            "EEE305",
        )
    ]
    + [("CSC201", False)],
    "ACC": [
        (c, True)
        for c in (
            "ACC101",
            "ACC102",
            "ECO101",
            "ECO102",
            "BUS101",
            "BUS102",
            "MTH101",
            "ACC201",
            "ACC202",
            "ACC203",
            "ACC204",
            "BUS201",
            "ACC301",
            "ACC303",
            "ACC305",
        )
    ]
    + [("BUS203", False), ("BUS202", False), ("BUS305", False)],
    "BUS": [
        (c, True)
        for c in (
            "BUS101",
            "BUS102",
            "ECO101",
            "ECO102",
            "ACC101",
            "ACC102",
            "MTH101",
            "BUS201",
            "BUS202",
            "BUS203",
            "BUS204",
            "ACC201",
            "BUS301",
            "BUS303",
            "BUS305",
        )
    ]
    + [("ACC203", False), ("ACC204", False)],
    "ENG": [
        (c, True)
        for c in (
            "ENG101",
            "ENG102",
            "ENG103",
            "ENG104",
            "ENG201",
            "ENG202",
            "ENG203",
            "ENG204",
            "ENG301",
            "ENG303",
            "ENG305",
        )
    ]
    + [("ENG205", False), ("BUS203", False)],
}

# username, title, first, last, department, designation, roles [(role, scope)]
STAFF = [
    ("registrar", "Mrs.", "Folasade", "Adeyemi", None, "Registrar", [("registrar", None)]),
    ("bursar", "Mr.", "Emeka", "Nwankwo", None, "Bursar", [("bursar", None)]),
    ("vc", "Prof.", "Aminu", "Bello", None, "Vice Chancellor", [("vc", None)]),
    (
        "examofficer",
        "Dr.",
        "Hauwa",
        "Musa",
        "MTH",
        "Examinations Officer",
        [("exam_officer", None), ("lecturer", None)],
    ),
    ("lecturer", "Dr.", "Adaeze", "Okonkwo", "CSC", "Senior Lecturer", [("lecturer", None)]),
    ("hod", "Prof.", "Babatunde", "Ogunleye", "CSC", "Professor", [("hod", "CSC"), ("lecturer", None)]),
    ("dean", "Prof.", "Ngozi", "Eze", "MCB", "Professor", [("dean", "FSC"), ("lecturer", None)]),
    ("iabubakar", "Dr.", "Ibrahim", "Abubakar", "EEE", "Senior Lecturer", [("lecturer", None), ("hod", "EEE")]),
    ("tolawale", "Mr.", "Tunde", "Olawale", "CSC", "Lecturer I", [("lecturer", None)]),
    ("cobi", "Dr.", "Chiamaka", "Obi", "MTH", "Lecturer I", [("lecturer", None), ("hod", "MTH")]),
    ("kadamu", "Dr.", "Kemi", "Adamu", "MCB", "Lecturer I", [("lecturer", None), ("hod", "MCB")]),
    ("sibrahim", "Dr.", "Suleiman", "Ibrahim", "ACC", "Senior Lecturer", [("lecturer", None), ("hod", "ACC")]),
    ("fokafor", "Mrs.", "Funmilayo", "Okafor", "BUS", "Lecturer II", [("lecturer", None), ("hod", "BUS")]),
    ("aeze", "Dr.", "Adanna", "Eze", "ENG", "Senior Lecturer", [("lecturer", None), ("hod", "ENG")]),
    ("finance1", "Mr.", "Yusuf", "Danjuma", None, "Finance Officer", [("finance_officer", None)]),
    ("admissions1", "Ms.", "Grace", "Etim", None, "Admissions Officer", [("admission_officer", None)]),
]

FIRST_NAMES = [
    "Chinedu",
    "Amaka",
    "Tunde",
    "Ifeoma",
    "Yusuf",
    "Zainab",
    "Emeka",
    "Funke",
    "Ibrahim",
    "Ngozi",
    "Segun",
    "Aisha",
    "Obinna",
    "Temitope",
    "Musa",
    "Chioma",
    "Kelechi",
    "Halima",
    "Damilola",
    "Uche",
    "Bola",
    "Fatima",
    "Ikenna",
    "Blessing",
    "Abdullahi",
    "Nneka",
    "Gbenga",
    "Rukayat",
]
LAST_NAMES = [
    "Okafor",
    "Adeyemi",
    "Bello",
    "Nwosu",
    "Abdullahi",
    "Eze",
    "Ogunleye",
    "Musa",
    "Okonkwo",
    "Ibrahim",
    "Afolabi",
    "Umeh",
    "Salisu",
    "Oyelaran",
    "Chukwu",
    "Danladi",
    "Akande",
    "Obi",
]
STATES = ["Lagos", "Enugu", "Kano", "Oyo", "Anambra", "Kaduna", "Rivers", "Ogun", "Imo", "Kwara", "Delta", "Plateau"]

FEES = [  # name, amount, description
    ("Development levy", 25000, "Infrastructure and maintenance"),
    ("ICT and e-learning fee", 15000, "Portal, campus network and software"),
    ("Medical fee", 10000, "University health centre"),
    ("Library fee", 5000, "Library services and e-resources"),
    ("Sports fee", 5000, "Sports facilities"),
    ("Student union dues", 2000, "Student Union Government"),
]
TUITION_PER_UNIT = Decimal("15000")
VENUES = [
    "LT 1",
    "LT 2",
    "LT 3",
    "Science Auditorium",
    "CSC Lab 2",
    "Engineering Hall",
    "Management Sciences LT",
    "Arts Theatre",
    "Room 204",
    "Room 108",
]
# Weekly lecture slots that never overlap one another: (days, start hour), each two hours long.
SLOTS = [(days, hour) for days in ("MON,WED", "TUE,THU", "FRI") for hour in (8, 10, 12, 14, 16)]
# Courses taken by students of several programmes; they get timetable slots of their own.
SHARED_PREFIXES = ("GST", "MTH", "STA", "PHY", "CHM", "BIO", "ECO")


class Command(BaseCommand):
    help = "Seed the database with a demo Nigerian university."

    def add_arguments(self, parser):
        parser.add_argument("--flush", action="store_true", help="Delete existing portal data first.")

    @transaction.atomic
    def handle(self, *args, flush=False, **options):
        self.rng = random.Random(2026)
        if flush:
            self.flush()
        if Faculty.objects.exists():
            self.stdout.write(self.style.WARNING("Demo data already present; use --flush to reseed."))
            return

        self.create_structure()
        self.create_semesters()
        self.create_staff()
        self.create_offerings()
        self.create_students()
        self.create_history()
        self.create_current_registrations()
        self.create_status_history()
        self.create_finance()
        self.create_attendance()
        call_command("seed_exams", stdout=self.stdout)
        self.create_admissions()
        self.create_news()

        owing = sum(1 for s in self.students if account_summary(s)["balance"] > 0)
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(self.students)} students, {len(self.staff)} staff, {Course.objects.count()} courses, "
                f"{CourseOffering.objects.count()} offerings; {owing} students owe fees. "
                f"Password for all demo users: {DEMO_PASSWORD}"
            )
        )

    # --- Reset ----------------------------------------------------------------------------------

    def flush(self):
        for document in StudentDocument.objects.all():
            document.file.storage.delete(document.file.name)
        for document in ApplicationDocument.objects.all():
            document.file.storage.delete(document.file.name)
        for model in (
            ApplicationEvent,
            ApplicationPayment,
            ApplicationDocument,
            Application,
            AdmissionCycle,
            AttendanceCorrection,
            AttendanceRecord,
            AttendanceSession,
            Notification,
            AuditLog,
            Announcement,
            Event,
            PaymentProof,
            GatewayTransaction,
            Payment,
            Charge,
            FeeType,
            Enrollment,
            CourseOffering,
            ProgrammeCourse,
        ):
            model.objects.all().delete()
        # Keep superusers created by hand; remove every account the seed created.
        User.objects.filter(Q(is_superuser=False) | Q(email__endswith=f"@{DEMO_EMAIL_DOMAIN}")).delete()
        for model in (Course, Semester, Programme, Department, Faculty):
            model.objects.all().delete()

    # --- Builders -------------------------------------------------------------------------------

    def make_user(self, username, first, last, role, **extra):
        user = User(
            username=username,
            first_name=first,
            last_name=last,
            role=role,
            email=f"{username.replace('/', '').lower()}@{DEMO_EMAIL_DOMAIN}",
            **extra,
        )
        user.set_password(DEMO_PASSWORD)
        user.save()
        return user

    def create_structure(self):
        self.faculties = {code: Faculty.objects.create(code=code, name=name) for code, name in FACULTIES}
        self.departments = {
            code: Department.objects.create(code=code, name=name, faculty=self.faculties[fac])
            for code, name, fac in DEPARTMENTS
        }
        self.programmes = {
            code: Programme.objects.create(
                code=code,
                name=name,
                degree=degree,
                department=self.departments[dept],
                duration_years=years,
                description=f"{degree} {name}, a {years}-year programme of the "
                f"Department of {self.departments[dept].name}.",
            )
            for code, name, degree, dept, years in PROGRAMMES
        }
        self.courses = {
            code: Course.objects.create(
                code=code,
                title=title,
                units=units,
                level=level,
                semester_number=sem,
                department=self.departments[dept],
                description=f"{title}. A {units}-unit {level}-level course.",
            )
            for code, title, units, level, sem, dept in COURSES
        }
        for programme, entries in CURRICULA.items():
            for code, compulsory in GENERAL + entries:
                ProgrammeCourse.objects.create(
                    programme=self.programmes[programme], course=self.courses[code], is_compulsory=compulsory
                )

    def create_semesters(self):
        def semester(session, number, start, end, **kw):
            return Semester.objects.create(
                session=session,
                number=number,
                start_date=start,
                end_date=end,
                tuition_per_unit=TUITION_PER_UNIT,
                **kw,
            )

        self.past_first = semester(
            "2025/2026",
            1,
            date(2025, 9, 8),
            date(2026, 1, 30),
            registration_open=False,
            fee_due_date=date(2025, 10, 10),
        )
        self.past_second = semester(
            "2025/2026",
            2,
            date(2026, 2, 16),
            date(2026, 7, 10),
            registration_open=False,
            fee_due_date=date(2026, 3, 13),
        )
        self.current = semester(
            "2026/2027",
            1,
            date(2026, 9, 7),
            date(2027, 1, 29),
            is_current=True,
            registration_open=True,
            fee_due_date=date(2026, 10, 16),
        )

    def create_staff(self):
        self.admin = self.make_user(
            "admin",
            "System",
            "Administrator",
            User.Role.ADMIN,
            university_id="SA/0001",
            is_staff=True,
            is_superuser=True,
        )
        roles = {r.code: r for r in Role.objects.all()}
        self.staff, self.lecturers = [], {}
        for i, (username, title, first, last, dept, designation, appointments) in enumerate(STAFF, start=1):
            user = self.make_user(
                username,
                first,
                last,
                User.Role.STAFF,
                title=title,
                university_id=f"SP/{1000 + i}",
                department=self.departments.get(dept),
                phone=f"0803{self.rng.randint(1000000, 9999999)}",
                is_staff=username == "registrar",
            )
            academic = any(code == "lecturer" for code, _ in appointments)
            StaffProfile.objects.create(
                user=user,
                designation=designation,
                category=StaffProfile.Category.ACADEMIC if academic else StaffProfile.Category.NON_ACADEMIC,
                office=f"{self.departments[dept].name} Dept." if dept else "Senate Building",
            )
            for code, scope in appointments:
                RoleAssignment.objects.create(
                    user=user,
                    role=roles[code],
                    faculty=self.faculties.get(scope) if roles[code].scope == "faculty" else None,
                    department=self.departments.get(scope) if roles[code].scope == "department" else None,
                )
            self.staff.append(user)
            if academic and dept:
                self.lecturers.setdefault(dept, []).append(user)

    def create_offerings(self):
        """Offer every course in its semester, with a clash-free timetable for each programme."""
        self.offerings = {}
        for semester in (self.past_first, self.past_second, self.current):
            courses = [c for c in self.courses.values() if c.semester_number == semester.number]
            for level in sorted({c.level for c in courses}):
                for course, (days, hour) in self.timetable([c for c in courses if c.level == level]):
                    lecturers = self.lecturers.get(course.department.code) or self.lecturers["CSC"]
                    self.offerings[(semester.pk, course.code)] = CourseOffering.objects.create(
                        course=course,
                        semester=semester,
                        lecturer=self.rng.choice(lecturers),
                        capacity=150,
                        days=days,
                        start_time=time(hour),
                        end_time=time(hour + 2),
                        venue=self.rng.choice(VENUES),
                    )

    @staticmethod
    def timetable(courses):
        """Slots for one level's courses: shared courses get their own slots; a department's
        courses never share a slot with each other (different programmes may share)."""
        shared = sorted((c for c in courses if c.code.startswith(SHARED_PREFIXES)), key=lambda c: c.code)
        own = sorted((c for c in courses if c not in shared), key=lambda c: (c.department.code, c.code))
        plan = list(zip(shared, SLOTS, strict=False))
        free = SLOTS[len(shared) :]
        departments = sorted({c.department.code for c in own})
        for course in own:
            same_dept = [c for c in own if c.department.code == course.department.code]
            index = departments.index(course.department.code) * 3 + same_dept.index(course)
            plan.append((course, free[index % len(free)]))
        return plan

    def create_students(self):
        self.students, used = [], set()
        plan = [
            ("CSC", 100, 3),
            ("CSC", 200, 5),
            ("CSC", 300, 4),
            ("MTH", 200, 3),
            ("MCB", 200, 3),
            ("EEE", 300, 3),
            ("ACC", 200, 4),
            ("BUS", 300, 3),
            ("ENG", 200, 3),
            ("ACC", 100, 2),
        ]
        serial = 0
        for programme_code, level, count in plan:
            for _ in range(count):
                serial += 1
                is_demo = serial == 4  # a 200-level Computer Science student with history
                first, last = ("Chinedu", "Okafor") if is_demo else self.unique_name(used)
                entry_year = 2026 - level // 100 + 1
                matric = f"BU/{entry_year % 100:02d}/{programme_code}/{serial:04d}"
                user = self.make_user(
                    "student" if is_demo else matric.replace("/", "").lower(),
                    first,
                    last,
                    User.Role.STUDENT,
                    university_id=matric,
                    department=self.programmes[programme_code].department,
                    phone=f"0806{self.rng.randint(1000000, 9999999)}",
                )
                StudentProfile.objects.create(
                    user=user,
                    programme=self.programmes[programme_code],
                    level=level,
                    entry_session=f"{entry_year}/{entry_year + 1}",
                    current_session="2026/2027",
                    admission_date=date(entry_year, 10, 12),
                    jamb_reg_number=f"{entry_year}{serial * 7919 % 10000:04d}"
                    f"{chr(65 + serial % 26)}{chr(75 + serial % 10)}",
                    gender=self.rng.choice(StudentProfile.Gender.values),
                    date_of_birth=date(2008 - level // 100, self.rng.randint(1, 12), self.rng.randint(1, 28)),
                    state_of_origin=self.rng.choice(STATES),
                    home_address=(
                        f"{self.rng.randint(2, 90)} {self.rng.choice(LAST_NAMES)} Street, {self.rng.choice(STATES)}"
                    ),
                    next_of_kin_name=f"{self.rng.choice(['Mr.', 'Mrs.'])} {self.rng.choice(FIRST_NAMES)} {last}",
                    next_of_kin_relationship=self.rng.choice(["Father", "Mother", "Guardian"]),
                    next_of_kin_phone=f"0802{self.rng.randint(1000000, 9999999)}",
                    emergency_contact_name=f"{self.rng.choice(FIRST_NAMES)} {last}",
                    emergency_contact_relationship=self.rng.choice(["Sibling", "Uncle", "Aunt"]),
                    emergency_contact_phone=f"0809{self.rng.randint(1000000, 9999999)}",
                )
                self.students.append(user)
        self.demo_student = User.objects.get(username="student")

    def unique_name(self, used):
        while True:
            name = (self.rng.choice(FIRST_NAMES), self.rng.choice(LAST_NAMES))
            if name not in used and name != ("Chinedu", "Okafor"):
                used.add(name)
                return name

    def score(self, strong):
        """(CA, exam) giving a realistic spread; `strong` students rarely fail."""
        total = min(95, max(18, self.rng.gauss(64 if strong else 52, 12)))
        ca = round(min(CA_MAX, total * self.rng.uniform(0.26, 0.34)), 1)
        return Decimal(str(ca)), Decimal(str(round(min(EXAM_MAX, max(0, total - ca)), 1)))

    def curriculum(self, programme, level, number):
        return list(
            ProgrammeCourse.objects.filter(
                programme=programme, course__level=level, course__semester_number=number
            ).select_related("course")
        )

    def create_history(self):
        """Published results for last session, taken at each student's previous level."""
        for student in self.students:
            profile = student.student_profile
            if profile.level == 100:
                continue
            strong = self.rng.random() < 0.6 or student == self.demo_student
            for semester in (self.past_first, self.past_second):
                for pc in self.curriculum(profile.programme, profile.level - 100, semester.number):
                    if not pc.is_compulsory and self.rng.random() < 0.5:
                        continue
                    ca, exam = self.score(strong)
                    if student == self.demo_student and pc.course.code == "MTH101":
                        ca, exam = Decimal("11.0"), Decimal("24.0")  # a carry-over to show off
                    Enrollment.objects.create(
                        student=student,
                        offering=self.offerings[(semester.pk, pc.course.code)],
                        ca_score=ca,
                        exam_score=exam,
                        result_status=Enrollment.ResultStatus.PUBLISHED,
                    )

    def create_status_history(self):
        """A few 100-level students whose status has changed, recorded as the Registry would."""
        registrar = User.objects.get(username="registrar")
        freshers = [s for s in self.students if s.student_profile.level == 100 and s != self.demo_student]
        changes = [
            (
                freshers[0],
                StudentProfile.Status.SUSPENDED,
                "Suspended for one semester by the Student Disciplinary Committee.",
            ),
            (
                freshers[-2],
                StudentProfile.Status.DEFERRED,
                "Deferred admission on medical grounds (approved by Senate).",
            ),
            (freshers[-1], StudentProfile.Status.WITHDRAWN, "Voluntary withdrawal at the student's request."),
        ]
        for i, (student, status, reason) in enumerate(changes):
            when = timezone.make_aware(datetime.combine(date(2026, 9, 10 + i * 3), time(11)))
            change = StatusChange.objects.create(
                student=student,
                from_status=StudentProfile.Status.ACTIVE,
                to_status=status,
                reason=reason,
                effective_date=when.date(),
                changed_by=registrar,
            )
            StatusChange.objects.filter(pk=change.pk).update(created_at=when)
            StudentProfile.objects.filter(user=student).update(status=status)
            log = AuditLog.objects.create(
                actor=registrar,
                action="students.status",
                target_type="accounts.user",
                target_id=str(student.pk),
                summary=f"{student.university_id}: Active → {StudentProfile.Status(status).label}. {reason}"[:255],
            )
            AuditLog.objects.filter(pk=log.pk).update(created_at=when)
            if status == StudentProfile.Status.WITHDRAWN:
                User.objects.filter(pk=student.pk).update(is_active=False)

    def create_current_registrations(self):
        """Most continuing students have registered this semester's compulsory courses; freshers haven't."""
        for student in self.students:
            profile = student.student_profile
            if profile.level == 100 or (student != self.demo_student and self.rng.random() < 0.15):
                continue
            for pc in self.curriculum(profile.programme, profile.level, self.current.number):
                if pc.is_compulsory or self.rng.random() < 0.4:
                    try:
                        register_course(student, self.offerings[(self.current.pk, pc.course.code)])
                    except Exception:  # timetable clash or unit limit: skip, as a student would
                        continue

    def create_finance(self):
        for name, amount, desc in FEES:
            FeeType.objects.create(name=name, amount=amount, description=desc)
        for student in self.students:
            for semester in (self.past_first, self.past_second, self.current):
                assess_semester_fees(student, semester)

        def pay(student, amount, when, method=Payment.Method.PAYSTACK, reference=None):
            Payment.objects.create(
                student=student,
                amount=amount,
                method=method,
                reference=reference or f"BU-{when:%Y%m%d}-{self.rng.randint(100000, 999999)}",
                note="Paid via card" if method == Payment.Method.PAYSTACK else "",
                card_last4=f"{self.rng.randint(0, 9999):04d}" if method == Payment.Method.PAYSTACK else "",
                paid_at=timezone.make_aware(datetime.combine(when, time(self.rng.randint(8, 18), 30))),
            )

        def paid_during(start, days):
            return start + timedelta(days=self.rng.randint(0, days))

        for i, student in enumerate(self.students):
            charges = Charge.objects.filter(student=student).exclude(semester=self.current)
            first = sum(c.amount for c in charges.filter(semester=self.past_first))
            rest = sum(c.amount for c in charges.exclude(semester=self.past_first))
            # Students pay over the weeks after each semester's bills: some at once, some in two instalments.
            if first:
                if i % 3 == 0:
                    half = (first / 2).quantize(Decimal("1"))
                    pay(student, half, paid_during(date(2025, 10, 6), 20))
                    pay(student, first - half, paid_during(date(2025, 11, 17), 30))
                else:
                    pay(student, first, paid_during(date(2025, 10, 6), 45))
            if rest:
                if i % 11 == 7:  # a few still owe from last session (overdue)
                    pay(student, (rest * Decimal("0.7")).quantize(Decimal("1")), paid_during(date(2026, 3, 2), 60))
                elif i % 3 == 1:
                    half = (rest / 2).quantize(Decimal("1"))
                    pay(student, half, paid_during(date(2026, 2, 9), 20))
                    pay(student, rest - half, paid_during(date(2026, 4, 6), 45))
                else:
                    pay(student, rest, paid_during(date(2026, 2, 9), 50))
            current = sum(c.amount for c in Charge.objects.filter(student=student, semester=self.current))
            if not current:
                continue
            if student == self.demo_student:
                pay(student, Decimal("150000"), date(2026, 9, 10))
            elif self.rng.random() < 0.45:
                pay(student, current, date(2026, 9, self.rng.randint(8, 20)))
            elif self.rng.random() < 0.5:
                pay(
                    student,
                    Decimal(self.rng.choice([50000, 100000, 150000])),
                    date(2026, 9, self.rng.randint(8, 20)),
                    method=Payment.Method.BANK_DEPOSIT,
                    reference=f"TLR{self.rng.randint(100000, 999999)}",
                )

    def create_news(self):
        registrar = User.objects.get(username="registrar")
        hod = User.objects.get(username="hod")
        now = timezone.now()

        Announcement.objects.create(
            title="Course registration for First Semester 2026/2027 is open",
            body="All returning and new students should complete course registration and print their course forms "
            "before the deadline on Friday, 16 October 2026. Late registration attracts a penalty.",
            priority=Announcement.Priority.IMPORTANT,
            pinned=True,
            is_public=True,
            author=registrar,
        )
        Announcement.objects.create(
            title="Matriculation ceremony for 2026/2027 freshers",
            body="The matriculation ceremony holds at the University Auditorium. All 100-level students must attend "
            "in their academic gowns.",
            audience=Announcement.Audience.STUDENTS,
            is_public=True,
            author=registrar,
        )
        Announcement.objects.create(
            title="Senate meeting",
            body="The next Senate meeting holds on Thursday at 10:00 a.m. in the Senate Chamber.",
            audience=Announcement.Audience.STAFF,
            author=registrar,
        )
        Announcement.objects.create(
            title="Departmental orientation for Computer Science students",
            body="All Computer Science students should attend the departmental orientation in LT 1 on Wednesday.",
            department=self.departments["CSC"],
            author=hod,
        )
        for code in ("CSC201", "CSC203"):
            offering = self.offerings[(self.current.pk, code)]
            Announcement.objects.create(
                title=f"{code}: Lecture notes and first assignment",
                body="Lecture notes for weeks 1–2 and the first assignment are available. Submission is in two weeks.",
                offering=offering,
                author=offering.lecturer,
            )

        for title, body in [
            (
                "Admission into 2027/2028 undergraduate programmes: applications open soon",
                "The University will soon begin accepting applications into its undergraduate programmes for the "
                "2027/2028 academic session. Candidates who chose the University in the UTME and meet the minimum "
                "requirements should watch the Admissions page for screening dates.",
            ),
            (
                "Department of Microbiology wins national research grant",
                "Researchers in the Department of Microbiology have been awarded a national research grant to study "
                "antimicrobial resistance in community health settings across three states.",
            ),
            (
                "New ICT and e-learning centre commissioned",
                "A 500-seat ICT and e-learning centre has been commissioned to support computer-based examinations, "
                "digital skills training and the University's growing online resources.",
            ),
        ]:
            Announcement.objects.create(title=title, body=body, is_public=True, author=registrar)

        def at(day, hour=9):
            return timezone.make_aware(datetime.combine(day, time(hour)))

        today = timezone.localdate()
        for title, category, location, day in [
            ("Course registration closes", Event.Category.DEADLINE, "Online", date(2026, 10, 16)),
            ("Matriculation ceremony", Event.Category.ACADEMIC, "University Auditorium", date(2026, 10, 24)),
            ("Mid-semester break", Event.Category.ACADEMIC, "Campus-wide", date(2026, 11, 13)),
            (
                "Inter-faculty football final",
                Event.Category.SPORTS,
                "University Sports Complex",
                today + timedelta(days=12),
            ),
            ("Career and internship fair", Event.Category.CAREER, "Multipurpose Hall", today + timedelta(days=18)),
            ("First semester examinations begin", Event.Category.ACADEMIC, "Examination halls", date(2027, 1, 11)),
            ("Convocation ceremony", Event.Category.ACADEMIC, "Convocation Arena", date(2026, 12, 5)),
        ]:
            if at(day) >= now:
                Event.objects.create(
                    title=title,
                    category=category,
                    location=location,
                    starts_at=at(day),
                    ends_at=at(day, 13),
                    description=f"{title}.",
                )

        Notification.objects.create(
            user=self.demo_student,
            category=Notification.Category.RESULTS,
            title="Your Second Semester 2025/2026 results are available",
            link="/portal/results",
        )
        Notification.objects.create(
            user=self.demo_student,
            category=Notification.Category.REGISTRATION,
            title="Course registration for First Semester 2026/2027 is now open",
            link="/portal/registration",
        )

    def create_attendance(self):
        """Closed sessions for every current offering since the semester began, plus one ready for today."""
        weekday_codes = ["MON", "TUE", "WED", "THU", "FRI"]
        today = timezone.localdate()
        # Most students attend well; a few are at risk of missing the 75% requirement.
        reliability = {s.pk: (0.55 if i % 9 == 4 else 0.92) for i, s in enumerate(self.students)}
        reliability[self.demo_student.pk] = 0.85
        for (semester_id, _), offering in self.offerings.items():
            if semester_id != self.current.pk:
                continue
            students = [
                e.student
                for e in offering.enrollments.filter(status=Enrollment.Status.REGISTERED).select_related("student")
            ]
            if not students:
                continue
            day = self.current.start_date
            while day < today:
                if day.weekday() < 5 and weekday_codes[day.weekday()] in offering.day_list:
                    opened = timezone.make_aware(datetime.combine(day, offering.start_time))
                    session = AttendanceSession.objects.create(
                        offering=offering,
                        date=day,
                        start_time=offering.start_time,
                        status=AttendanceSession.Status.CLOSED,
                        opened_at=opened,
                        closed_at=opened + timedelta(minutes=20),
                        created_by=offering.lecturer,
                        topic=f"Week {(day - self.current.start_date).days // 7 + 1}",
                    )
                    for student in students:
                        roll = self.rng.random()
                        if roll < reliability[student.pk]:
                            status = (
                                AttendanceRecord.Status.LATE
                                if roll > reliability[student.pk] - 0.08
                                else AttendanceRecord.Status.PRESENT
                            )
                            method = AttendanceRecord.Method.QR
                        elif roll < reliability[student.pk] + 0.03:
                            status, method = AttendanceRecord.Status.EXCUSED, AttendanceRecord.Method.LECTURER
                        else:
                            status, method = AttendanceRecord.Status.ABSENT, AttendanceRecord.Method.SYSTEM
                        AttendanceRecord.objects.create(
                            session=session,
                            student=student,
                            status=status,
                            method=method,
                            marked_by=student if method == AttendanceRecord.Method.QR else offering.lecturer,
                            marked_at=opened + timedelta(minutes=self.rng.randint(1, 14)),
                        )
                day += timedelta(days=1)

        # The demo lecturer: a correction awaiting the HOD, and a session ready to start today.
        lecturer = User.objects.get(username="lecturer")
        taught = [o for (sem, _), o in self.offerings.items() if sem == self.current.pk and o.lecturer == lecturer]
        absent = (
            AttendanceRecord.objects.filter(session__offering__in=taught, status=AttendanceRecord.Status.ABSENT)
            .select_related("session")
            .first()
        )
        if absent:
            AttendanceCorrection.objects.create(
                record=absent,
                from_status=absent.status,
                to_status=AttendanceRecord.Status.EXCUSED,
                reason="Student presented a medical certificate from the University Health Centre.",
                requested_by=lecturer,
            )
        if taught:
            offering = taught[0]
            AttendanceSession.objects.get_or_create(
                offering=offering,
                date=today,
                start_time=offering.start_time,
                defaults={"topic": "Today's lecture", "created_by": lecturer},
            )

    # --- Admissions -----------------------------------------------------------------------------

    def sample_document(self, kind, applicant):
        """A small stand-in file for an uploaded credential: a photo for the passport, else a PDF."""
        from io import BytesIO

        from django.core.files.base import ContentFile
        from PIL import Image, ImageDraw
        from reportlab.lib.pagesizes import A5
        from reportlab.pdfgen import canvas

        buffer = BytesIO()
        if kind == ApplicationDocument.Kind.PASSPORT:
            image = Image.new("RGB", (300, 360), (225, 232, 242))
            draw = ImageDraw.Draw(image)
            draw.ellipse((95, 60, 205, 170), fill=(120, 135, 160))
            draw.rounded_rectangle((55, 190, 245, 380), radius=60, fill=(120, 135, 160))
            image.save(buffer, "JPEG", quality=85)
            return ContentFile(buffer.getvalue(), name="passport.jpg"), "image/jpeg"
        pdf = canvas.Canvas(buffer, pagesize=A5)
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(40, 520, ApplicationDocument.Kind(kind).label)
        pdf.setFont("Helvetica", 10)
        pdf.drawString(40, 495, f"Candidate: {applicant.get_full_name()}")
        pdf.drawString(40, 478, "SAMPLE DOCUMENT FOR THE DEMO PORTAL - NOT A REAL CREDENTIAL")
        pdf.save()
        return ContentFile(buffer.getvalue(), name=f"{kind}.pdf"), "application/pdf"

    def create_admissions(self):
        today = timezone.localdate()
        self.cycle = AdmissionCycle.objects.create(
            session="2026/2027",
            application_fee=Decimal("10000"),
            opens_on=date(2026, 8, 3),
            closes_on=max(date(2026, 10, 30), today + timedelta(days=30)),
            min_utme_score=180,
            resumption_date=date(2026, 11, 16),
            acceptance_deadline=max(date(2026, 11, 6), today + timedelta(days=40)),
        )
        officer = User.objects.get(username="admissions1")
        S = Application.Status
        # Everything that happens on the way to each status.
        paths = {
            S.DRAFT: [],
            S.SUBMITTED: [S.SUBMITTED],
            S.UNDER_REVIEW: [S.SUBMITTED, S.UNDER_REVIEW],
            S.SCREENING: [S.SUBMITTED, S.UNDER_REVIEW, S.SCREENING],
            S.APPROVED: [S.SUBMITTED, S.UNDER_REVIEW, S.SCREENING, S.APPROVED],
            S.WAITLISTED: [S.SUBMITTED, S.UNDER_REVIEW, S.SCREENING, S.WAITLISTED],
            S.REJECTED: [S.SUBMITTED, S.UNDER_REVIEW, S.SCREENING, S.REJECTED],
            S.ADMITTED: [S.SUBMITTED, S.UNDER_REVIEW, S.SCREENING, S.APPROVED, S.ADMITTED],
            S.ACCEPTED: [S.SUBMITTED, S.UNDER_REVIEW, S.SCREENING, S.APPROVED, S.ADMITTED, S.ACCEPTED],
        }
        people = [  # username, first, last, gender, target status, programme, second choice, UTME score
            ("applicant", "Chioma", "Nwosu", "female", S.DRAFT, "CSC", "MTH", 262),
            ("applicant2", "Emeka", "Obiora", "male", S.ADMITTED, "EEE", "CSC", 291),
            ("aisha.bello", "Aisha", "Bello", "female", S.SUBMITTED, "MCB", "CSC", 238),
            ("tobi.adeyemi", "Tobiloba", "Adeyemi", "male", S.SUBMITTED, "ACC", "BUS", 221),
            ("ngozi.ude", "Ngozi", "Ude", "female", S.SUBMITTED, "ENG", None, 205),
            ("musa.garba", "Musa", "Garba", "male", S.UNDER_REVIEW, "EEE", "MTH", 244),
            ("ifeoma.okeke", "Ifeoma", "Okeke", "female", S.UNDER_REVIEW, "CSC", "MTH", 256),
            ("dayo.akande", "Dayo", "Akande", "male", S.SCREENING, "CSC", "EEE", 278),
            ("zainab.yusuf", "Zainab", "Yusuf", "female", S.SCREENING, "ACC", "BUS", 233),
            ("uche.nnamdi", "Uchenna", "Nnamdi", "male", S.SCREENING, "BUS", "ACC", 199),
            ("funke.alabi", "Funke", "Alabi", "female", S.APPROVED, "MCB", "MTH", 268),
            ("bashir.lawal", "Bashir", "Lawal", "male", S.WAITLISTED, "CSC", "MTH", 214),
            ("esther.john", "Esther", "John", "female", S.REJECTED, "EEE", None, 187),
            ("kelechi.eze", "Kelechi", "Eze", "male", S.ACCEPTED, "CSC", "MTH", 301),
            ("halima.sani", "Halima", "Sani", "female", S.ACCEPTED, "ENG", "BUS", 247),
            ("victor.ojo", "Victor", "Ojo", "male", S.DRAFT, "ACC", None, None),
        ]
        subjects = [
            "English Language",
            "Mathematics",
            "Physics",
            "Chemistry",
            "Biology",
            "Economics",
            "Civic Education",
        ]
        start = timezone.make_aware(datetime.combine(date(2026, 8, 10), time(9)))
        for i, (username, first, last, gender, target, first_choice, second_choice, utme) in enumerate(people):
            user = self.make_user(
                username, first, last, User.Role.APPLICANT, phone=f"0813{self.rng.randint(1000000, 9999999)}"
            )
            application = Application.objects.create(
                cycle=self.cycle,
                applicant=user,
                gender=gender,
                programme=self.programmes[first_choice],
                second_choice=self.programmes[second_choice] if second_choice else None,
                date_of_birth=date(2007 - self.rng.randint(0, 2), self.rng.randint(1, 12), self.rng.randint(1, 28)),
                state_of_origin=self.rng.choice(STATES),
                lga="Municipal" if username != "applicant" else "Nsukka",
                address=f"{self.rng.randint(2, 90)} {self.rng.choice(LAST_NAMES)} Street",
                phone=user.phone,
                next_of_kin_name=f"Mr. {self.rng.choice(FIRST_NAMES)} {last}" if utme else "",
                next_of_kin_relationship="Father",
                next_of_kin_phone=f"0802{self.rng.randint(1000000, 9999999)}" if utme else "",
                jamb_reg_number=f"2026{self.rng.randint(1000, 9999)}{chr(65 + i)}{chr(70 + i % 10)}" if utme else "",
                utme_score=utme,
                olevel_results=[
                    {
                        "exam": "WAEC",
                        "year": 2025,
                        "subject": subject,
                        "grade": self.rng.choice(["A1", "B2", "B3", "C4", "C5"]),
                    }
                    for subject in subjects[: 6 if utme else 3]
                ],
            )
            application.number = f"BU/APP/{self.cycle.code}/{application.pk:05d}"
            application.save(update_fields=["number"])
            when = start + timedelta(days=i * 2, hours=i)
            events = [
                ApplicationEvent(
                    application=application,
                    action="created",
                    actor=user,
                    note="Application started",
                    public=True,
                    to_status=S.DRAFT,
                    created_at=when,
                )
            ]

            # The demo applicant's draft is half done: two documents, fee not yet paid.
            kinds = ApplicationDocument.REQUIRED[:2] if username == "applicant" else ApplicationDocument.REQUIRED
            if target == S.DRAFT and username != "applicant":
                kinds = ()
            steps = paths[target]
            for kind in kinds:
                content, content_type = self.sample_document(kind, user)
                reviewed = S.SCREENING in steps or (
                    target == S.UNDER_REVIEW and kind != ApplicationDocument.Kind.OLEVEL
                )
                rejected = username == "musa.garba" and kind == ApplicationDocument.Kind.OLEVEL
                ApplicationDocument.objects.create(
                    application=application,
                    kind=kind,
                    file=content,
                    original_filename=content.name,
                    content_type=content_type,
                    size=content.size,
                    status="rejected" if rejected else "verified" if reviewed else "pending",
                    review_note="The result is not legible. Upload a clear scan of the full result."
                    if rejected
                    else "",
                    reviewed_by=officer if (reviewed or rejected) else None,
                    reviewed_at=when + timedelta(days=4) if (reviewed or rejected) else None,
                )
            if steps:
                paid_at = when + timedelta(hours=2)
                ApplicationPayment.objects.create(
                    application=application,
                    reference=f"APP-{paid_at:%Y%m%d}-{self.rng.randint(10**9, 10**10 - 1):X}",
                    amount=self.cycle.application_fee,
                    status="success",
                    channel=self.rng.choice(["card", "bank_transfer", "ussd"]),
                    gateway_response="Approved",
                    paid_at=paid_at,
                )
                events.append(
                    ApplicationEvent(
                        application=application,
                        action="fee_paid",
                        actor=user,
                        public=True,
                        note="Application fee ₦10,000.00",
                        created_at=paid_at,
                    )
                )

            previous = S.DRAFT
            for n, status in enumerate(steps, start=1):
                at = when + timedelta(days=n * 3, hours=3)
                actor = user if status in (S.SUBMITTED, S.ACCEPTED) else officer
                note = ""
                if status == S.SUBMITTED:
                    application.submitted_at = at
                elif status == S.UNDER_REVIEW:
                    application.reviewer = officer
                elif status in (S.APPROVED, S.WAITLISTED, S.REJECTED):
                    score = Decimal(
                        self.rng.randint(58, 88)
                        if status == S.APPROVED or target in (S.ADMITTED, S.ACCEPTED)
                        else self.rng.randint(40, 55)
                    )
                    application.screening_score, application.screened_by = score, officer
                    application.screened_at = at - timedelta(days=1)
                    events.append(
                        ApplicationEvent(
                            application=application,
                            action="screening",
                            actor=officer,
                            note=f"Screening score {score}.",
                            created_at=at - timedelta(days=1),
                        )
                    )
                    note = {
                        S.WAITLISTED: "Quota for the programme is filled; you may be offered a place later.",
                        S.REJECTED: "Aggregate score below the departmental cut-off.",
                    }.get(status, "")
                    application.decision_note, application.decided_by, application.decided_at = note, officer, at
                    if status == S.APPROVED:
                        application.admitted_programme = application.programme
                elif status == S.ADMITTED:
                    application.letter_number = f"BU/ADM/{self.cycle.code}/{application.pk:05d}"
                    application.letter_issued_at = at
                    note = f"Admission letter {application.letter_number}"
                elif status == S.ACCEPTED:
                    application.accepted_at = at
                events.append(
                    ApplicationEvent(
                        application=application,
                        action="status",
                        actor=actor,
                        public=True,
                        from_status=previous,
                        to_status=status,
                        note=note,
                        created_at=at,
                    )
                )
                title, body = admission_services.MESSAGES[status]
                Notification.objects.create(
                    user=user,
                    title=title,
                    body=body.format(number=application.number),
                    link="/portal/application",
                    category=Notification.Category.ADMISSION,
                    read_at=at if status != steps[-1] else None,
                )
                if actor == officer:
                    log = AuditLog.objects.create(
                        actor=officer,
                        action=f"admissions.{status}",
                        target_type="admissions.application",
                        target_id=str(application.pk),
                        summary=f"{application.number}: {S(previous).label} → {S(status).label}",
                    )
                    AuditLog.objects.filter(pk=log.pk).update(created_at=at)
                previous = status
            if target == S.SCREENING and username == "dayo.akande":
                application.screening_score, application.screened_by = Decimal("74.5"), officer
                application.screened_at = when + timedelta(days=10)
            application.status = target
            application.save()
            # auto_now_add overrides the timestamps on insert; put the backdated ones back.
            times = [e.created_at for e in events]
            for event, created in zip(ApplicationEvent.objects.bulk_create(events), times, strict=True):
                ApplicationEvent.objects.filter(pk=event.pk).update(created_at=created)

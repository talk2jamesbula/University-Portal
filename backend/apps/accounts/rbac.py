"""Role-based access control: the permission catalogue and the default staff roles.

Every access check in the API asks for a permission code (e.g. "finance.manage"), never a
role name, so the Registrar can change what a role may do from the portal without code changes.
Super admins (User.Role.ADMIN) hold every permission.
"""

PERMISSIONS = {
    # People
    "users.manage": "Create and manage user accounts",
    "roles.manage": "Assign staff roles and edit role permissions",
    "students.manage": "Maintain student records: matriculation, transfers, withdrawals, graduation",
    "students.view": "View student records (HODs and Deans: their own department or faculty)",
    # Academics
    "academics.manage": "Manage faculties, departments, programmes, courses, sessions and semesters",
    "registration.manage": "Open or close course registration and adjust student registrations",
    "courses.teach": "Teach assigned courses: materials, attendance and scores",
    "results.approve_department": "Approve results for a department (HOD)",
    "results.approve_faculty": "Approve results for a faculty (Dean)",
    "results.publish": "Publish approved results to students",
    "exams.manage": "Manage examination timetables and venues, eligibility waivers and exam cards",
    "exams.invigilate": "Verify exam cards and check candidates in at examinations",
    "attendance.view": "View attendance reports across courses",
    "attendance.approve": "Approve corrections to closed attendance sessions",
    # Admissions & records
    "admissions.manage": "Screen applicants and issue admission decisions",
    "documents.issue": "Issue and verify transcripts, certificates and letters",
    # Money
    "finance.view": "View student accounts and financial reports",
    "finance.manage": "Configure fees, record and verify payments, issue refunds",
    # Services
    "library.manage": "Manage the library catalogue and loans",
    "accommodation.manage": "Manage hostels, allocations and maintenance",
    "helpdesk.manage": "Handle support tickets",
    "communications.send": "Send announcements and messages to groups of users",
    # Oversight
    "reports.view": "View the management dashboard and reports",
    "audit.view": "View audit logs and login history",
}

# code: (name, scope, permissions). Scope says what an appointment is tied to.
DEFAULT_ROLES = {
    "vc": ("Vice Chancellor", None, ["reports.view", "finance.view", "attendance.view", "audit.view", "students.view"]),
    "registrar": (
        "Registrar",
        None,
        [
            "users.manage",
            "roles.manage",
            "students.manage",
            "academics.manage",
            "registration.manage",
            "results.publish",
            "admissions.manage",
            "documents.issue",
            "communications.send",
            "reports.view",
            "attendance.view",
            "attendance.approve",
        ],
    ),
    "bursar": ("Bursar", None, ["finance.view", "finance.manage", "reports.view"]),
    "dean": (
        "Dean",
        "faculty",
        ["results.approve_faculty", "attendance.view", "students.view", "communications.send", "reports.view"],
    ),
    "hod": (
        "Head of Department",
        "department",
        [
            "results.approve_department",
            "attendance.view",
            "attendance.approve",
            "students.view",
            "communications.send",
        ],
    ),
    "lecturer": ("Lecturer", None, ["courses.teach", "exams.invigilate"]),
    "exam_officer": (
        "Examination Officer",
        None,
        ["exams.manage", "exams.invigilate", "results.publish", "communications.send"],
    ),
    "admission_officer": ("Admission Officer", None, ["admissions.manage"]),
    "finance_officer": ("Finance Officer", None, ["finance.view", "finance.manage"]),
    "librarian": ("Librarian", None, ["library.manage"]),
    "hostel_officer": ("Hostel Officer", None, ["accommodation.manage"]),
    "support_officer": ("Support Officer", None, ["helpdesk.manage"]),
}


def sync_default_roles(**kwargs):
    """Create any missing default roles. Existing roles (and edits to them) are left alone."""
    from .models import Role

    for code, (name, scope, permissions) in DEFAULT_ROLES.items():
        Role.objects.get_or_create(
            code=code, defaults={"name": name, "scope": scope or "", "permissions": permissions, "is_system": True}
        )

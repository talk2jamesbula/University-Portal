"""What the website chatbot knows: fixed facts about the University, plus live data from the database.

Keep the fixed facts in step with the public website's text in frontend/src/site/content.js.
"""

from django.conf import settings
from django.utils import timezone

from apps.academics.models import Faculty, Programme
from apps.admissions.models import AdmissionCycle
from apps.campus.models import Announcement, Event

CONTACT = {
    "address": "Km 12, University Road, Abuja, FCT, Nigeria",
    "phone": "+234 800 000 0000",
    "email": "info@bulacode.edu.ng",
    "admissions_email": "admissions@bulacode.edu.ng",
    "hours": "Monday to Friday, 8:00 a.m. to 4:00 p.m.",
}

PROFILE = f"""{settings.UNIVERSITY_NAME} is a Nigerian university established in 2012 and accredited by the National
Universities Commission (NUC). Motto: Knowledge, Character and Service. Mission: accessible, high-quality education and
research that develops ethical leaders, drives innovation and contributes to national development."""

REQUIREMENTS = """Admission routes:
- UTME (100 Level): five credit passes in WAEC, NECO or NABTEB (at most two sittings) including English Language and
  Mathematics; choose the University in JAMB UTME and meet the cut-off mark; take the post-UTME screening.
- Direct Entry (200 Level): A-Level, IJMB, JUPEB, OND (upper credit) or NCE (merit) in relevant subjects, plus the
  O-Level requirements; register for Direct Entry with JAMB choosing the University.
- Inter-university transfer: at least one completed session at an NUC-accredited university, a minimum CGPA of 2.40
  on a five-point scale, a letter of good conduct and an academic transcript.
How to apply online: create an account at /apply, complete the application (personal details, programme choice,
JAMB details, O-Level results), upload a passport photograph, O-Level result, JAMB result slip and birth certificate,
pay the application fee online (card, bank transfer or USSD via Paystack), then submit. Applicants track their status
(submitted, under review, screening, approved/waitlisted/rejected, admitted, accepted) by signing in at
/login/applicant, and download their admission letter and accept the offer there."""

LIBRARY = """Library hours: Monday to Friday 8:00 a.m. to 10:00 p.m.; Saturday 9:00 a.m. to 5:00 p.m.;
Sunday 2:00 p.m. to 8:00 p.m.; open 24 hours during examinations.
Students may borrow up to 5 books for 14 days, renewable online.
E-journals, e-books and databases are available on and off campus."""

RESEARCH = """Research centres: Centre for Applied Computing (data science, AI); Antimicrobial Resistance
Research Group; Renewable Energy Laboratory (off-grid solar); Centre for Entrepreneurship; African Literatures Forum."""

PAGES = {
    "Home": "/",
    "About the University": "/about",
    "Faculties and departments": "/faculties",
    "Academic programmes": "/programmes",
    "Admissions and requirements": "/admissions",
    "Apply online": "/apply",
    "Applicant sign-in (track an application)": "/login/applicant",
    "News and announcements": "/news",
    "Events": "/events",
    "Research": "/research",
    "Library": "/library",
    "Contact us": "/contact",
    "Student portal sign-in": "/login/student",
    "Staff portal sign-in": "/login/staff",
}


def programmes():
    return list(
        Programme.objects.filter(is_active=True)
        .select_related("department__faculty")
        .order_by("department__faculty__name", "name")
    )


def admission_facts(cycle=None):
    cycle = cycle or AdmissionCycle.current()
    if not cycle:
        return "There is no admission exercise running at the moment."
    state = "OPEN" if cycle.is_open else "CLOSED"
    lines = [
        f"Admission into the {cycle.session} session is {state}. Applications open {cycle.opens_on:%d %B %Y} and close "
        f"{cycle.closes_on:%d %B %Y}.",
        f"Application fee: ₦{cycle.application_fee:,.2f} (not refundable). "
        f"Minimum UTME score to apply: {cycle.min_utme_score}.",
    ]
    if cycle.acceptance_deadline:
        lines.append(f"Admitted candidates must accept their offer by {cycle.acceptance_deadline:%d %B %Y}.")
    if cycle.resumption_date:
        lines.append(f"Resumption for new students: {cycle.resumption_date:%d %B %Y}.")
    return " ".join(lines)


def build():
    """The chatbot's knowledge as plain text, for the model's system prompt."""
    faculties = Faculty.objects.prefetch_related("departments").order_by("name")
    programme_lines = [
        f"- {p.title} ({p.duration_years} years) — Department of {p.department.name}, {p.department.faculty.name}. "
        f"Page: /programmes/{p.code}"
        for p in programmes()
    ]
    news = Announcement.objects.filter(is_public=True).order_by("-created_at")[:5]
    events = Event.objects.filter(is_public=True, starts_at__gte=timezone.now()).order_by("starts_at")[:5]
    sections = [
        ("About", PROFILE),
        (
            "Contact",
            f"Address: {CONTACT['address']}. Phone: {CONTACT['phone']}. Email: {CONTACT['email']}. "
            f"Admissions email: {CONTACT['admissions_email']}. Office hours: {CONTACT['hours']} "
            "Messages can also be sent through the contact form at /contact.",
        ),
        (
            "Faculties and departments",
            "\n".join(f"- {f.name}: {', '.join(d.name for d in f.departments.all())}" for f in faculties),
        ),
        ("Undergraduate programmes", "\n".join(programme_lines)),
        ("Current admission exercise", admission_facts()),
        ("Admission requirements and how to apply", REQUIREMENTS),
        ("Library", LIBRARY),
        ("Research", RESEARCH),
        ("Latest news", "\n".join(f"- {n.title} ({n.created_at:%d %b %Y}): /news/{n.pk}" for n in news) or "None."),
        (
            "Upcoming events",
            "\n".join(f"- {e.title}, {timezone.localtime(e.starts_at):%d %b %Y}" for e in events) or "None listed.",
        ),
        ("Website pages", "\n".join(f"- {name}: {path}" for name, path in PAGES.items())),
    ]
    return "\n\n".join(f"## {title}\n{body}" for title, body in sections)

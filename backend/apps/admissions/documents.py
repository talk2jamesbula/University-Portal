"""PDF admission letters and application fee receipts (sharing the finance PDFs' fonts and styles)."""

from django.conf import settings
from django.utils import timezone
from reportlab.lib.enums import TA_JUSTIFY, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import ListFlowable, ListItem, Paragraph, Spacer, Table, TableStyle

from apps.finance.documents import (
    BASE,
    BOLD,
    GOLD,
    NAVY,
    ORG,
    SMALL,
    TITLE,
    _build,
    _details,
    amount_in_words,
    naira,
)

BODY = ParagraphStyle("body", parent=BASE, fontSize=10.5, leading=15.5, alignment=TA_JUSTIFY)
HEADING = ParagraphStyle("heading", parent=BOLD, fontSize=12, leading=16, textColor=NAVY, spaceBefore=4)


def _letterhead(office, number, issued, title=None):
    left = [Paragraph(settings.UNIVERSITY_NAME, ORG), Paragraph(office, SMALL)]
    right = [
        Paragraph(f"Ref: <b>{number}</b>", ParagraphStyle("r", parent=BASE, alignment=TA_RIGHT)),
        Paragraph(f"{issued:%d %B %Y}", ParagraphStyle("d", parent=SMALL, alignment=TA_RIGHT)),
    ]
    if title:
        right.insert(0, Paragraph(title, ParagraphStyle("t", parent=TITLE, alignment=TA_RIGHT)))
    table = Table([[left, right]], colWidths=[100 * mm, 74 * mm])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, 0), 2, GOLD),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return table


def admission_letter_pdf(application):
    app = application
    applicant = app.applicant
    programme = app.admitted_programme
    department = programme.department
    cycle = app.cycle
    issued = timezone.localtime(app.letter_issued_at)
    name = " ".join(p for p in (applicant.first_name, app.middle_name, applicant.last_name) if p)
    level = "200" if app.entry_mode == app.EntryMode.DIRECT_ENTRY else "100"
    deadline = f" by <b>{cycle.acceptance_deadline:%d %B %Y}</b>" if cycle.acceptance_deadline else ""
    conditions = [
        f"Accept this offer on the admission portal{deadline}, and also accept it on the JAMB Central "
        "Admissions Processing System (CAPS).",
        "Present the originals of all credentials submitted with your application for verification at registration. "
        "The admission will be withdrawn if any information or document is found to be false, at any time.",
        "Pay the acceptance and tuition fees, complete medical screening and register within the registration period.",
        "Abide by the rules and regulations of the University.",
    ]
    story = [
        _letterhead("Office of the Registrar · Admissions", app.letter_number, issued),
        Spacer(1, 10 * mm),
        Paragraph(f"<b>{name.upper()}</b>", BASE),
        Paragraph(app.address.replace("\n", "<br/>") or "", SMALL),
        Paragraph(
            f"Application no. {app.number}"
            + (f" · JAMB reg. no. {app.jamb_reg_number}" if app.jamb_reg_number else ""),
            SMALL,
        ),
        Spacer(1, 8 * mm),
        Paragraph(f"Dear {applicant.first_name},", BODY),
        Spacer(1, 4 * mm),
        Paragraph(f"OFFER OF PROVISIONAL ADMISSION: {cycle.session} ACADEMIC SESSION", HEADING),
        Spacer(1, 3 * mm),
        Paragraph(
            "I am pleased to inform you that you have been offered <b>provisional admission</b> into "
            f"{settings.UNIVERSITY_NAME} to study for the degree of <b>{programme.title}</b> "
            f"in the Department of {department.name}, "
            f"{department.faculty.name}, for the {cycle.session} academic session.",
            BODY,
        ),
        Spacer(1, 4 * mm),
        _details(
            [
                ("Programme", programme.title),
                ("Department", department.name),
                ("Faculty", department.faculty.name),
                ("Mode of entry", app.get_entry_mode_display()),
                ("Entry level", f"{level} Level"),
                ("Duration", f"{programme.duration_years - (1 if level == '200' else 0)} years"),
                *([("Resumption", f"{cycle.resumption_date:%A %d %B %Y}")] if cycle.resumption_date else []),
            ]
        ),
        Spacer(1, 5 * mm),
        Paragraph("This offer is subject to the following conditions:", BODY),
        ListFlowable(
            [ListItem(Paragraph(c, BODY), leftIndent=12) for c in conditions],
            bulletType="1",
            leftIndent=14,
            bulletFontName="DejaVu",
        ),
        Spacer(1, 5 * mm),
        Paragraph("Please accept my congratulations on your admission.", BODY),
        Spacer(1, 12 * mm),
        Paragraph("<b>Registrar</b>", BASE),
        Paragraph(f"for: {settings.UNIVERSITY_NAME}", SMALL),
        Spacer(1, 10 * mm),
        Paragraph(
            f"Verify this letter with the Admissions Office quoting reference {app.letter_number} "
            f"and application number {app.number}.",
            SMALL,
        ),
    ]
    return _build(story, f"Admission letter {app.letter_number}")


def fee_receipt_pdf(payment):
    app = payment.application
    paid = timezone.localtime(payment.paid_at)
    story = [
        _letterhead("Admissions Office", payment.reference, paid, title="Receipt"),
        Spacer(1, 8 * mm),
        _details(
            [
                ("Received from", app.applicant.get_full_name()),
                ("Application no.", app.number),
                ("Admission session", app.cycle.session),
                ("For", "Application fee"),
                ("Amount", f"<b>{naira(payment.amount)}</b>"),
                ("Amount in words", amount_in_words(payment.amount)),
                ("Paid via", (payment.channel or payment.gateway).replace("_", " ").title()),
                ("Transaction reference", payment.reference),
                ("Date paid", f"{paid:%d %B %Y, %H:%M}"),
            ]
        ),
        Spacer(1, 8 * mm),
        Paragraph("The application fee is not refundable.", SMALL),
    ]
    return _build(story, f"Receipt {payment.reference}")

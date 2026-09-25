"""The examination card: the student's photo, their exams with venue and seat, and a QR code
that invigilators scan to check the card is genuine and see the student's live eligibility."""

from django.conf import settings
from django.utils import timezone
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, Spacer, Table, TableStyle

from apps.finance.documents import (
    BASE,
    BOLD,
    GOLD,
    LINE,
    MUTED,
    NAVY,
    ORG,
    SMALL,
    SOFT,
    TITLE,
    _build,
)

CENTER_SMALL = ParagraphStyle("center_small", parent=SMALL, alignment=TA_CENTER)
PHOTO = 32 * mm


def _qr(text, size=34 * mm):
    widget = QrCodeWidget(text, barLevel="M")
    x1, y1, x2, y2 = widget.getBounds()
    drawing = Drawing(size, size, transform=[size / (x2 - x1), 0, 0, size / (y2 - y1), 0, 0])
    drawing.add(widget)
    return drawing


def _photo(student):
    if student.avatar:
        try:
            return Image(student.avatar.path, width=PHOTO, height=PHOTO)
        except OSError:
            pass  # file missing on disk: fall back to the placeholder
    box = Table([[Paragraph("No photo on record", CENTER_SMALL)]], colWidths=[PHOTO], rowHeights=[PHOTO])
    box.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    return box


def _header(semester, number):
    left = [Paragraph(settings.UNIVERSITY_NAME, ORG), Paragraph("Examinations Office", SMALL)]
    right = [
        Paragraph("Examination Card", ParagraphStyle("t", parent=TITLE, alignment=TA_RIGHT)),
        Paragraph(f"{semester.name} · No. <b>{number}</b>", ParagraphStyle("n", parent=BASE, alignment=TA_RIGHT)),
    ]
    table = Table([[left, right]], colWidths=[90 * mm, 84 * mm])
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


def card_number(student, semester):
    return f"EC/{semester.code}/{student.university_id or student.pk}"


def exam_card_pdf(student, semester, rows, verify_url):
    """rows: the student's eligible exams from services.student_exams()."""
    profile = getattr(student, "student_profile", None)
    details = [
        ("Name", f"<b>{student.get_full_name() or student.username}</b>"),
        ("Matric no.", student.university_id or "—"),
    ]
    if profile:
        details += [("Programme", profile.programme.title), ("Level", f"{profile.level} Level")]
    about = Table(
        [[Paragraph(label, SMALL), Paragraph(value, BASE)] for label, value in details], colWidths=[24 * mm, 74 * mm]
    )
    about.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    identity = Table(
        [[_photo(student), about, _qr(verify_url)]],
        colWidths=[PHOTO + 6 * mm, 100 * mm, 36 * mm],
    )
    identity.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    header = ["Course", "Date", "Time", "Venue", "Seat"]
    data = [[Paragraph(h, SMALL) for h in header]]
    for row in rows:
        exam, candidate = row["exam"], row["candidate"]
        course = exam.offering.course
        venue = candidate.venue.name if candidate and candidate.venue else "To be assigned"
        seat = str(candidate.seat_number) if candidate and candidate.seat_number else "—"
        mode = " · CBT" if exam.is_cbt else ""
        data.append(
            [
                Paragraph(f"<b>{course.code}</b> {course.title}{mode}", BASE),
                Paragraph(f"{exam.date:%a %d %b %Y}", BASE),
                Paragraph(f"{exam.start_time:%H:%M} ({exam.duration_minutes} min)", BASE),
                Paragraph(venue, BASE),
                Paragraph(f"<b>{seat}</b>", BASE),
            ]
        )
    exams = Table(data, colWidths=[62 * mm, 28 * mm, 30 * mm, 40 * mm, 14 * mm], repeatRows=1)
    exams.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), SOFT),
                ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    rules = [
        "Bring this card and your student ID card to every examination. You will not be admitted without them.",
        "Be seated 15 minutes before the start. Phones, smart watches and notes are not allowed in the hall.",
        "The invigilator scans the QR code to confirm your eligibility on the day. "
        "A card printed earlier does not override a change in your eligibility.",
    ]
    number = card_number(student, semester)
    story = [
        _header(semester, number),
        Spacer(1, 8 * mm),
        identity,
        Spacer(1, 8 * mm),
        Paragraph("Examinations", ParagraphStyle("h", parent=BOLD, fontSize=11, textColor=NAVY)),
        Spacer(1, 2 * mm),
        exams,
        Spacer(1, 8 * mm),
        Paragraph("Rules", ParagraphStyle("h2", parent=BOLD, textColor=NAVY)),
        *[Paragraph(f"{i}. {text}", SMALL) for i, text in enumerate(rules, 1)],
        Spacer(1, 6 * mm),
        Paragraph(
            f"Issued {timezone.localtime():%d %B %Y at %H:%M}. Verify at {verify_url.split('?')[0]}",
            ParagraphStyle("v", parent=SMALL, textColor=MUTED),
        ),
    ]
    return _build(story, f"Examination card {number}")

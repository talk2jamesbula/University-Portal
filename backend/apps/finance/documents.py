"""PDF receipts and invoices."""

from decimal import Decimal
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import Charge
from .services import account_summary, allocate_payments

FONT_DIR = Path(__file__).resolve().parent / "fonts"
# DejaVu Sans includes the Naira sign (₦), which the built-in PDF fonts lack.
pdfmetrics.registerFont(TTFont("DejaVu", FONT_DIR / "DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DejaVu-Bold", FONT_DIR / "DejaVuSans-Bold.ttf"))
# Lets <b> inside paragraphs switch to the bold face.
pdfmetrics.registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold", italic="DejaVu", boldItalic="DejaVu-Bold")

NAVY = colors.HexColor("#12305a")
GOLD = colors.HexColor("#e0b54a")
MUTED = colors.HexColor("#64748b")
LINE = colors.HexColor("#e2e7ef")
SOFT = colors.HexColor("#f4f6fa")
GREEN = colors.HexColor("#147a4b")
RED = colors.HexColor("#b42318")
AMBER = colors.HexColor("#a15c07")

BASE = ParagraphStyle("base", fontName="DejaVu", fontSize=9.5, leading=13)
SMALL = ParagraphStyle("small", parent=BASE, fontSize=8, leading=11, textColor=MUTED)
BOLD = ParagraphStyle("bold", parent=BASE, fontName="DejaVu-Bold")
RIGHT = ParagraphStyle("right", parent=BASE, alignment=TA_RIGHT)
SMALL_RIGHT = ParagraphStyle("small_right", parent=SMALL, alignment=TA_RIGHT)
ORG = ParagraphStyle("org", parent=BOLD, fontSize=15, leading=19, textColor=NAVY)
TITLE = ParagraphStyle("title", parent=BASE, fontName="DejaVu-Bold", fontSize=18, leading=22, textColor=NAVY)


def naira(amount):
    amount = Decimal(amount)
    sign = "-" if amount < 0 else ""
    return f"{sign}₦{abs(amount):,.2f}"


_ONES = [
    "",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def _words_below_1000(n):
    hundreds, rest = divmod(n, 100)
    parts = []
    if hundreds:
        parts.append(f"{_ONES[hundreds]} hundred")
    if rest:
        if rest < 20:
            text = _ONES[rest]
        else:
            tens, ones = divmod(rest, 10)
            text = _TENS[tens] + (f"-{_ONES[ones]}" if ones else "")
        parts.append(("and " if hundreds else "") + text)
    return " ".join(parts)


def number_to_words(n):
    if n == 0:
        return "zero"
    parts = []
    for size, label in ((10**9, "billion"), (10**6, "million"), (10**3, "thousand"), (1, "")):
        chunk, n = divmod(n, size)
        if chunk:
            words = _words_below_1000(chunk)
            # "one thousand and five": British/Nigerian usage adds "and" before a final small chunk.
            if not label and parts and chunk < 100:
                words = f"and {words}"
            parts.append(f"{words} {label}".strip())
    return " ".join(parts)


def amount_in_words(amount):
    amount = Decimal(amount).quantize(Decimal("0.01"))
    naira_part = int(amount)
    kobo = int((amount - naira_part) * 100)
    text = f"{number_to_words(naira_part)} naira"
    if kobo:
        text += f", {number_to_words(kobo)} kobo"
    return text[0].upper() + text[1:] + " only"


def _header(title, number, issued):
    """University name on the left; document title and number on the right."""
    left = [
        Paragraph(settings.UNIVERSITY_NAME, ORG),
        Paragraph(settings.UNIVERSITY_ADDRESS, SMALL),
    ]
    right = [
        Paragraph(title, ParagraphStyle("t", parent=TITLE, alignment=TA_RIGHT)),
        Paragraph(f"No. <b>{number}</b>", ParagraphStyle("n", parent=RIGHT, fontName="DejaVu")),
        Paragraph(f"Issued {issued:%d %B %Y}", ParagraphStyle("d", parent=SMALL, alignment=TA_RIGHT)),
    ]
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


def _details(rows):
    """Two-column label/value block."""
    table = Table(
        [[Paragraph(label, SMALL), Paragraph(value, BASE)] for label, value in rows],
        colWidths=[38 * mm, 136 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return table


def _line_items(header, rows, totals, col_widths):
    data = [[Paragraph(h, SMALL_RIGHT if i else SMALL) for i, h in enumerate(header)]]
    for row in rows:
        data.append([Paragraph(str(c), RIGHT if i else BASE) for i, c in enumerate(row)])
    for label, *values in totals:
        data.append([Paragraph(label, BOLD)] + [Paragraph(f"<b>{v}</b>", RIGHT) for v in values])
    table = Table(data, colWidths=col_widths, repeatRows=1)
    n_totals = len(totals)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), SOFT),
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, LINE),
                ("LINEBELOW", (0, 1), (-1, -1 - n_totals), 0.4, LINE),
                ("LINEABOVE", (0, -n_totals), (-1, -n_totals), 1, NAVY),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("DejaVu", 7.5)
    canvas.setFillColor(MUTED)
    notice = "This is a computer-generated document and does not require a signature."
    canvas.drawString(18 * mm, 12 * mm, f"{settings.UNIVERSITY_NAME} · {notice}")
    canvas.drawRightString(A4[0] - 18 * mm, 12 * mm, f"Generated {timezone.localtime():%d %b %Y %H:%M}")
    canvas.restoreState()


def _build(story, title):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title=title,
        author=settings.UNIVERSITY_NAME,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=22 * mm,
    )
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()


def _student_rows(student):
    rows = [("Student", f"<b>{student.get_full_name() or student.username}</b>")]
    if student.university_id:
        rows.append(("Student ID", student.university_id))
    if student.department:
        rows.append(("Department", student.department.name))
    if student.email:
        rows.append(("Email", student.email))
    return rows


def receipt_pdf(payment):
    student = payment.student
    by_payment, _ = allocate_payments(student)
    balance = account_summary(student)["balance"]
    void = payment.status == payment.Status.VOID

    method = payment.get_method_display()
    channel = payment.note[len("Paid via ") :] if payment.note.startswith("Paid via ") else ""
    if payment.method == payment.Method.PAYSTACK and channel:
        method += f" — {channel}"
    if payment.card_last4:
        method += f" ending {payment.card_last4}"

    story = [
        _header("PAYMENT RECEIPT", payment.receipt_number, timezone.localtime(payment.paid_at)),
        Spacer(1, 8 * mm),
    ]
    if void:
        story += [
            Paragraph(
                f"VOID — this payment was reversed on {timezone.localtime(payment.voided_at):%d %B %Y}.",
                ParagraphStyle("void", parent=BOLD, textColor=RED, fontSize=11),
            ),
            Spacer(1, 4 * mm),
        ]

    amount_box = Table(
        [
            [
                [
                    Paragraph("AMOUNT RECEIVED", SMALL),
                    Paragraph(
                        naira(payment.amount),
                        ParagraphStyle(
                            "amount",
                            parent=BOLD,
                            fontSize=22,
                            leading=28,
                            textColor=RED if void else GREEN,
                        ),
                    ),
                    Paragraph(amount_in_words(payment.amount), BASE),
                ],
            ]
        ],
        colWidths=[174 * mm],
    )
    amount_box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SOFT),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story += [amount_box, Spacer(1, 6 * mm)]

    rows = _student_rows(student) + [
        ("Payment date", f"{timezone.localtime(payment.paid_at):%d %B %Y, %H:%M}"),
        ("Payment method", method),
    ]
    if payment.reference:
        rows.append(("Transaction ref.", payment.reference))
    story += [_details(rows), Spacer(1, 7 * mm)]

    parts = by_payment.get(payment.id, [])
    if parts:
        story += [Paragraph("Applied to", BOLD), Spacer(1, 2 * mm)]
        story.append(
            _line_items(
                ["Description", "Semester", "Amount applied"],
                [(c.description, c.semester.name if c.semester else "—", naira(amount)) for c, amount in parts],
                [("Total", "", naira(sum(a for _, a in parts)))],
                [82 * mm, 54 * mm, 38 * mm],
            )
        )
        story.append(Spacer(1, 6 * mm))

    status = "in credit" if balance < 0 else "outstanding" if balance > 0 else "fully paid"
    story.append(
        Paragraph(
            f"Account balance as at {timezone.localtime():%d %B %Y}: <b>{naira(abs(balance))}</b> {status}.",
            BASE,
        )
    )
    return _build(story, f"Receipt {payment.receipt_number}")


def invoice_number(student, semester):
    code = semester.code if semester else "GEN"
    return f"INV-{code}-{student.university_id or student.pk}"


def invoice_pdf(student, semester):
    charges = list(Charge.objects.filter(student=student, semester=semester).order_by("due_date", "id"))
    _, paid_by_charge = allocate_payments(student)
    total = sum((c.amount for c in charges), Decimal("0"))
    paid = sum((paid_by_charge.get(c.id, Decimal("0")) for c in charges), Decimal("0"))
    due = total - paid
    due_dates = [c.due_date for c in charges if paid_by_charge.get(c.id, 0) < c.amount]

    status_text, status_color = (
        ("PAID IN FULL", GREEN) if due <= 0 else ("PARTLY PAID", AMBER) if paid else ("UNPAID", RED)
    )

    story = [
        _header("INVOICE", invoice_number(student, semester), timezone.localdate()),
        Spacer(1, 8 * mm),
    ]
    rows = _student_rows(student) + [("Semester", semester.name if semester else "General charges")]
    if due_dates:
        rows.append(("Payment due", f"<b>{min(due_dates):%d %B %Y}</b>"))
    rows.append(("Status", f"<font color='#{status_color.hexval()[2:]}'><b>{status_text}</b></font>"))
    story += [_details(rows), Spacer(1, 7 * mm)]

    story.append(
        _line_items(
            ["Description", "Due date", "Amount", "Paid"],
            [
                (c.description, f"{c.due_date:%d %b %Y}", naira(c.amount), naira(paid_by_charge.get(c.id, 0)))
                for c in charges
            ],
            [("Total", "", naira(total), naira(paid)), ("Balance due", "", "", naira(max(due, 0)))],
            [88 * mm, 28 * mm, 29 * mm, 29 * mm],
        )
    )
    story += [
        Spacer(1, 7 * mm),
        Paragraph("How to pay", BOLD),
        Spacer(1, 1.5 * mm),
        Paragraph(
            "Pay online from <b>Fees &amp; Payments</b> in the student portal "
            "(card, bank transfer or USSD via Paystack), "
            "or at the Bursary quoting your student ID and this invoice number. Payments are applied to the "
            "oldest outstanding charges first.",
            BASE,
        ),
    ]
    if settings.BURSARY_ACCOUNT_NUMBER:
        story += [
            Spacer(1, 3 * mm),
            _details(
                [
                    ("Bank", settings.BURSARY_BANK_NAME),
                    ("Account name", settings.BURSARY_ACCOUNT_NAME),
                    ("Account number", f"<b>{settings.BURSARY_ACCOUNT_NUMBER}</b>"),
                ]
            ),
            Spacer(1, 2 * mm),
            Paragraph(
                "If you pay at the bank or by transfer, upload your teller or transfer receipt under "
                "<b>Fees &amp; Payments → Upload proof of payment</b> so the Bursary can credit your account.",
                BASE,
            ),
        ]
    return _build(story, f"Invoice {invoice_number(student, semester)}")

"""Bulk attendance upload: enter paper registers for a course from a CSV or Excel file.

One row per student per class: the date, the student's matric number and their status. Every row is checked
first; nothing is saved unless the whole file is valid. Classes are matched to existing sessions (or new ones
are created). Closed sessions can't be changed here: that still needs an approved correction.
"""

import re
from collections import defaultdict
from datetime import datetime, time

from django.db import transaction
from django.utils import timezone

from apps.core import spreadsheets
from apps.core.services import audit

from . import services
from .models import AttendanceRecord, AttendanceSession

Status = AttendanceRecord.Status
MAX_ROWS = 5000
REQUIRED = ["date", "matric_number", "status"]
ALIASES = {
    "matric": "matric_number",
    "matric_no": "matric_number",
    "reg_no": "matric_number",
    "registration_number": "matric_number",
    "attendance": "status",
    "time": "start_time",
    "class_time": "start_time",
    "name": "student_name",
}
STATUS_WORDS = {
    Status.PRESENT: {"present", "p", "yes", "y", "1", "✓", "attended"},
    Status.LATE: {"late", "l"},
    Status.EXCUSED: {"excused", "e", "exc", "permission"},
    Status.ABSENT: {"absent", "a", "no", "n", "0", "x"},
}
WORD_TO_STATUS = {word: status for status, words in STATUS_WORDS.items() for word in words}


def parse_status(value):
    return WORD_TO_STATUS.get(spreadsheets.text(value).lower())


def parse_time(value, default):
    """'09:00', '9:00', '9am', '14:30' or an Excel time; blank → the course's usual start time."""
    if isinstance(value, time):
        return value
    if isinstance(value, datetime):
        return value.time()
    raw = spreadsheets.text(value).lower().replace(".", ":")
    if not raw:
        return default
    match = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", raw)
    if not match:
        return None
    hour, minute, suffix = int(match[1]), int(match[2] or 0), match[3]
    if suffix == "pm" and hour < 12:
        hour += 12
    if suffix == "am" and hour == 12:
        hour = 0
    return time(hour, minute) if hour < 24 and minute < 60 else None


def template(offering, day, file_format="csv"):
    """The class list, ready to fill in: one row per registered student for the given date."""
    day = day or timezone.localdate()
    rows = [[day.isoformat(), s.university_id, s.get_full_name(), ""] for s in services.registered_students(offering)]
    header = ["date", "matric_number", "student_name", "status"]
    return spreadsheets.write_table(header, rows, file_format, title=f"{offering.course.code} attendance")


def check(offering, upload):
    """Validate a file. Returns (valid rows, errors, preview of the classes it covers)."""
    rows = spreadsheets.read_rows(upload, required=REQUIRED, aliases=ALIASES, max_rows=MAX_ROWS, noun="attendance rows")
    semester = offering.semester
    today = timezone.localdate()
    students = {s.university_id.upper(): s for s in services.registered_students(offering) if s.university_id}
    sessions = {(s.date, s.start_time): s for s in offering.attendance_sessions.all()}
    valid, errors, seen = [], [], {}

    for number, row in rows:
        problems = {}
        day = spreadsheets.parse_date(row.get("date"))
        if not day:
            problems["date"] = ["Use a date like 2026-10-05 or 05/10/2026."]
        elif not semester.start_date <= day <= semester.end_date:
            problems["date"] = [f"{day:%d %b %Y} is outside {semester}."]
        elif day > today:
            problems["date"] = ["Attendance can't be recorded for a future date."]
        start = parse_time(row.get("start_time"), offering.start_time)
        if start is None:
            problems["start_time"] = ["Use a time like 09:00 or 2pm."]
        matric = spreadsheets.text(row.get("matric_number")).upper()
        student = students.get(matric)
        if not matric:
            problems["matric_number"] = ["Enter the student's matric number."]
        elif not student:
            problems["matric_number"] = [f"{matric} isn't registered for {offering.course.code}."]
        status = parse_status(row.get("status"))
        if not status:
            problems["status"] = ["Use present, late, excused or absent (or P, L, E, A)."]
        if day and start and student:
            key = (day, start, student.pk)
            if key in seen:
                problems["matric_number"] = [f"Same student and class as row {seen[key]}."]
            else:
                seen[key] = number
            session = sessions.get((day, start))
            if session and session.status == AttendanceSession.Status.CLOSED:
                problems["date"] = [
                    f"The {day:%d %b} class is already closed. Ask for a correction to change it instead."
                ]
        if problems:
            errors.append({"row": number, "matric_number": matric, "errors": problems})
        else:
            valid.append({"date": day, "start_time": start, "student": student, "status": status})

    registered = len(students)
    groups = defaultdict(list)
    for row in valid:
        groups[(row["date"], row["start_time"])].append(row)
    preview = []
    for (day, start), group in sorted(groups.items()):
        counts = {s: sum(1 for r in group if r["status"] == s) for s in Status.values}
        session = sessions.get((day, start))
        preview.append(
            {
                "date": day,
                "start_time": start,
                "session": session.pk if session else None,
                "session_status": session.status if session else "new",
                **counts,
                "not_in_file": registered - len(group),
            }
        )
    return valid, errors, preview


def upload(offering, file, by, request=None, *, dry_run=False, close=True):
    """Check the file and, if every row is valid (and it isn't a dry run), record the attendance."""
    services.ensure_lecturer(by, offering)
    valid, errors, preview = check(offering, file)
    result = {
        "rows": len(valid) + len(errors),
        "valid": len(valid),
        "errors": errors,
        "sessions": preview,
        "saved": False,
    }
    if errors or dry_run:
        return result

    with transaction.atomic():
        by_class = defaultdict(list)
        for row in valid:
            by_class[(row["date"], row["start_time"])].append(row)
        for (day, start), rows in by_class.items():
            session, _ = AttendanceSession.objects.get_or_create(
                offering=offering,
                date=day,
                start_time=start,
                defaults={"created_by": by, "topic": "Uploaded register"},
            )
            now = timezone.now()
            for row in rows:
                AttendanceRecord.objects.update_or_create(
                    session=session,
                    student=row["student"],
                    defaults={
                        "status": row["status"],
                        "method": AttendanceRecord.Method.UPLOAD,
                        "marked_by": by,
                        "marked_at": now,
                        "flagged": False,
                        "flag_reason": "",
                    },
                )
            if close:  # everyone not on the register is marked absent (and told), as when closing in class
                services.close_session(session, by)
        audit(
            request,
            "attendance.upload",
            offering,
            f"Uploaded {len(valid)} attendance records for {offering.course.code} "
            f"({len(by_class)} class{'es' if len(by_class) != 1 else ''}){' and closed them' if close else ''}",
            actor=by,
        )
    result["saved"] = True
    result["sessions"] = check_saved(offering, preview)
    return result


def check_saved(offering, preview):
    """The preview again after saving, with each class's session and its final status."""
    sessions = {(s.date, s.start_time): s for s in offering.attendance_sessions.all()}
    for item in preview:
        session = sessions[(item["date"], item["start_time"])]
        item["session"], item["session_status"] = session.pk, session.status
    return preview

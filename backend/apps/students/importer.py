"""Bulk import of students from CSV or Excel.

Every row is validated first (with the same rules as the "New student" form). Nothing is imported unless every
row is valid, so a file can be fixed and uploaded again without creating half the students twice.
"""

from django.db import transaction

from apps.academics.models import Programme
from apps.core import spreadsheets
from apps.core.services import audit

from . import services
from .serializers import StudentWriteSerializer

MAX_ROWS = 2000
COLUMNS = [
    # (column, required, example)
    ("first_name", True, "Adaeze"),
    ("last_name", True, "Okafor"),
    ("email", True, "adaeze.okafor@example.com"),
    ("phone", False, "08031234567"),
    ("gender", True, "female"),
    ("date_of_birth", False, "2007-05-14"),
    ("programme_code", True, "CSC"),
    ("level", True, "100"),
    ("entry_session", True, "2026/2027"),
    ("current_session", True, "2026/2027"),
    ("mode_of_entry", False, "utme"),
    ("jamb_reg_number", False, "20261234AB"),
    ("admission_date", False, "2026-10-01"),
    ("state_of_origin", False, "Enugu"),
    ("lga", False, "Nsukka"),
    ("home_address", False, "12 Okpara Avenue, Enugu"),
    ("country", False, "Nigeria"),
    ("next_of_kin_name", False, "Mrs. Ngozi Okafor"),
    ("next_of_kin_relationship", False, "Mother"),
    ("next_of_kin_phone", False, "08037654321"),
]
ALIASES = {
    "programme": "programme_code",
    "surname": "last_name",
    "firstname": "first_name",
    "dob": "date_of_birth",
    "state": "state_of_origin",
    "address": "home_address",
    "jamb_number": "jamb_reg_number",
}


def template(file_format="csv"):
    return spreadsheets.write_table(
        [c for c, _, _ in COLUMNS], [[e for _, _, e in COLUMNS]], file_format, title="Students"
    )


def read_rows(upload):
    return spreadsheets.read_rows(
        upload,
        required=[c for c, required, _ in COLUMNS if required],
        aliases=ALIASES,
        max_rows=MAX_ROWS,
        noun="student rows",
    )


def _date(value):
    parsed = spreadsheets.parse_date(value)
    return parsed.isoformat() if parsed else (spreadsheets.text(value) or None)


def _payload(row, programmes):
    payload = {
        c: spreadsheets.text(row.get(c))
        for c, _, _ in COLUMNS
        if c not in ("programme_code", "date_of_birth", "admission_date")
    }
    payload["gender"] = payload["gender"].lower()
    payload["mode_of_entry"] = (payload.get("mode_of_entry") or "utme").lower().replace("direct entry", "de")
    for field in ("country",):
        if not payload[field]:
            payload.pop(field)
    payload["date_of_birth"] = _date(row.get("date_of_birth"))
    payload["admission_date"] = _date(row.get("admission_date"))
    code = spreadsheets.text(row.get("programme_code")).upper()
    payload["programme"] = programmes.get(code, f"unknown:{code}")
    return payload


def validate_rows(rows):
    """Validate each row. Returns (valid payloads, errors [{row, errors}])."""
    programmes = {p.code.upper(): p.pk for p in Programme.objects.all()}
    valid, errors = [], []
    seen = {"email": {}}
    for number, row in rows:
        payload = _payload(row, programmes)
        serializer = StudentWriteSerializer(data=payload)
        row_errors = {}
        if isinstance(payload["programme"], str):
            row_errors["programme_code"] = [f"No programme with code '{payload['programme'][8:]}'."]
            payload["programme"] = None
        if not serializer.is_valid():
            row_errors.update(
                {
                    k: [str(e) for e in v]
                    for k, v in serializer.errors.items()
                    if k != "programme" or "programme_code" not in row_errors
                }
            )
        for field in seen:
            value = (payload.get(field) or "").lower()
            if value and value in seen[field]:
                row_errors.setdefault(field, []).append(f"Same as row {seen[field][value]}.")
            elif value:
                seen[field][value] = number
        if row_errors:
            errors.append(
                {
                    "row": number,
                    "name": f"{payload.get('first_name', '')} {payload.get('last_name', '')}".strip(),
                    "errors": row_errors,
                }
            )
        else:
            valid.append((number, serializer.validated_data))
    return valid, errors


def import_students(upload, by, request=None, dry_run=False):
    services.require_manage(by)
    rows = read_rows(upload)
    valid, errors = validate_rows(rows)
    result = {"rows": len(rows), "valid": len(valid), "errors": errors, "created": []}
    if errors or dry_run:
        return result
    with transaction.atomic():
        for _, data in valid:
            user, password = services.create_student(data, by, request)
            result["created"].append(
                {
                    "id": user.id,
                    "name": user.get_full_name(),
                    "matric_number": user.university_id,
                    "email": user.email,
                    "temporary_password": password,
                }
            )
        audit(request, "students.import", None, f"Imported {len(valid)} students from {upload.name}"[:255], actor=by)
    return result

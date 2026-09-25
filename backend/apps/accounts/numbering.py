"""ID numbers, assigned by the system. Nobody types them in, so they're always unique and in the same format.

Students   matric number  BU/<entry year>/<programme code>/<serial>, e.g. BU/26/CSC/0012
           Student ID     STU0000123 (permanent, set on StudentProfile)
Staff      staff number   SP/<serial from 1001>, e.g. SP/1017
Admins     admin number   SA/<serial>, e.g. SA/0002
Applicants application    BU/APP/<session>/<serial> (see apps.admissions)
"""

from django.db import IntegrityError, transaction
from django.utils import timezone

ATTEMPTS = 5


def _next(prefix, first=1):
    """The next free serial after `prefix`, looking at numbers already issued."""
    from .models import User

    taken = User.objects.filter(university_id__startswith=prefix).values_list("university_id", flat=True)
    serials = [int(n[len(prefix) :]) for n in taken if n[len(prefix) :].isdigit()]
    return max(serials, default=first - 1) + 1


def matric_number(programme, entry_session=""):
    year = (entry_session or "")[:4] or str(timezone.localdate().year)
    prefix = f"BU/{year[2:4]}/{programme.code}/"
    return f"{prefix}{_next(prefix):04d}"


def staff_number():
    return f"SP/{_next('SP/', first=1001)}"


def admin_number():
    return f"SA/{_next('SA/'):04d}"


def save_with_number(obj, field, make_number, save):
    """Set obj.<field> = make_number() and save. If another request took the same number at the same moment,
    the database's unique constraint refuses it; take the next one and try again."""
    for attempt in range(ATTEMPTS):
        setattr(obj, field, make_number())
        try:
            with transaction.atomic():
                save()
            return
        except IntegrityError:
            if attempt == ATTEMPTS - 1:
                raise

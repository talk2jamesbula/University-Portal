"""Give existing Lecturer and Examination Officer roles the new exams.invigilate permission.

New databases get it from accounts.rbac.DEFAULT_ROLES; roles created before this module existed
(and possibly edited since) are only extended, never overwritten.
"""

from django.db import migrations

ROLES = ("lecturer", "exam_officer")
PERMISSION = "exams.invigilate"


def grant(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    for role in Role.objects.filter(code__in=ROLES):
        if PERMISSION not in role.permissions:
            role.permissions = sorted([*role.permissions, PERMISSION])
            role.save(update_fields=["permissions"])


def revoke(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    for role in Role.objects.filter(code__in=ROLES):
        role.permissions = [p for p in role.permissions if p != PERMISSION]
        role.save(update_fields=["permissions"])


class Migration(migrations.Migration):
    dependencies = [
        ("exams", "0001_initial"),
        ("accounts", "0001_initial"),
    ]

    operations = [migrations.RunPython(grant, revoke)]

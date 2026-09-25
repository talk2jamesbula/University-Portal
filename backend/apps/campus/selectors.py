from django.db.models import Q

from apps.academics.models import CourseOffering, Enrollment

from .models import Announcement


def my_offerings(user):
    """Course offerings a user teaches (staff) or is registered for (students)."""
    if user.is_student:
        return CourseOffering.objects.filter(
            enrollments__student=user, enrollments__status=Enrollment.Status.REGISTERED
        )
    return CourseOffering.objects.filter(lecturer=user)


def visible_announcements(user):
    """University-wide news for the user's audience, plus their department's and their courses'."""
    qs = Announcement.objects.select_related("author", "offering__course", "department")
    if user.has_permission("communications.send"):
        return qs
    general = Q(offering__isnull=True, department__isnull=True, audience__in=[Announcement.Audience.ALL, user.role])
    department = Q(department_id=user.department_id) if user.department_id else Q(pk__in=[])
    return qs.filter(general | department | Q(offering__in=my_offerings(user))).distinct()

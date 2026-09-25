from django.contrib import admin
from django.contrib.auth import get_user_model

from apps.finance.services import assess_semester_fees

from .models import Course, CourseOffering, Department, Enrollment, Faculty, Programme, ProgrammeCourse, Semester


@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ["code", "name"]
    search_fields = ["code", "name"]


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "faculty"]
    list_filter = ["faculty"]
    search_fields = ["code", "name"]


class CurriculumInline(admin.TabularInline):
    model = ProgrammeCourse
    autocomplete_fields = ["course"]
    extra = 0


@admin.register(Programme)
class ProgrammeAdmin(admin.ModelAdmin):
    list_display = ["code", "title", "department", "duration_years", "is_active"]
    list_filter = ["department__faculty", "degree", "is_active"]
    search_fields = ["code", "name"]
    inlines = [CurriculumInline]


@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "start_date",
        "end_date",
        "is_current",
        "registration_open",
        "tuition_per_unit",
        "fee_due_date",
    ]
    list_editable = ["is_current", "registration_open"]
    list_filter = ["session", "number"]
    actions = ["recalculate_fees"]

    @admin.action(description="Recalculate tuition and fees for registered students")
    def recalculate_fees(self, request, queryset):
        count = 0
        for semester in queryset:
            registered = Enrollment.objects.filter(offering__semester=semester).values("student")
            for student in get_user_model().objects.filter(pk__in=registered):
                assess_semester_fees(student, semester)
                count += 1
        self.message_user(request, f"Recalculated fees for {count} student accounts.")


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ["code", "title", "department", "units", "level", "semester_number", "is_active"]
    list_filter = ["level", "semester_number", "department__faculty", "department"]
    search_fields = ["code", "title"]


@admin.register(CourseOffering)
class CourseOfferingAdmin(admin.ModelAdmin):
    list_display = ["course", "semester", "lecturer", "capacity", "days", "venue"]
    list_filter = ["semester", "course__department"]
    search_fields = ["course__code", "course__title"]
    autocomplete_fields = ["course", "lecturer"]


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ["student", "offering", "status", "ca_score", "exam_score", "result_status", "is_carryover"]
    list_filter = ["status", "result_status", "offering__semester"]
    search_fields = ["student__university_id", "student__last_name", "offering__course__code"]
    raw_id_fields = ["student", "offering"]

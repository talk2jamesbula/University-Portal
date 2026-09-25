from django.contrib import admin

from .models import Attempt, Candidate, Exam, Question, Venue


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "capacity", "is_cbt_centre", "is_active"]
    list_filter = ["is_cbt_centre", "is_active"]
    search_fields = ["code", "name"]


class CandidateInline(admin.TabularInline):
    model = Candidate
    extra = 0
    raw_id_fields = ["student", "waived_by", "checked_in_by"]


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ["offering", "date", "start_time", "duration_minutes", "mode", "status"]
    list_filter = ["status", "mode", "offering__semester"]
    search_fields = ["offering__course__code", "offering__course__title"]
    filter_horizontal = ["venues"]
    raw_id_fields = ["offering"]
    inlines = [CandidateInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ["__str__", "exam", "marks", "order"]
    list_filter = ["exam__offering__semester"]


@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = ["student", "exam", "status", "score", "max_score", "focus_losses", "started_at"]
    list_filter = ["status", "exam__offering__semester"]
    raw_id_fields = ["student", "exam"]
    readonly_fields = ["question_ids", "choice_order"]

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import LoginEvent, Role, RoleAssignment, StaffProfile, StudentProfile, User


class StudentProfileInline(admin.StackedInline):
    model = StudentProfile
    can_delete = False
    autocomplete_fields = ["programme"]
    extra = 0


class StaffProfileInline(admin.StackedInline):
    model = StaffProfile
    can_delete = False
    extra = 0


class RoleAssignmentInline(admin.TabularInline):
    model = RoleAssignment
    extra = 0


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["username", "get_full_name", "email", "role", "university_id", "department", "is_active"]
    list_filter = ["role", "department", "is_active"]
    search_fields = ["username", "first_name", "last_name", "email", "university_id"]
    fieldsets = BaseUserAdmin.fieldsets + (
        ("University", {"fields": ("role", "title", "university_id", "department", "phone", "bio")}),
    )
    # Matric, staff and admin numbers are assigned by the system when the record is saved.
    readonly_fields = ["university_id"]
    inlines = [StudentProfileInline, StaffProfileInline, RoleAssignmentInline]


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "scope", "is_system"]
    readonly_fields = ["is_system"]


@admin.register(LoginEvent)
class LoginEventAdmin(admin.ModelAdmin):
    list_display = ["created_at", "username", "successful", "ip_address"]
    list_filter = ["successful"]
    search_fields = ["username", "ip_address"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

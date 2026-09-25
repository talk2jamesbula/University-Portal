from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import LoginEvent, Role, RoleAssignment, StaffProfile, StudentProfile
from .rbac import PERMISSIONS

User = get_user_model()

# What a student may change on their own record; the rest is maintained by the Registry.
STUDENT_EDITABLE = [
    "home_address",
    "next_of_kin_name",
    "next_of_kin_relationship",
    "next_of_kin_phone",
    "next_of_kin_address",
    "emergency_contact_name",
    "emergency_contact_relationship",
    "emergency_contact_phone",
]


class StudentProfileSerializer(serializers.ModelSerializer):
    programme_title = serializers.CharField(source="programme.title", read_only=True)
    department_name = serializers.CharField(source="programme.department.name", read_only=True)
    faculty_name = serializers.CharField(source="programme.department.faculty.name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    mode_of_entry_label = serializers.CharField(source="get_mode_of_entry_display", read_only=True)

    class Meta:
        model = StudentProfile
        exclude = ["id", "user"]


class OwnStudentProfileSerializer(StudentProfileSerializer):
    class Meta(StudentProfileSerializer.Meta):
        read_only_fields = [f.name for f in StudentProfile._meta.fields if f.name not in STUDENT_EDITABLE]


class StaffProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffProfile
        exclude = ["id", "user"]


class RoleAssignmentSerializer(serializers.ModelSerializer):
    role_code = serializers.CharField(source="role.code", read_only=True)
    role_name = serializers.CharField(source="role.name", read_only=True)
    user_name = serializers.CharField(source="user.get_full_name", read_only=True)
    faculty_name = serializers.CharField(source="faculty.name", read_only=True, default=None)
    department_name = serializers.CharField(source="department.name", read_only=True, default=None)

    class Meta:
        model = RoleAssignment
        fields = [
            "id",
            "user",
            "user_name",
            "role",
            "role_code",
            "role_name",
            "faculty",
            "faculty_name",
            "department",
            "department_name",
            "assigned_at",
        ]
        read_only_fields = ["assigned_at"]

    def validate(self, attrs):
        user, role = attrs.get("user"), attrs.get("role")
        if user and not user.is_staff_member:
            raise serializers.ValidationError({"user": "Roles can only be given to staff."})
        if role and role.scope == Role.Scope.FACULTY and not attrs.get("faculty"):
            raise serializers.ValidationError({"faculty": f"Choose the faculty this {role.name} is responsible for."})
        if role and role.scope == Role.Scope.DEPARTMENT and not attrs.get("department"):
            raise serializers.ValidationError({"department": f"Choose the department this {role.name} heads."})
        return attrs


class RoleSerializer(serializers.ModelSerializer):
    holders = serializers.IntegerField(read_only=True, default=None)

    class Meta:
        model = Role
        fields = ["id", "code", "name", "scope", "permissions", "is_system", "holders"]
        read_only_fields = ["is_system"]

    def validate_permissions(self, value):
        unknown = set(value) - set(PERMISSIONS)
        if unknown:
            raise serializers.ValidationError(f"Unknown permissions: {', '.join(sorted(unknown))}")
        return sorted(set(value))


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="get_full_name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True, default=None)
    avatar_url = serializers.CharField(read_only=True)
    password = serializers.CharField(write_only=True, required=False, validators=[validate_password])
    roles = serializers.ListField(source="role_codes", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "title",
            "first_name",
            "last_name",
            "full_name",
            "role",
            "university_id",
            "department",
            "department_name",
            "phone",
            "bio",
            "avatar_url",
            "roles",
            "is_active",
            "date_joined",
            "last_login",
            "password",
        ]
        read_only_fields = ["date_joined", "last_login", "university_id"]  # assigned automatically

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        instance = super().update(instance, validated_data)
        if password:
            instance.set_password(password)
            instance.save(update_fields=["password"])
        return instance


class MeSerializer(UserSerializer):
    """The signed-in user: identity, what they may do, and their student or staff record."""

    permissions = serializers.SerializerMethodField()
    assignments = RoleAssignmentSerializer(source="role_assignments", many=True, read_only=True)
    student_profile = StudentProfileSerializer(read_only=True, default=None)
    staff_profile = StaffProfileSerializer(read_only=True, default=None)

    class Meta(UserSerializer.Meta):
        fields = [f for f in UserSerializer.Meta.fields if f not in ("password", "is_active")] + [
            "permissions",
            "assignments",
            "student_profile",
            "staff_profile",
        ]
        # Names, IDs and departments are maintained by the Registry.
        read_only_fields = [
            "username",
            "role",
            "university_id",
            "department",
            "title",
            "first_name",
            "last_name",
            "date_joined",
            "last_login",
        ]

    def get_permissions(self, obj):
        return sorted(obj.permission_codes)


class DirectorySerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="get_full_name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True, default=None)
    designation = serializers.CharField(source="staff_profile.designation", read_only=True, default="")
    avatar_url = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "full_name",
            "email",
            "phone",
            "role",
            "designation",
            "department",
            "department_name",
            "bio",
            "avatar_url",
        ]


class LoginEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoginEvent
        fields = ["id", "user", "username", "successful", "ip_address", "user_agent", "created_at"]


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_current_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate_new_password(self, value):
        validate_password(value, self.context["request"].user)
        return value

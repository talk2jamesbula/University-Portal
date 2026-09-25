import re

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from apps.academics.models import Programme
from apps.accounts.models import StudentProfile

from .models import StatusChange, StudentDocument

User = get_user_model()
PHONE = re.compile(r"^\+?\d[\d ]{9,15}$")
SESSION = re.compile(r"^(\d{4})/(\d{4})$")
MAX_DOCUMENT_SIZE = 5 * 1024 * 1024
SIGNATURES = {
    b"%PDF-": ("application/pdf", "pdf"),
    b"\xff\xd8\xff": ("image/jpeg", "jpg"),
    b"\x89PNG\r\n\x1a\n": ("image/png", "png"),
}


def validate_session(value):
    match = SESSION.match(value or "")
    if value and (not match or int(match[2]) != int(match[1]) + 1):
        raise serializers.ValidationError("Use the form 2026/2027.")
    return value


def validate_phone(value):
    if value and not PHONE.match(value):
        raise serializers.ValidationError("Enter a valid phone number, e.g. 08031234567.")
    return value.replace(" ", "")


class StudentListSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="get_full_name", read_only=True)
    matric_number = serializers.CharField(source="university_id", read_only=True)
    student_id = serializers.CharField(source="student_profile.student_id", read_only=True)
    programme = serializers.CharField(source="student_profile.programme.title", read_only=True)
    department = serializers.CharField(source="student_profile.programme.department.name", read_only=True)
    faculty = serializers.CharField(source="student_profile.programme.department.faculty.name", read_only=True)
    level = serializers.IntegerField(source="student_profile.level", read_only=True)
    status = serializers.CharField(source="student_profile.status", read_only=True)
    status_label = serializers.CharField(source="student_profile.get_status_display", read_only=True)
    gender = serializers.CharField(source="student_profile.gender", read_only=True)
    current_session = serializers.CharField(source="student_profile.current_session", read_only=True)
    avatar_url = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "full_name",
            "first_name",
            "last_name",
            "matric_number",
            "student_id",
            "email",
            "phone",
            "avatar_url",
            "programme",
            "department",
            "faculty",
            "level",
            "status",
            "status_label",
            "gender",
            "current_session",
            "is_active",
        ]


class StudentDetailSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="get_full_name", read_only=True)
    matric_number = serializers.CharField(source="university_id", read_only=True)
    avatar_url = serializers.CharField(read_only=True)
    profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "full_name",
            "first_name",
            "last_name",
            "matric_number",
            "email",
            "phone",
            "avatar_url",
            "is_active",
            "date_joined",
            "last_login",
            "profile",
        ]

    def get_profile(self, obj):
        p = obj.student_profile
        department = p.programme.department
        data = {
            f.name: getattr(p, f.name) for f in StudentProfile._meta.fields if f.name not in ("id", "user", "programme")
        }
        return {
            **data,
            "programme": p.programme_id,
            "programme_title": p.programme.title,
            "programme_code": p.programme.code,
            "duration_years": p.programme.duration_years,
            "department": department.id,
            "department_name": department.name,
            "faculty": department.faculty_id,
            "faculty_name": department.faculty.name,
            "status_label": p.get_status_display(),
            "mode_of_entry_label": p.get_mode_of_entry_display(),
            "gender_label": p.get_gender_display(),
        }


class StudentWriteSerializer(serializers.Serializer):
    """Create or edit a student: account details and the student record together."""

    first_name = serializers.CharField(max_length=60)
    last_name = serializers.CharField(max_length=60)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")

    programme = serializers.PrimaryKeyRelatedField(queryset=Programme.objects.select_related("department"))
    level = serializers.IntegerField()
    current_session = serializers.CharField(max_length=9)
    entry_session = serializers.CharField(max_length=9)
    mode_of_entry = serializers.ChoiceField(choices=StudentProfile.Entry.choices, default=StudentProfile.Entry.UTME)
    admission_date = serializers.DateField(required=False, allow_null=True)
    jamb_reg_number = serializers.CharField(max_length=16, required=False, allow_blank=True, default="")

    gender = serializers.ChoiceField(choices=StudentProfile.Gender.choices)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    nationality = serializers.CharField(max_length=60, required=False, default="Nigerian")
    state_of_origin = serializers.CharField(max_length=40, required=False, allow_blank=True, default="")
    lga = serializers.CharField(max_length=60, required=False, allow_blank=True, default="")
    home_address = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    country = serializers.CharField(max_length=60, required=False, default="Nigeria")

    next_of_kin_name = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    next_of_kin_relationship = serializers.CharField(max_length=40, required=False, allow_blank=True, default="")
    next_of_kin_phone = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    next_of_kin_address = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    emergency_contact_name = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    emergency_contact_relationship = serializers.CharField(max_length=40, required=False, allow_blank=True, default="")
    emergency_contact_phone = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")

    validate_phone = staticmethod(validate_phone)
    validate_next_of_kin_phone = staticmethod(validate_phone)
    validate_emergency_contact_phone = staticmethod(validate_phone)
    validate_current_session = staticmethod(validate_session)
    validate_entry_session = staticmethod(validate_session)

    def _others(self):
        qs = User.objects.all()
        return qs.exclude(pk=self.instance.pk) if self.instance else qs

    def validate_first_name(self, value):
        return value.strip()

    validate_last_name = validate_first_name

    def validate_email(self, value):
        value = value.strip().lower()
        if self._others().filter(email__iexact=value).exists():
            raise serializers.ValidationError("Another account already uses this email address.")
        return value

    def validate_jamb_reg_number(self, value):
        value = value.strip().upper()
        if value and not re.fullmatch(r"\d{8}[A-Z]{2}", value):
            raise serializers.ValidationError("A JAMB registration number is 8 digits and 2 letters, e.g. 20261234AB.")
        return value

    def validate_date_of_birth(self, value):
        if value:
            today = timezone.localdate()
            age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
            if not 14 <= age <= 80:
                raise serializers.ValidationError("Check the date of birth.")
        return value

    def validate_admission_date(self, value):
        if value and value > timezone.localdate():
            raise serializers.ValidationError("The admission date can't be in the future.")
        return value

    def validate(self, attrs):
        programme = attrs.get("programme")
        level = attrs.get("level")
        if programme and level is not None:
            # Up to two extra years for students spilling over.
            highest = (programme.duration_years + 2) * 100
            if level % 100 or not 100 <= level <= highest:
                raise serializers.ValidationError(
                    {"level": f"Choose a level from 100 to {highest} for {programme.title}."}
                )
        if not self.instance and programme and not programme.is_active:
            raise serializers.ValidationError({"programme": f"{programme.title} is not admitting students."})
        entry, current = attrs.get("entry_session"), attrs.get("current_session")
        if entry and current and current < entry:
            raise serializers.ValidationError(
                {"current_session": "The current session can't be before the entry session."}
            )
        return attrs


class StatusChangeSerializer(serializers.ModelSerializer):
    from_label = serializers.CharField(source="get_from_status_display", read_only=True)
    to_label = serializers.CharField(source="get_to_status_display", read_only=True)
    changed_by_name = serializers.CharField(source="changed_by.get_full_name", read_only=True, default=None)

    class Meta:
        model = StatusChange
        fields = [
            "id",
            "from_status",
            "from_label",
            "to_status",
            "to_label",
            "reason",
            "effective_date",
            "changed_by_name",
            "created_at",
        ]


class StatusChangeRequestSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=StudentProfile.Status.choices)
    reason = serializers.CharField(min_length=5, max_length=300)
    effective_date = serializers.DateField(required=False)


class ActivationSerializer(serializers.Serializer):
    active = serializers.BooleanField()
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class DocumentSerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    uploaded_by_name = serializers.CharField(source="uploaded_by.get_full_name", read_only=True, default=None)

    class Meta:
        model = StudentDocument
        fields = [
            "id",
            "kind",
            "kind_label",
            "title",
            "original_filename",
            "content_type",
            "size",
            "uploaded_by_name",
            "uploaded_at",
        ]


class DocumentUploadSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=StudentDocument.Kind.choices)
    title = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    file = serializers.FileField()

    def validate_file(self, upload):
        if upload.size > MAX_DOCUMENT_SIZE:
            raise serializers.ValidationError("File is too large. The maximum size is 5 MB.")
        head = upload.read(8)
        upload.seek(0)
        for signature, (content_type, ext) in SIGNATURES.items():
            if head.startswith(signature):
                upload.name = f"{upload.name.rsplit('.', 1)[0][:180]}.{ext}"
                self.content_type = content_type
                return upload
        raise serializers.ValidationError("Upload a PDF, JPG or PNG file.")

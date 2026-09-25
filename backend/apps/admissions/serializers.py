import re

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import serializers

from apps.academics.models import Programme

from . import services
from .models import AdmissionCycle, Application, ApplicationDocument, ApplicationEvent, ApplicationPayment

User = get_user_model()

MAX_DOCUMENT_SIZE = 5 * 1024 * 1024
# Identify uploads by their first bytes rather than trusting the filename or browser.
SIGNATURES = {
    b"%PDF-": ("application/pdf", "pdf"),
    b"\xff\xd8\xff": ("image/jpeg", "jpg"),
    b"\x89PNG\r\n\x1a\n": ("image/png", "png"),
}
PHONE = re.compile(r"^\+?\d[\d ]{9,15}$")


# --- Accounts -----------------------------------------------------------------------------------


class ApplicantSignupSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=60)
    last_name = serializers.CharField(max_length=60)
    email = serializers.EmailField()
    phone = serializers.RegexField(PHONE, error_messages={"invalid": "Enter a valid phone number, e.g. 08031234567."})
    password = serializers.CharField(write_only=True, min_length=8, style={"input_type": "password"})

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists() or User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists. Sign in instead.")
        return value

    def validate(self, attrs):
        user = User(
            username=attrs["email"], email=attrs["email"], first_name=attrs["first_name"], last_name=attrs["last_name"]
        )
        validate_password(attrs["password"], user)
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data["email"],
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=validated_data["first_name"].strip(),
            last_name=validated_data["last_name"].strip(),
            phone=validated_data["phone"].replace(" ", ""),
            role=User.Role.APPLICANT,
        )


# --- Cycles -------------------------------------------------------------------------------------


class CycleSerializer(serializers.ModelSerializer):
    is_open = serializers.BooleanField(read_only=True)

    class Meta:
        model = AdmissionCycle
        fields = [
            "id",
            "session",
            "application_fee",
            "opens_on",
            "closes_on",
            "min_utme_score",
            "resumption_date",
            "acceptance_deadline",
            "is_active",
            "is_open",
        ]

    def validate_session(self, value):
        match = re.fullmatch(r"(\d{4})/(\d{4})", value)
        if not match or int(match[2]) != int(match[1]) + 1:
            raise serializers.ValidationError("Use the form 2026/2027.")
        return value

    def validate(self, attrs):
        opens = attrs.get("opens_on", getattr(self.instance, "opens_on", None))
        closes = attrs.get("closes_on", getattr(self.instance, "closes_on", None))
        if opens and closes and closes < opens:
            raise serializers.ValidationError({"closes_on": "Applications must close after they open."})
        if attrs.get("is_active"):
            others = AdmissionCycle.objects.filter(is_active=True)
            if self.instance:
                others = others.exclude(pk=self.instance.pk)
            if others.exists():
                raise serializers.ValidationError(
                    {"is_active": "Another admission cycle is active. Deactivate it first."}
                )
        return attrs


# --- Application parts --------------------------------------------------------------------------


class DocumentSerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    reviewed_by_name = serializers.CharField(source="reviewed_by.get_full_name", read_only=True, default=None)

    class Meta:
        model = ApplicationDocument
        fields = [
            "id",
            "kind",
            "kind_label",
            "original_filename",
            "content_type",
            "size",
            "status",
            "status_label",
            "review_note",
            "reviewed_by_name",
            "reviewed_at",
            "uploaded_at",
        ]
        read_only_fields = fields


class DocumentUploadSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=ApplicationDocument.Kind.choices)
    file = serializers.FileField()

    def validate_file(self, upload):
        if upload.size > MAX_DOCUMENT_SIZE:
            raise serializers.ValidationError("File is too large. The maximum size is 5 MB.")
        head = upload.read(8)
        upload.seek(0)
        for signature, (content_type, ext) in SIGNATURES.items():
            if head.startswith(signature):
                # Keep the applicant's filename for display, with the extension matching the real content.
                upload.name = f"{upload.name.rsplit('.', 1)[0][:180]}.{ext}"
                self.content_type = content_type
                return upload
        raise serializers.ValidationError("Upload a PDF, JPG or PNG file.")

    def validate(self, attrs):
        if attrs["kind"] == ApplicationDocument.Kind.PASSPORT and self.content_type == "application/pdf":
            raise serializers.ValidationError({"file": "Upload your passport photograph as a JPG or PNG image."})
        return attrs


class PaymentSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = ApplicationPayment
        fields = [
            "id",
            "reference",
            "amount",
            "gateway",
            "status",
            "status_label",
            "channel",
            "gateway_response",
            "created_at",
            "paid_at",
        ]
        read_only_fields = fields


class EventSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()
    to_status_label = serializers.SerializerMethodField()

    class Meta:
        model = ApplicationEvent
        fields = [
            "id",
            "action",
            "from_status",
            "to_status",
            "to_status_label",
            "actor_name",
            "note",
            "public",
            "created_at",
        ]

    def get_actor_name(self, obj):
        if not obj.actor:
            return "System"
        return (
            "You"
            if obj.actor_id == obj.application.applicant_id and self.context.get("applicant_view")
            else obj.actor.get_full_name()
        )

    def get_to_status_label(self, obj):
        return Application.Status(obj.to_status).label if obj.to_status else ""


class OLevelSerializer(serializers.Serializer):
    exam = serializers.ChoiceField(choices=services.EXAMS)
    year = serializers.IntegerField(min_value=1980)
    subject = serializers.CharField(max_length=60)
    grade = serializers.ChoiceField(choices=services.GRADES)

    def validate_year(self, value):
        if value > timezone.localdate().year:
            raise serializers.ValidationError("The exam year can't be in the future.")
        return value


PERSONAL = [
    "middle_name",
    "gender",
    "date_of_birth",
    "nationality",
    "state_of_origin",
    "lga",
    "address",
    "phone",
    "nin",
    "next_of_kin_name",
    "next_of_kin_relationship",
    "next_of_kin_phone",
]
ACADEMIC = [
    "entry_mode",
    "jamb_reg_number",
    "utme_score",
    "olevel_results",
    "previous_institution",
    "previous_qualification",
]


class ApplicationSerializer(serializers.ModelSerializer):
    """What the applicant sees and edits (edits only while it's a draft)."""

    status_label = serializers.CharField(source="get_status_display", read_only=True)
    entry_mode_label = serializers.CharField(source="get_entry_mode_display", read_only=True)
    programme_name = serializers.CharField(source="programme.title", read_only=True, default=None)
    second_choice_name = serializers.CharField(source="second_choice.title", read_only=True, default=None)
    admitted_programme_name = serializers.CharField(source="admitted_programme.title", read_only=True, default=None)
    programme = serializers.PrimaryKeyRelatedField(
        queryset=Programme.objects.filter(is_active=True), allow_null=True, required=False
    )
    second_choice = serializers.PrimaryKeyRelatedField(
        queryset=Programme.objects.filter(is_active=True), allow_null=True, required=False
    )
    olevel_results = OLevelSerializer(many=True, required=False)
    applicant_name = serializers.CharField(source="applicant.get_full_name", read_only=True)
    email = serializers.EmailField(source="applicant.email", read_only=True)
    fee_paid = serializers.BooleanField(read_only=True)
    session = serializers.CharField(source="cycle.session", read_only=True)

    class Meta:
        model = Application
        fields = [
            "id",
            "number",
            "session",
            "status",
            "status_label",
            "applicant_name",
            "email",
            *PERSONAL,
            *ACADEMIC,
            "entry_mode_label",
            "programme",
            "programme_name",
            "second_choice",
            "second_choice_name",
            "admitted_programme",
            "admitted_programme_name",
            "decision_note",
            "letter_number",
            "letter_issued_at",
            "accepted_at",
            "submitted_at",
            "fee_paid",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "number",
            "status",
            "admitted_programme",
            "decision_note",
            "letter_number",
            "letter_issued_at",
            "accepted_at",
            "submitted_at",
        ]

    def validate_date_of_birth(self, value):
        if value:
            today = timezone.localdate()
            age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
            if not 14 <= age <= 70:
                raise serializers.ValidationError("Check your date of birth.")
        return value

    def validate_nin(self, value):
        if value and not re.fullmatch(r"\d{11}", value):
            raise serializers.ValidationError("The NIN has 11 digits.")
        return value

    def validate_phone(self, value):
        if value and not PHONE.match(value):
            raise serializers.ValidationError("Enter a valid phone number, e.g. 08031234567.")
        return value.replace(" ", "")

    validate_next_of_kin_phone = validate_phone

    def validate_jamb_reg_number(self, value):
        value = value.strip().upper()
        if value and not re.fullmatch(r"\d{8}[A-Z]{2}", value):
            raise serializers.ValidationError("A JAMB registration number is 8 digits and 2 letters, e.g. 20261234AB.")
        if value and self.instance:
            clash = Application.objects.filter(cycle=self.instance.cycle, jamb_reg_number=value).exclude(
                pk=self.instance.pk
            )
            if clash.exists():
                raise serializers.ValidationError("Another application already uses this JAMB registration number.")
        return value

    def validate_olevel_results(self, value):
        subjects = [r["subject"].strip().lower() for r in value]
        if len(subjects) != len(set(subjects)):
            raise serializers.ValidationError("Each subject may only be listed once; list your best grade.")
        if len(value) > 12:
            raise serializers.ValidationError("List at most 12 subjects.")
        return value

    def update(self, instance, validated_data):
        if instance.status != Application.Status.DRAFT:
            raise serializers.ValidationError("A submitted application can't be changed.")
        results = validated_data.pop("olevel_results", None)
        if results is not None:  # a JSON field edited through a nested serializer
            instance.olevel_results = [{**r, "subject": r["subject"].strip()} for r in results]
        return super().update(instance, validated_data)


def applicant_payload(application, request):
    """The applicant's view: application, checklist, documents, fee payments and public timeline."""
    return {
        "application": ApplicationSerializer(application, context={"request": request}).data,
        "checklist": services.checklist(application),
        "documents": DocumentSerializer(application.documents.all(), many=True).data,
        "required_documents": list(ApplicationDocument.REQUIRED),
        "payments": PaymentSerializer(application.payments.all(), many=True).data,
        "timeline": EventSerializer(
            application.events.filter(public=True).select_related("actor", "application"),
            many=True,
            context={"applicant_view": True},
        ).data,
        "can_replace": [
            k for k, _ in ApplicationDocument.Kind.choices if services.can_replace_document(application, k)
        ],
    }


# --- Admissions Office --------------------------------------------------------------------------


class ApplicationListSerializer(serializers.ModelSerializer):
    applicant_name = serializers.CharField(source="applicant.get_full_name", read_only=True)
    email = serializers.EmailField(source="applicant.email", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    programme_name = serializers.CharField(source="programme.title", read_only=True, default=None)
    faculty_name = serializers.CharField(source="programme.department.faculty.name", read_only=True, default=None)
    aggregate_score = serializers.FloatField(read_only=True)
    fee_paid = serializers.BooleanField(source="paid", read_only=True)
    documents_pending = serializers.IntegerField(read_only=True)
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = [
            "id",
            "number",
            "applicant_name",
            "email",
            "avatar_url",
            "status",
            "status_label",
            "entry_mode",
            "programme",
            "programme_name",
            "faculty_name",
            "state_of_origin",
            "utme_score",
            "screening_score",
            "aggregate_score",
            "fee_paid",
            "documents_pending",
            "submitted_at",
        ]

    def get_avatar_url(self, obj):
        passport = next((d for d in obj.documents.all() if d.kind == ApplicationDocument.Kind.PASSPORT), None)
        return f"/api/admissions/documents/{passport.pk}/file/" if passport else None


class OfficerApplicationSerializer(ApplicationSerializer):
    reviewer_name = serializers.CharField(source="reviewer.get_full_name", read_only=True, default=None)
    screened_by_name = serializers.CharField(source="screened_by.get_full_name", read_only=True, default=None)
    decided_by_name = serializers.CharField(source="decided_by.get_full_name", read_only=True, default=None)
    aggregate_score = serializers.FloatField(read_only=True)
    min_utme_score = serializers.IntegerField(source="cycle.min_utme_score", read_only=True)
    applicant_phone = serializers.CharField(source="applicant.phone", read_only=True)

    class Meta(ApplicationSerializer.Meta):
        fields = ApplicationSerializer.Meta.fields + [
            "reviewer_name",
            "screening_score",
            "screening_remarks",
            "screened_by_name",
            "screened_at",
            "decided_by_name",
            "decided_at",
            "aggregate_score",
            "min_utme_score",
            "applicant_phone",
        ]
        read_only_fields = fields


class DocumentReviewSerializer(serializers.Serializer):
    verified = serializers.BooleanField()
    note = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class ScreeningSerializer(serializers.Serializer):
    score = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=100)
    remarks = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class DecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=list(services.DECISIONS))
    note = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")
    programme = serializers.PrimaryKeyRelatedField(queryset=Programme.objects.all(), required=False, allow_null=True)

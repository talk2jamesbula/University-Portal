import re

from django.db import transaction
from rest_framework import serializers

from .models import Course, CourseOffering, Department, Enrollment, Faculty, Programme, ProgrammeCourse, Semester


class FacultySerializer(serializers.ModelSerializer):
    department_count = serializers.IntegerField(read_only=True, default=None)

    class Meta:
        model = Faculty
        fields = ["id", "code", "name", "description", "department_count"]


class DepartmentSerializer(serializers.ModelSerializer):
    faculty_name = serializers.CharField(source="faculty.name", read_only=True)
    programme_count = serializers.IntegerField(read_only=True, default=None)

    class Meta:
        model = Department
        fields = ["id", "code", "name", "description", "faculty", "faculty_name", "programme_count"]


class ProgrammeSerializer(serializers.ModelSerializer):
    title = serializers.CharField(read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    faculty_name = serializers.CharField(source="department.faculty.name", read_only=True)

    class Meta:
        model = Programme
        fields = [
            "id",
            "code",
            "name",
            "title",
            "degree",
            "duration_years",
            "description",
            "is_active",
            "department",
            "department_name",
            "faculty_name",
        ]


class SemesterSerializer(serializers.ModelSerializer):
    name = serializers.CharField(read_only=True)

    class Meta:
        model = Semester
        fields = [
            "id",
            "name",
            "session",
            "number",
            "start_date",
            "end_date",
            "is_current",
            "registration_open",
            "tuition_per_unit",
            "fee_due_date",
        ]

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and start >= end:
            raise serializers.ValidationError({"end_date": "The semester must end after it starts."})
        return attrs


COURSE_CODE = re.compile(r"[A-Z]{2,5}\d{3}[A-Z]?")


class CourseSerializer(serializers.ModelSerializer):
    department_code = serializers.CharField(source="department.code", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    semester_label = serializers.CharField(source="get_semester_number_display", read_only=True)
    programme_count = serializers.IntegerField(read_only=True, default=None)
    offering_count = serializers.IntegerField(read_only=True, default=None)

    class Meta:
        model = Course
        fields = [
            "id",
            "code",
            "title",
            "description",
            "units",
            "level",
            "semester_number",
            "semester_label",
            "is_active",
            "department",
            "department_code",
            "department_name",
            "programme_count",
            "offering_count",
        ]
        # validate_code() normalises the code first, then checks uniqueness with a clearer message.
        extra_kwargs = {"code": {"validators": []}}

    def validate_code(self, value):
        """Store codes in one form: "csc 207" -> "CSC207"."""
        code = re.sub(r"\s+", "", value).upper()
        if not COURSE_CODE.fullmatch(code):
            raise serializers.ValidationError("Use a code like CSC207: 2–5 letters then 3 digits.")
        existing = Course.objects.filter(code=code).exclude(pk=getattr(self.instance, "pk", None))
        if existing.exists():
            raise serializers.ValidationError(f"{code} already exists in the catalogue.")
        return code


class CurriculumEntrySerializer(serializers.Serializer):
    programme = serializers.PrimaryKeyRelatedField(queryset=Programme.objects.all())
    is_compulsory = serializers.BooleanField(default=True)


class NewOfferingSerializer(serializers.ModelSerializer):
    """Offering details given while creating a course (the course itself doesn't exist yet)."""

    class Meta:
        model = CourseOffering
        fields = ["semester", "lecturer", "capacity", "days", "start_time", "end_time", "venue"]

    def validate(self, attrs):
        return validate_offering_fields(attrs)


def validate_offering_fields(attrs, instance=None):
    """Checks shared by new and existing offerings: timetable, lecturer."""

    def get(field):
        return attrs.get(field, getattr(instance, field, None))

    days = [d for d in (get("days") or "").split(",") if d]
    unknown = set(days) - set(CourseOffering.Weekday.values)
    if unknown:
        raise serializers.ValidationError({"days": f"Unknown weekdays: {', '.join(sorted(unknown))}"})
    if "days" in attrs:
        # Keep a canonical order: "WED,MON" -> "MON,WED".
        attrs["days"] = ",".join(d for d in CourseOffering.Weekday.values if d in days)
    start, end = get("start_time"), get("end_time")
    if bool(start) != bool(end):
        raise serializers.ValidationError({"end_time": "Give both a start and an end time, or neither."})
    if start and end and start >= end:
        raise serializers.ValidationError({"end_time": "End time must be after start time."})
    if (start or days) and not (start and days):
        raise serializers.ValidationError({"days": "Choose the lecture days and times together."})
    lecturer = attrs.get("lecturer")
    if lecturer and not (lecturer.is_staff_member and lecturer.has_permission("courses.teach")):
        raise serializers.ValidationError({"lecturer": f"{lecturer} isn't a lecturer."})
    return attrs


class CourseCreateSerializer(CourseSerializer):
    """Create a catalogue course and, optionally, add it to curricula and offer it — all or nothing."""

    curriculum = CurriculumEntrySerializer(many=True, required=False, write_only=True)
    offering = NewOfferingSerializer(required=False, write_only=True, allow_null=True)

    class Meta(CourseSerializer.Meta):
        fields = [*CourseSerializer.Meta.fields, "curriculum", "offering"]

    def validate(self, attrs):
        programmes = [entry["programme"].pk for entry in attrs.get("curriculum", [])]
        if len(programmes) != len(set(programmes)):
            raise serializers.ValidationError({"curriculum": "Each programme can only be listed once."})
        offering = attrs.get("offering")
        number = attrs.get("semester_number", Course._meta.get_field("semester_number").default)
        if offering and offering["semester"].number != number:
            label = Semester.Number(number).label
            raise serializers.ValidationError({"offering": f"This is a {label} course; offer it in a {label}."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        curriculum = validated_data.pop("curriculum", [])
        offering = validated_data.pop("offering", None)
        course = Course.objects.create(**validated_data)
        ProgrammeCourse.objects.bulk_create(ProgrammeCourse(course=course, **entry) for entry in curriculum)
        if offering:
            CourseOffering.objects.create(course=course, **offering)
        return course


class ProgrammeCourseSerializer(serializers.ModelSerializer):
    course_detail = CourseSerializer(source="course", read_only=True)
    programme_title = serializers.CharField(source="programme.title", read_only=True)
    department_name = serializers.CharField(source="programme.department.name", read_only=True)

    class Meta:
        model = ProgrammeCourse
        fields = ["id", "programme", "programme_title", "department_name", "course", "course_detail", "is_compulsory"]


class OfferingSerializer(serializers.ModelSerializer):
    """A course offering with its catalogue details flattened in for convenience."""

    code = serializers.CharField(source="course.code", read_only=True)
    title = serializers.CharField(source="course.title", read_only=True)
    units = serializers.IntegerField(source="course.units", read_only=True)
    level = serializers.IntegerField(source="course.level", read_only=True)
    department_code = serializers.CharField(source="course.department.code", read_only=True)
    semester_name = serializers.CharField(source="semester.name", read_only=True)
    lecturer_name = serializers.CharField(source="lecturer.get_full_name", read_only=True, default=None)
    registered_count = serializers.IntegerField(read_only=True, default=None)
    seats_available = serializers.SerializerMethodField()

    class Meta:
        model = CourseOffering
        fields = [
            "id",
            "course",
            "code",
            "title",
            "units",
            "level",
            "department_code",
            "semester",
            "semester_name",
            "lecturer",
            "lecturer_name",
            "capacity",
            "registered_count",
            "seats_available",
            "days",
            "start_time",
            "end_time",
            "venue",
        ]

    def get_seats_available(self, obj):
        registered = getattr(obj, "registered_count", None)
        return None if registered is None else max(obj.capacity - registered, 0)

    def validate(self, attrs):
        attrs = validate_offering_fields(attrs, self.instance)
        course = attrs.get("course", getattr(self.instance, "course", None))
        semester = attrs.get("semester", getattr(self.instance, "semester", None))
        if course and semester and course.semester_number != semester.number:
            raise serializers.ValidationError(
                {"semester": f"{course.code} is a {course.get_semester_number_display()} course."}
            )
        return attrs


class RegistrationSerializer(serializers.ModelSerializer):
    """A student's registration for an offering, as the student sees it."""

    offering_detail = OfferingSerializer(source="offering", read_only=True)

    class Meta:
        model = Enrollment
        fields = ["id", "offering", "offering_detail", "status", "is_carryover", "registered_at"]


class RosterEntrySerializer(serializers.ModelSerializer):
    """A student on a class list, with their scores (for the lecturer and result officers)."""

    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    matric_number = serializers.CharField(source="student.university_id", read_only=True)
    student_email = serializers.CharField(source="student.email", read_only=True)
    student_avatar_url = serializers.CharField(source="student.avatar_url", read_only=True)
    level = serializers.IntegerField(source="student.student_profile.level", read_only=True, default=None)
    total_score = serializers.DecimalField(max_digits=5, decimal_places=1, read_only=True)
    grade = serializers.CharField(read_only=True)
    grade_points = serializers.IntegerField(read_only=True)

    class Meta:
        model = Enrollment
        fields = [
            "id",
            "student",
            "student_name",
            "matric_number",
            "student_email",
            "student_avatar_url",
            "level",
            "is_carryover",
            "ca_score",
            "exam_score",
            "total_score",
            "grade",
            "grade_points",
            "result_status",
        ]
        read_only_fields = fields

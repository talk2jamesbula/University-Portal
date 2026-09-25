"""Small factories for tests: build academic structure and users in one line each.

semester = make_semester()
student = make_student(programme=make_programme(), level=200)
lecturer = make_staff(roles=["lecturer"])
offering = make_offering(make_course(units=3), semester, lecturer=lecturer)
"""

from datetime import date, time
from itertools import count

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.academics.models import Course, CourseOffering, Department, Faculty, Programme, ProgrammeCourse, Semester
from apps.accounts.models import Role, RoleAssignment, StaffProfile, StudentProfile

User = get_user_model()
_seq = count(1)


def _n():
    return next(_seq)


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def make_faculty(**kw):
    n = _n()
    return Faculty.objects.create(**{"code": f"F{n}", "name": f"Faculty {n}", **kw})


def make_department(faculty=None, **kw):
    n = _n()
    fields = {"code": f"D{n}", "name": f"Department {n}", "faculty": faculty or make_faculty()}
    return Department.objects.create(**{**fields, **kw})


def make_programme(department=None, **kw):
    n = _n()
    fields = {"code": f"P{n}", "name": f"Programme {n}", "department": department or make_department()}
    return Programme.objects.create(**{**fields, **kw})


def make_semester(session="2026/2027", number=1, **kw):
    defaults = {
        "start_date": date(2026, 9, 1) if number == 1 else date(2027, 2, 1),
        "end_date": date(2027, 1, 30) if number == 1 else date(2027, 7, 1),
        "is_current": True,
        "registration_open": True,
        "tuition_per_unit": 100,
    }
    return Semester.objects.create(session=session, number=number, **{**defaults, **kw})


def make_course(department=None, *, units=3, level=100, semester_number=1, **kw):
    n = _n()
    return Course.objects.create(
        code=kw.pop("code", f"C{n:03d}"),
        title=kw.pop("title", f"Course {n}"),
        units=units,
        level=level,
        semester_number=semester_number,
        department=department or make_department(),
        **kw,
    )


def make_offering(course, semester, *, days="MON", hour=None, **kw):
    hour = hour if hour is not None else 8 + _n() % 9
    return CourseOffering.objects.create(
        course=course,
        semester=semester,
        days=days,
        start_time=time(hour),
        end_time=time(hour + 1),
        **kw,
    )


def add_to_curriculum(programme, *courses, compulsory=True):
    for course in courses:
        ProgrammeCourse.objects.create(programme=programme, course=course, is_compulsory=compulsory)


def make_student(username=None, *, programme=None, level=100, email="", **kw):
    n = _n()
    user = User.objects.create_user(
        username or f"student{n}",
        password="x",
        role=User.Role.STUDENT,
        email=email,
        university_id=f"BU/26/T/{n:04d}",
        **kw,
    )
    StudentProfile.objects.create(user=user, programme=programme or make_programme(), level=level)
    return user


def make_staff(username=None, *, roles=(), department=None, **kw):
    """roles: role codes, or (code, faculty_or_department) for scoped roles."""
    n = _n()
    user = User.objects.create_user(
        username or f"staff{n}",
        password="x",
        role=User.Role.STAFF,
        department=department,
        university_id=f"SP/T{n}",
        **kw,
    )
    StaffProfile.objects.create(user=user)
    for entry in roles:
        code, scope = entry if isinstance(entry, tuple) else (entry, None)
        role = Role.objects.get(code=code)
        RoleAssignment.objects.create(
            user=user,
            role=role,
            faculty=scope if role.scope == Role.Scope.FACULTY else None,
            department=scope if role.scope == Role.Scope.DEPARTMENT else None,
        )
    return user


def make_admin(username=None):
    return User.objects.create_user(username or f"admin{_n()}", password="x", role=User.Role.ADMIN)

"""Add demo examination data to a seeded database: venues and a published, clash-free exam timetable
for the current semester, with GST courses sat as computer-based tests.

    python manage.py seed_exams              # timetable in the last weeks of the semester
    python manage.py seed_exams --live-cbt   # also open the GST211 CBT now, to try it in the browser
"""

import random
from collections import Counter, defaultdict
from datetime import time, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.academics.models import CourseOffering, Enrollment, Semester
from apps.core.models import Notification
from apps.core.services import notify
from apps.exams import services
from apps.exams.models import Choice, Exam, Question, Venue

VENUES = [
    ("MAIN", "Main Auditorium", 400, "Senate Road", False),
    ("SCI-HALL", "Faculty of Science Exam Hall", 220, "Science Complex", False),
    ("LT1", "Lecture Theatre 1", 150, "Central Lecture Block", False),
    ("ICT-CBT", "ICT CBT Centre", 180, "ICT Building, ground floor", True),
]
SESSIONS = [time(9), time(14)]

# (question, [options], index of the correct option)
LOGIC_QUESTIONS = [
    (
        "Which branch of philosophy studies the nature of knowledge?",
        ["Ethics", "Epistemology", "Aesthetics", "Metaphysics"],
        1,
    ),
    (
        "An argument whose conclusion must be true if its premises are true is called…",
        ["Valid", "Sound", "Cogent", "Fallacious"],
        0,
    ),
    (
        "A valid argument with true premises is…",
        ["Strong", "Sound", "Inductive", "Circular"],
        1,
    ),
    (
        "“All men are mortal. Socrates is a man. Therefore Socrates is mortal.” This is an example of…",
        ["Induction", "Deduction", "Abduction", "Analogy"],
        1,
    ),
    (
        "Attacking the person instead of their argument is the fallacy of…",
        ["Straw man", "Ad hominem", "Begging the question", "False dilemma"],
        1,
    ),
    (
        "Which branch of philosophy is concerned with right and wrong conduct?",
        ["Logic", "Ethics", "Epistemology", "Ontology"],
        1,
    ),
    (
        "If “P → Q” is true and Q is false, then P is…",
        ["True", "False", "Undetermined", "Both true and false"],
        1,
    ),
    (
        "The statement “It is raining or it is not raining” is a…",
        ["Contradiction", "Tautology", "Contingency", "Fallacy"],
        1,
    ),
    (
        "Who wrote “The Republic”?",
        ["Aristotle", "Plato", "Socrates", "Kant"],
        1,
    ),
    (
        "Reasoning from specific observations to a general conclusion is…",
        ["Deduction", "Induction", "Syllogism", "Negation"],
        1,
    ),
    (
        "Presenting only two options when more exist is the fallacy of…",
        ["False dilemma", "Red herring", "Slippery slope", "Appeal to pity"],
        0,
    ),
    (
        "Metaphysics is mainly the study of…",
        ["Beauty", "Reality and existence", "Language", "Politics"],
        1,
    ),
]


class Command(BaseCommand):
    help = "Add demo exam venues and a published exam timetable for the current semester."

    def add_arguments(self, parser):
        parser.add_argument("--live-cbt", action="store_true", help="Open the GST211 CBT now so it can be sat.")

    @transaction.atomic
    def handle(self, *args, live_cbt=False, **options):
        semester = Semester.objects.filter(is_current=True).first()
        if semester is None:
            self.stderr.write("There is no current semester. Run seed_demo first.")
            return
        venues = {
            code: Venue.objects.get_or_create(
                code=code, defaults={"name": name, "capacity": seats, "location": where, "is_cbt_centre": cbt}
            )[0]
            for code, name, seats, where, cbt in VENUES
        }
        created = self.schedule(semester, venues)
        if live_cbt:
            self.open_cbt_now(semester)
        self.stdout.write(self.style.SUCCESS(f"Scheduled and published {created} exams for {semester}."))

    def schedule(self, semester, venues):
        offerings = list(
            CourseOffering.objects.filter(semester=semester, exam__isnull=True)
            .select_related("course")
            .annotate(students=Count("enrollments", filter=Q(enrollments__status=Enrollment.Status.REGISTERED)))
            .filter(students__gt=0)
            .order_by("-students", "course__code")
        )
        enrolled = defaultdict(set)
        for offering_id, student_id in Enrollment.objects.filter(
            offering__in=offerings, status=Enrollment.Status.REGISTERED
        ).values_list("offering_id", "student_id"):
            enrolled[offering_id].add(student_id)

        # Two sittings a weekday over the last three weeks of the semester.
        day, days = semester.end_date - timedelta(days=21), []
        while len(days) < 12:
            if day.weekday() < 5:
                days.append(day)
            day += timedelta(days=1)
        slots = [(d, t) for d in days for t in SESSIONS]
        in_slot, seats_used = defaultdict(set), defaultdict(Counter)
        halls = sorted((v for v in venues.values() if not v.is_cbt_centre), key=lambda v: -v.capacity)

        exams = []
        for offering in offerings:
            cbt = offering.course.code.startswith("GST")
            options = [venues["ICT-CBT"]] if cbt else halls
            for slot in slots:
                if enrolled[offering.pk] & in_slot[slot]:
                    continue  # a student would have two exams at once
                chosen, free = [], 0
                for venue in options:
                    available = venue.capacity - seats_used[slot][venue.pk]
                    if available > 0 and free < offering.students:
                        chosen.append(venue)
                        free += available
                if free < offering.students:
                    continue
                exam = Exam.objects.create(
                    offering=offering,
                    date=slot[0],
                    start_time=slot[1],
                    duration_minutes=60 if cbt else (120 if offering.course.units >= 3 else 90),
                    mode=Exam.Mode.CBT if cbt else Exam.Mode.PAPER,
                    instructions="Answer every question." if cbt else "Answer question 1 and any three others.",
                )
                exam.venues.set(chosen)
                if cbt:
                    self.add_questions(exam)
                left = offering.students
                for venue in chosen:
                    take = min(left, venue.capacity - seats_used[slot][venue.pk])
                    seats_used[slot][venue.pk] += take
                    left -= take
                in_slot[slot] |= enrolled[offering.pk]
                exams.append(exam)
                break
            else:
                self.stdout.write(self.style.WARNING(f"No free slot for {offering.course.code}; schedule it by hand."))

        students = set()
        for exam in exams:
            services.allocate_seats(exam)
            exam.status = Exam.Status.PUBLISHED
            exam.save(update_fields=["status"])
            students |= enrolled[exam.offering_id]
        if exams:
            notify(
                list(get_user_model().objects.filter(pk__in=students)),
                f"Your examination timetable for {semester} is out",
                "Check your exam dates, venues and seats, and download your exam card.",
                link="/portal/exams",
                category=Notification.Category.EXAMS,
            )
        return len(exams)

    @staticmethod
    def add_questions(exam):
        rng = random.Random(exam.offering_id)
        for order, (text, options, correct) in enumerate(rng.sample(LOGIC_QUESTIONS, len(LOGIC_QUESTIONS)), 1):
            question = Question.objects.create(exam=exam, text=text, order=order)
            Choice.objects.bulk_create(
                Choice(question=question, text=option, is_correct=i == correct, order=i)
                for i, option in enumerate(options)
            )
        exam.questions_per_candidate = 10
        exam.save(update_fields=["questions_per_candidate"])

    def open_cbt_now(self, semester):
        exam = Exam.objects.filter(offering__semester=semester, offering__course__code="GST211").first()
        if exam is None:
            self.stdout.write(self.style.WARNING("No GST211 exam to open."))
            return
        start = timezone.localtime().replace(second=0, microsecond=0)
        exam.date, exam.start_time, exam.late_entry_minutes = start.date(), start.time(), 120
        exam.attempts.all().delete()
        exam.save(update_fields=["date", "start_time", "late_entry_minutes"])
        self.stdout.write(f"GST211 CBT is open now until {start + timedelta(minutes=120):%H:%M} for late entry.")

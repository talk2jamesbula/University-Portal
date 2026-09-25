"""The Nigerian (NUC) five-point grading system.

A course score is continuous assessment (out of 30) plus examination (out of 70). GPA is the
unit-weighted average of grade points for a semester; CGPA is the same across all semesters.
"""

from decimal import ROUND_HALF_UP, Decimal

CA_MAX = 30
EXAM_MAX = 70
PASS_MARK = 40

# (minimum total, grade, grade points), highest first.
GRADE_SCALE = [
    (70, "A", 5),
    (60, "B", 4),
    (50, "C", 3),
    (45, "D", 2),
    (40, "E", 1),
    (0, "F", 0),
]

# (minimum CGPA, class of degree), highest first.
DEGREE_CLASSES = [
    (Decimal("4.50"), "First Class"),
    (Decimal("3.50"), "Second Class (Upper Division)"),
    (Decimal("2.40"), "Second Class (Lower Division)"),
    (Decimal("1.50"), "Third Class"),
    (Decimal("1.00"), "Pass"),
    (Decimal("0.00"), "Fail"),
]

# A student whose CGPA falls below this is placed on academic probation.
PROBATION_CGPA = Decimal("1.00")


def grade_for(total):
    """(grade, grade points) for a total score out of 100."""
    for minimum, grade, points in GRADE_SCALE:
        if total >= minimum:
            return grade, points
    return "F", 0


def weighted_average(results):
    """GPA over (units, grade_points) pairs. Returns (gpa, units_taken, units_passed)."""
    points = units = passed = 0
    for course_units, grade_points in results:
        points += course_units * grade_points
        units += course_units
        if grade_points > 0:
            passed += course_units
    # Round half up (2.625 -> 2.63), as on transcripts; Decimal's default would give 2.62.
    gpa = (Decimal(points) / units).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if units else None
    return gpa, units, passed


def degree_class(cgpa):
    if cgpa is None:
        return None
    for minimum, name in DEGREE_CLASSES:
        if cgpa >= minimum:
            return name
    return DEGREE_CLASSES[-1][1]


def academic_standing(cgpa):
    if cgpa is None:
        return "Not yet graded"
    return "Academic probation" if cgpa < PROBATION_CGPA else "Good standing"

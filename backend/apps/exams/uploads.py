"""Bulk import of CBT questions from a CSV or Excel file.

One row per question: the question, two to six options (option_a … option_f), the answer (the correct option's
letter, or its exact text) and optionally the marks (1 by default). Every row is checked first; nothing is saved
unless the whole file is valid. The questions are added to the exam's, or replace them.
"""

from django.db import transaction

from apps.core import spreadsheets
from apps.core.services import audit

from . import services
from .models import Choice, Question

LETTERS = "abcdef"
OPTIONS = [f"option_{letter}" for letter in LETTERS]
MAX_ROWS = 500
REQUIRED = ["question", "option_a", "option_b", "answer"]
ALIASES = {
    "question_text": "question",
    "text": "question",
    **{letter: f"option_{letter}" for letter in LETTERS},
    **{f"option_{n}": f"option_{letter}" for n, letter in enumerate(LETTERS, 1)},
    "correct": "answer",
    "correct_answer": "answer",
    "correct_option": "answer",
    "key": "answer",
    "mark": "marks",
    "score": "marks",
    "points": "marks",
}
EXAMPLES = [
    ["Which data structure works on a first-in, first-out basis?", "Stack", "Queue", "Tree", "Graph", "B", 1],
    ["A binary search needs the list to be sorted.", "True", "False", "", "", "A", 1],
]
HEADER = ["question", *OPTIONS[:4], "answer", "marks"]


def template(exam, file_format="csv"):
    """The exam's questions in upload format (so they can be edited and uploaded again), or two examples."""
    questions = list(exam.questions.prefetch_related("choices"))
    if not questions:
        return spreadsheets.write_table(HEADER, EXAMPLES, file_format, title="Questions")
    widest = max(len(q.choices.all()) for q in questions)
    header = ["question", *OPTIONS[: max(widest, 4)], "answer", "marks"]
    rows = []
    for q in questions:
        choices = list(q.choices.all())
        options = [c.text for c in choices] + [""] * (len(header) - 3 - len(choices))
        answer = next((LETTERS[i].upper() for i, c in enumerate(choices) if c.is_correct), "")
        rows.append([q.text, *options, answer, q.marks])
    return spreadsheets.write_table(header, rows, file_format, title=f"{exam.offering.course.code} questions")


def _marks(value):
    raw = spreadsheets.text(value)
    if not raw:
        return 1
    try:
        marks = int(float(raw))
    except ValueError:
        return None
    return marks if 1 <= marks <= 20 and float(raw) == marks else None


def check(exam, upload, *, replace=False):
    """Validate a file. Returns (valid questions, errors)."""
    rows = spreadsheets.read_rows(upload, required=REQUIRED, aliases=ALIASES, max_rows=MAX_ROWS, noun="questions")
    existing = set() if replace else {q.text.strip().lower() for q in exam.questions.all()}
    valid, errors, seen = [], [], {}

    for number, row in rows:
        problems = {}
        text = spreadsheets.text(row.get("question"))
        if not text:
            problems["question"] = ["Write the question."]
        elif len(text) > 5000:
            problems["question"] = ["Keep the question under 5,000 characters."]
        elif text.lower() in existing:
            problems["question"] = ["This question is already in the exam."]
        elif text.lower() in seen:
            problems["question"] = [f"Same question as row {seen[text.lower()]}."]
        else:
            seen[text.lower()] = number

        cells = [spreadsheets.text(row.get(column)) for column in OPTIONS]
        while cells and not cells[-1]:
            cells.pop()
        if len(cells) < 2:
            problems["options"] = ["Give at least two options (option_a and option_b)."]
        elif not all(cells):
            gap = LETTERS[cells.index("")].upper()
            problems["options"] = [f"Option {gap} is empty but a later option is filled in."]
        elif any(len(c) > 500 for c in cells):
            problems["options"] = ["Keep each option under 500 characters."]
        elif len({c.lower() for c in cells}) != len(cells):
            problems["options"] = ["Two options are the same."]

        answer = spreadsheets.text(row.get("answer"))
        correct = None
        if not answer:
            problems["answer"] = ["Give the correct option's letter (A–F)."]
        elif "options" not in problems:
            if len(answer) == 1 and answer.lower() in LETTERS:
                correct = LETTERS.index(answer.lower())
                if correct >= len(cells):
                    problems["answer"] = [f"There is no option {answer.upper()}."]
            else:  # the correct option written out in full
                matches = [i for i, c in enumerate(cells) if c.lower() == answer.lower()]
                if matches:
                    correct = matches[0]
                else:
                    problems["answer"] = ["Use the correct option's letter (A–F), or its exact text."]

        marks = _marks(row.get("marks"))
        if marks is None:
            problems["marks"] = ["Use a whole number from 1 to 20."]

        if problems:
            errors.append({"row": number, "question": text[:80], "errors": problems})
        else:
            valid.append({"text": text, "choices": cells, "correct": correct, "marks": marks})
    return valid, errors


def upload(exam, file, by, request=None, *, dry_run=False, replace=False):
    """Check the file and, if every row is valid (and it isn't a dry run), save the questions."""
    services.ensure_setter(by, exam)
    services.ensure_unlocked(exam)
    valid, errors = check(exam, file, replace=replace)
    result = {
        "rows": len(valid) + len(errors),
        "valid": len(valid),
        "marks": sum(q["marks"] for q in valid),
        "errors": errors,
        "replacing": exam.questions.count() if replace else 0,
        "preview": [
            {"text": q["text"], "choices": q["choices"], "correct": q["correct"], "marks": q["marks"]}
            for q in valid[:5]
        ],
        "saved": False,
    }
    if errors or dry_run:
        return result

    with transaction.atomic():
        if replace:
            exam.questions.all().delete()
        start = exam.questions.order_by("-order").values_list("order", flat=True).first() or 0
        questions = Question.objects.bulk_create(
            Question(exam=exam, text=q["text"], marks=q["marks"], order=start + i) for i, q in enumerate(valid, 1)
        )
        Choice.objects.bulk_create(
            Choice(question=question, text=text, is_correct=i == q["correct"], order=i)
            for question, q in zip(questions, valid, strict=True)
            for i, text in enumerate(q["choices"])
        )
        verb = "Replaced the questions with" if replace else "Imported"
        audit(request, "exams.questions_upload", exam, f"{verb} {len(valid)} questions for {exam}", actor=by)
    result["saved"] = True
    result["total"] = exam.questions.count()
    return result

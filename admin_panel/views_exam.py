from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Count, Max, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from courses.models import Course, Lesson, UserProgress

# ---- CHỌN BỘ MODEL ĐANG DÙNG THẬT (xem Bước 1) ----
from courses.models import Exercise, ExerciseQuestion, Test, TestQuestion
# Nếu dữ liệu thật nằm ở app riêng, bỏ dòng trên và dùng 2 dòng này:
# from exercise.models import Exercise, ExerciseQuestion
# from testing.models import Test, TestQuestion
# ----------------------------------------------------

from .decorators import admin_required

# ---- SỬA CHO KHỚP KẾT QUẢ BƯỚC 1 ----
TEST_STATUSES = ["active", "inactive"]       # giá trị đầu = "đang hiển thị"
CORRECT_CHOICES = ["A", "B", "C", "D"]       # các giá trị đáp án đúng
# --------------------------------------

HSK_LEVELS = list(range(1, 7))


def _fields(model):
    return {f.name for f in model._meta.concrete_fields}


TEST_FIELDS = _fields(Test)

KINDS = {
    "bai-tap": {
        "label": "bài tập",
        "parent": Exercise,
        "question": ExerciseQuestion,
        "fk": "exercise_id",
        "list_url": "admin_exercises",
    },
    "kiem-tra": {
        "label": "bài kiểm tra",
        "parent": Test,
        "question": TestQuestion,
        "fk": "test_id",
        "list_url": "admin_tests",
    },
}


def _kind(kind):
    cfg = KINDS.get(kind)
    if cfg is None:
        raise Http404
    return cfg


def _distinct(model, field):
    values = model.objects.values_list(field, flat=True).distinct()
    return sorted({str(v) for v in values if v not in (None, "")})


def _with_current(base, current=None):
    result = list(base)
    if current and current not in result:
        result.append(current)
    return result


def _lesson_options():
    courses = {c.id: c for c in Course.objects.all()}
    options = []
    for l in Lesson.objects.order_by("course_id", "lesson_order", "id"):
        c = courses.get(l.course_id)
        options.append({"id": l.id, "label": f"{c.name if c else '?'} - {l.title}"})
    return options


def _deps(cfg, obj_id):
    deps = []

    n = cfg["question"].objects.filter(**{cfg["fk"]: obj_id}).count()
    if n:
        deps.append(("câu hỏi", n))

    n = UserProgress.objects.filter(**{cfg["fk"]: obj_id}).count()
    if n:
        deps.append(("lượt tiến độ học viên", n))

    return deps


def _blocked_message(name, deps):
    detail = ", ".join(f"{n} {label}" for label, n in deps)
    return (
        f"Không thể xóa '{name}' vì đang có dữ liệu liên quan: {detail}. "
        "Hãy xóa hoặc chuyển các dữ liệu đó trước."
    )


# =========================================================
# BÀI TẬP
# =========================================================

@admin_required
def exercise_list(request):
    q = request.GET.get("q", "").strip()
    lesson = request.GET.get("lesson", "").strip()

    items = Exercise.objects.order_by("-id")

    if q:
        items = items.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if lesson.isdigit():
        items = items.filter(lesson_id=int(lesson))

    page_obj = Paginator(items, 20).get_page(request.GET.get("page"))
    rows = list(page_obj)

    lessons = Lesson.objects.in_bulk([e.lesson_id for e in rows])
    counts = dict(
        ExerciseQuestion.objects.filter(exercise_id__in=[e.id for e in rows])
        .values_list("exercise_id")
        .annotate(n=Count("id"))
    )
    for e in rows:
        e.lesson_obj = lessons.get(e.lesson_id)
        e.q_count = counts.get(e.id, 0)

    return render(request, "admin_panel/exercises.html", {
        "rows": rows,
        "page_obj": page_obj,
        "q": q,
        "lesson": lesson,
        "lessons": _lesson_options(),
        "total": page_obj.paginator.count,
    })


@admin_required
def exercise_form(request, exercise_id=None):
    exercise = get_object_or_404(Exercise, id=exercise_id) if exercise_id else None

    def render_form(values):
        return render(request, "admin_panel/exercise_form.html", {
            "exercise": exercise,
            "values": values,
            "lessons": _lesson_options(),
            "types": _distinct(Exercise, "exercise_type"),
            "difficulties": _distinct(Exercise, "difficulty"),
        })

    if request.method == "POST":
        lesson_raw = request.POST.get("lesson", "").strip()
        title = request.POST.get("title", "").strip()
        description = request.POST.get("description", "").strip()
        etype = request.POST.get("exercise_type", "").strip()
        difficulty = request.POST.get("difficulty", "").strip()

        values = {
            "lesson": lesson_raw, "title": title, "description": description,
            "exercise_type": etype, "difficulty": difficulty,
        }

        lesson = None
        if lesson_raw.isdigit():
            lesson = Lesson.objects.filter(id=int(lesson_raw)).first()

        error = None
        if lesson is None:
            error = "Vui lòng chọn bài học."
        elif not title:
            error = "Vui lòng nhập tiêu đề."
        elif not etype:
            error = "Vui lòng nhập loại bài tập."

        if error:
            messages.error(request, error)
            return render_form(values)

        now = timezone.now()
        if exercise is None:
            exercise = Exercise(created_at=now)

        exercise.lesson_id = lesson.id
        exercise.title = title
        exercise.description = description
        exercise.exercise_type = etype
        exercise.difficulty = difficulty
        exercise.updated_at = now
        exercise.save()

        messages.success(request, f"Đã lưu bài tập '{exercise.title}'.")
        return redirect("admin_exercises")

    if exercise:
        values = {
            "lesson": exercise.lesson_id,
            "title": exercise.title,
            "description": exercise.description or "",
            "exercise_type": exercise.exercise_type or "",
            "difficulty": exercise.difficulty or "",
        }
    else:
        values = {
            "lesson": request.GET.get("lesson", ""),
            "title": "", "description": "", "exercise_type": "", "difficulty": "",
        }

    return render_form(values)


# =========================================================
# BÀI KIỂM TRA
# =========================================================

@admin_required
def test_list(request):
    q = request.GET.get("q", "").strip()
    course = request.GET.get("course", "").strip()
    status = request.GET.get("status", "").strip()

    items = Test.objects.order_by("-id")

    if q:
        items = items.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if course.isdigit():
        items = items.filter(course_id=int(course))
    if status:
        items = items.filter(status=status)

    page_obj = Paginator(items, 20).get_page(request.GET.get("page"))
    rows = list(page_obj)

    courses = Course.objects.in_bulk([t.course_id for t in rows])
    lessons = Lesson.objects.in_bulk([t.lesson_id for t in rows])
    counts = dict(
        TestQuestion.objects.filter(test_id__in=[t.id for t in rows])
        .values_list("test_id")
        .annotate(n=Count("id"))
    )
    for t in rows:
        t.course_obj = courses.get(t.course_id)
        t.lesson_obj = lessons.get(t.lesson_id)
        t.q_count = counts.get(t.id, 0)
        t.is_on = t.status == TEST_STATUSES[0]

    return render(request, "admin_panel/tests.html", {
        "rows": rows,
        "page_obj": page_obj,
        "q": q,
        "course": course,
        "status": status,
        "courses": Course.objects.order_by("hsk_level", "id"),
        "statuses": TEST_STATUSES,
        "total": page_obj.paginator.count,
    })


@admin_required
def test_form(request, test_id=None):
    test = get_object_or_404(Test, id=test_id) if test_id else None

    has_hsk = "hsk_level" in TEST_FIELDS
    hsk_null = Test._meta.get_field("hsk_level").null if has_hsk else True
    course_null = Test._meta.get_field("course_id").null
    lesson_null = Test._meta.get_field("lesson_id").null

    def render_form(values):
        return render(request, "admin_panel/test_form.html", {
            "test": test,
            "values": values,
            "courses": Course.objects.order_by("hsk_level", "id"),
            "lessons": _lesson_options(),
            "statuses": _with_current(TEST_STATUSES, test.status if test else None),
            "levels": HSK_LEVELS,
            "has_hsk": has_hsk,
            "course_required": not course_null,
            "lesson_required": not lesson_null,
        })

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        description = request.POST.get("description", "").strip()
        duration_raw = request.POST.get("duration", "").strip()
        pass_raw = request.POST.get("passing_score", "").strip()
        status = request.POST.get("status", "").strip()
        course_raw = request.POST.get("course", "").strip()
        lesson_raw = request.POST.get("lesson", "").strip()
        hsk_raw = request.POST.get("hsk_level", "").strip()

        values = {
            "title": title, "description": description, "duration": duration_raw,
            "passing_score": pass_raw, "status": status, "course": course_raw,
            "lesson": lesson_raw, "hsk_level": hsk_raw,
        }

        course = Course.objects.filter(id=int(course_raw)).first() if course_raw.isdigit() else None
        lesson = Lesson.objects.filter(id=int(lesson_raw)).first() if lesson_raw.isdigit() else None

        # Chọn bài học mà chưa chọn khóa thì tự lấy khóa của bài đó
        if lesson and course is None:
            course = Course.objects.filter(id=lesson.course_id).first()

        allowed = set(TEST_STATUSES) | ({test.status} if test else set())

        error = None
        if not title:
            error = "Vui lòng nhập tiêu đề."
        elif course is None and not course_null:
            error = "Vui lòng chọn khóa học."
        elif lesson is None and not lesson_null:
            error = "Vui lòng chọn bài học."
        elif course is None and lesson is None:
            error = "Vui lòng chọn khóa học hoặc bài học."
        elif lesson and course and lesson.course_id != course.id:
            error = "Bài học đã chọn không thuộc khóa học đã chọn."
        elif not (duration_raw.isdigit() and int(duration_raw) > 0):
            error = "Thời gian làm bài (phút) phải là số lớn hơn 0."
        elif not pass_raw.isdigit():
            error = "Điểm đạt phải là số nguyên không âm."
        elif status not in allowed:
            error = "Trạng thái không hợp lệ."
        elif has_hsk and not (
            (hsk_raw.isdigit() and int(hsk_raw) in HSK_LEVELS) or (hsk_raw == "" and hsk_null)
        ):
            error = "Trình độ HSK không hợp lệ."

        if error:
            messages.error(request, error)
            return render_form(values)

        now = timezone.now()
        if test is None:
            test = Test(created_at=now)

        test.course_id = course.id if course else None
        test.lesson_id = lesson.id if lesson else None
        test.title = title
        test.description = description
        test.duration = int(duration_raw)
        test.passing_score = int(pass_raw)
        test.status = status
        if has_hsk:
            test.hsk_level = int(hsk_raw) if hsk_raw else None
        test.updated_at = now
        test.save()

        messages.success(request, f"Đã lưu bài kiểm tra '{test.title}'.")
        return redirect("admin_tests")

    if test:
        values = {
            "title": test.title,
            "description": test.description or "",
            "duration": test.duration,
            "passing_score": test.passing_score,
            "status": test.status,
            "course": test.course_id,
            "lesson": test.lesson_id,
            "hsk_level": getattr(test, "hsk_level", "") if has_hsk else "",
        }
    else:
        values = {
            "title": "", "description": "", "duration": "", "passing_score": "",
            "status": TEST_STATUSES[0], "course": "", "lesson": "", "hsk_level": "",
        }

    return render_form(values)


# =========================================================
# XÓA BÀI TẬP / BÀI KIỂM TRA (dùng chung)
# =========================================================

@admin_required
@require_POST
def parent_delete(request, kind, parent_id):
    cfg = _kind(kind)
    obj = get_object_or_404(cfg["parent"], id=parent_id)

    deps = _deps(cfg, obj.id)
    if deps:
        messages.error(request, _blocked_message(obj.title, deps))
        return redirect(cfg["list_url"])

    title = obj.title
    try:
        obj.delete()
    except IntegrityError:
        messages.error(request, f"Không thể xóa '{title}'.")
        return redirect(cfg["list_url"])

    messages.success(request, f"Đã xóa '{title}'.")
    return redirect(cfg["list_url"])


# =========================================================
# CÂU HỎI (dùng chung cho bài tập và bài kiểm tra)
# =========================================================

@admin_required
def question_list(request, kind, parent_id):
    cfg = _kind(kind)
    parent = get_object_or_404(cfg["parent"], id=parent_id)

    questions = list(
        cfg["question"].objects.filter(**{cfg["fk"]: parent.id}).order_by("question_order", "id")
    )

    return render(request, "admin_panel/questions.html", {
        "kind": kind,
        "label": cfg["label"],
        "parent": parent,
        "questions": questions,
        "show_score": "score" in _fields(cfg["question"]),
        "back_url": reverse(cfg["list_url"]),
    })


@admin_required
def question_form(request, kind, parent_id=None, question_id=None):
    cfg = _kind(kind)
    model = cfg["question"]
    fk = cfg["fk"]
    fields = _fields(model)
    has_expl = "explanation" in fields
    has_score = "score" in fields

    if question_id:
        question = get_object_or_404(model, id=question_id)
        parent = get_object_or_404(cfg["parent"], id=getattr(question, fk))
    else:
        question = None
        parent = get_object_or_404(cfg["parent"], id=parent_id)

    back_url = reverse("admin_questions", args=[kind, parent.id])

    def render_form(values):
        return render(request, "admin_panel/question_form.html", {
            "kind": kind,
            "label": cfg["label"],
            "parent": parent,
            "question": question,
            "values": values,
            "types": _distinct(model, "question_type"),
            "choices": _with_current(CORRECT_CHOICES, question.correct_answer if question else None),
            "has_expl": has_expl,
            "has_score": has_score,
            "back_url": back_url,
        })

    text_fields = ["question", "question_type", "option_a", "option_b", "option_c", "option_d"]

    if request.method == "POST":
        data = {f: request.POST.get(f, "").strip() for f in text_fields}
        correct = request.POST.get("correct_answer", "").strip()
        order_raw = request.POST.get("question_order", "").strip()
        explanation = request.POST.get("explanation", "").strip()
        score_raw = request.POST.get("score", "").strip()

        values = {
            **data, "correct_answer": correct, "question_order": order_raw,
            "explanation": explanation, "score": score_raw,
        }

        allowed = set(CORRECT_CHOICES) | ({question.correct_answer} if question else set())

        score = None
        if has_score:
            try:
                score = Decimal(score_raw)
            except InvalidOperation:
                score = None

        error = None
        if not data["question"]:
            error = "Vui lòng nhập nội dung câu hỏi."
        elif not data["question_type"]:
            error = "Vui lòng nhập loại câu hỏi."
        elif correct not in allowed:
            error = "Vui lòng chọn đáp án đúng."
        elif correct in CORRECT_CHOICES and not data[f"option_{correct.lower()}"]:
            error = f"Đáp án đúng là {correct} nhưng ô lựa chọn {correct} đang trống."
        elif not order_raw.isdigit():
            error = "Thứ tự phải là số nguyên không âm."
        elif has_score and (score is None or score < 0):
            error = "Điểm phải là số không âm."

        if error:
            messages.error(request, error)
            return render_form(values)

        now = timezone.now()
        if question is None:
            question = model(created_at=now)
            setattr(question, fk, parent.id)

        for f, v in data.items():
            setattr(question, f, v)
        question.correct_answer = correct
        question.question_order = int(order_raw)
        if has_expl:
            question.explanation = explanation
        if has_score:
            question.score = score
        question.save()

        messages.success(request, "Đã lưu câu hỏi.")
        return redirect(back_url)

    if question:
        values = {f: getattr(question, f) or "" for f in text_fields}
        values["correct_answer"] = question.correct_answer
        values["question_order"] = question.question_order
        values["explanation"] = (question.explanation or "") if has_expl else ""
        values["score"] = question.score if has_score else ""
    else:
        last = model.objects.filter(**{fk: parent.id}).aggregate(m=Max("question_order"))["m"] or 0
        values = {f: "" for f in text_fields}
        values.update({
            "correct_answer": "", "question_order": last + 1,
            "explanation": "", "score": 1 if has_score else "",
        })

    return render_form(values)


@admin_required
@require_POST
def question_delete(request, kind, question_id):
    cfg = _kind(kind)
    question = get_object_or_404(cfg["question"], id=question_id)
    parent_id = getattr(question, cfg["fk"])

    question.delete()

    messages.success(request, "Đã xóa câu hỏi.")
    return redirect("admin_questions", kind=kind, parent_id=parent_id)
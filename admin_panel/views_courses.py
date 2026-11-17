from urllib.parse import urlencode

from django.contrib import messages
from django.db import IntegrityError
from django.db.models import Count, Max, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from courses.models import (
    Course, Exercise, ExerciseQuestion, Lesson, LessonVocabulary,
    Test, TestQuestion, Translation, UserProgress,
)
from vocabulary.models import Vocabulary

from .decorators import admin_required

# ---- TRẠNG THÁI KHỚP VỚI DỮ LIỆU THẬT TRONG DB ----
COURSE_STATUSES = ["published", "draft"]
LESSON_STATUSES = ["published", "draft"]
# ----------------------------------------------------

HSK_LEVELS = list(range(1, 7))

ATTACH_KINDS = {
    "bai-tap": {"model": Exercise, "label": "bài tập"},
    "kiem-tra": {"model": Test, "label": "bài kiểm tra"},
}


def _statuses(base, current=None):
    """Danh sách trạng thái cho ô chọn; giữ cả giá trị hiện tại nếu nó lạ."""
    result = list(base)
    if current and current not in result:
        result.append(current)
    return result


def _blocked_message(name, deps):
    detail = ", ".join(f"{n} {label}" for label, n in deps)
    return (
        f"Không thể xóa '{name}' vì đang có dữ liệu liên quan: {detail}. "
        "Bạn có thể đổi trạng thái sang ẩn thay vì xóa."
    )


# =========================================================
# KHÓA HỌC
# =========================================================

@admin_required
def course_list(request):
    q = request.GET.get("q", "").strip()
    level = request.GET.get("level", "").strip()
    status = request.GET.get("status", "").strip()

    items = Course.objects.order_by("hsk_level", "id")

    if q:
        items = items.filter(Q(name__icontains=q) | Q(description__icontains=q))
    if level.isdigit():
        items = items.filter(hsk_level=int(level))
    if status:
        items = items.filter(status=status)

    rows = list(items)

    counts = dict(
        Lesson.objects.filter(course_id__in=[c.id for c in rows])
        .values_list("course_id")
        .annotate(n=Count("id"))
    )
    for c in rows:
        c.lesson_count = counts.get(c.id, 0)
        c.is_on = c.status == COURSE_STATUSES[0]

    return render(request, "admin_panel/courses.html", {
        "rows": rows,
        "q": q,
        "level": level,
        "status": status,
        "levels": HSK_LEVELS,
        "statuses": COURSE_STATUSES,
    })


@admin_required
def course_form(request, course_id=None):
    course = get_object_or_404(Course, id=course_id) if course_id else None

    def render_form(values):
        return render(request, "admin_panel/course_form.html", {
            "course": course,
            "values": values,
            "levels": HSK_LEVELS,
            "statuses": _statuses(COURSE_STATUSES, course.status if course else None),
        })

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        image = request.POST.get("image", "").strip()
        hsk_raw = request.POST.get("hsk_level", "").strip()
        status = request.POST.get("status", "").strip()

        values = {
            "name": name, "description": description, "image": image,
            "hsk_level": hsk_raw, "status": status,
        }

        allowed = set(COURSE_STATUSES) | ({course.status} if course else set())

        error = None
        if not name:
            error = "Vui lòng nhập tên khóa học."
        elif not (hsk_raw.isdigit() and int(hsk_raw) in HSK_LEVELS):
            error = "Trình độ HSK không hợp lệ."
        elif status not in allowed:
            error = "Trạng thái không hợp lệ."

        if error:
            messages.error(request, error)
            return render_form(values)

        now = timezone.now()
        if course is None:
            course = Course(created_at=now)

        course.name = name
        course.description = description
        course.image = image
        course.hsk_level = int(hsk_raw)
        course.status = status
        course.updated_at = now
        course.save()

        messages.success(request, f"Đã lưu khóa học '{course.name}'.")
        return redirect("admin_courses")

    if course:
        values = {
            "name": course.name,
            "description": course.description or "",
            "image": str(course.image or ""),
            "hsk_level": course.hsk_level,
            "status": course.status,
        }
    else:
        values = {
            "name": "", "description": "", "image": "",
            "hsk_level": 1, "status": COURSE_STATUSES[0],
        }

    return render_form(values)


@admin_required
@require_POST
def course_delete(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    checks = [
        ("bài học", Lesson.objects.filter(course_id=course.id)),
        ("bài kiểm tra", Test.objects.filter(course_id=course.id)),
    ]
    deps = [(label, qs.count()) for label, qs in checks if qs.exists()]

    if deps:
        messages.error(request, _blocked_message(course.name, deps))
        return redirect("admin_courses")

    name = course.name
    try:
        course.delete()
    except IntegrityError:
        messages.error(request, f"Không thể xóa khóa học '{name}'.")
        return redirect("admin_courses")

    messages.success(request, f"Đã xóa khóa học '{name}'.")
    return redirect("admin_courses")


# =========================================================
# BÀI HỌC
# =========================================================

@admin_required
def lesson_list(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    lessons = list(Lesson.objects.filter(course_id=course.id).order_by("lesson_order", "id"))

    counts = dict(
        LessonVocabulary.objects.filter(lesson_id__in=[l.id for l in lessons])
        .values_list("lesson_id")
        .annotate(n=Count("id"))
    )
    for l in lessons:
        l.vocab_count = counts.get(l.id, 0)
        l.is_on = l.status == LESSON_STATUSES[0]

    return render(request, "admin_panel/lessons.html", {
        "course": course,
        "lessons": lessons,
    })


@admin_required
def lesson_form(request, course_id=None, lesson_id=None):
    if lesson_id:
        lesson = get_object_or_404(Lesson, id=lesson_id)
        course = get_object_or_404(Course, id=lesson.course_id)
    else:
        lesson = None
        course = get_object_or_404(Course, id=course_id)

    def render_form(values):
        return render(request, "admin_panel/lesson_form.html", {
            "course": course,
            "lesson": lesson,
            "values": values,
            "statuses": _statuses(LESSON_STATUSES, lesson.status if lesson else None),
        })

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        description = request.POST.get("description", "").strip()
        order_raw = request.POST.get("lesson_order", "").strip()
        status = request.POST.get("status", "").strip()

        values = {
            "title": title, "description": description,
            "lesson_order": order_raw, "status": status,
        }

        allowed = set(LESSON_STATUSES) | ({lesson.status} if lesson else set())

        error = None
        if not title:
            error = "Vui lòng nhập tiêu đề bài học."
        elif not order_raw.isdigit():
            error = "Thứ tự phải là số nguyên không âm."
        elif status not in allowed:
            error = "Trạng thái không hợp lệ."

        if error:
            messages.error(request, error)
            return render_form(values)

        now = timezone.now()
        if lesson is None:
            lesson = Lesson(course=course, created_at=now)

        lesson.title = title
        lesson.description = description
        lesson.lesson_order = int(order_raw)
        lesson.status = status
        lesson.updated_at = now
        lesson.save()

        messages.success(request, f"Đã lưu bài học '{lesson.title}'.")
        return redirect("admin_lessons", course_id=course.id)

    if lesson:
        values = {
            "title": lesson.title,
            "description": lesson.description or "",
            "lesson_order": lesson.lesson_order,
            "status": lesson.status,
        }
    else:
        last = Lesson.objects.filter(course_id=course.id).aggregate(m=Max("lesson_order"))["m"] or 0
        values = {
            "title": "", "description": "",
            "lesson_order": last + 1, "status": LESSON_STATUSES[0],
        }

    return render_form(values)


@admin_required
@require_POST
def lesson_delete(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id)
    course_id = lesson.course_id

    checks = [
        ("từ vựng", LessonVocabulary.objects.filter(lesson_id=lesson.id)),
        ("bản dịch", Translation.objects.filter(lesson_id=lesson.id)),
        ("bài tập", Exercise.objects.filter(lesson_id=lesson.id)),
        ("bài kiểm tra", Test.objects.filter(lesson_id=lesson.id)),
        ("lượt tiến độ học viên", UserProgress.objects.filter(lesson_id=lesson.id)),
    ]
    deps = [(label, qs.count()) for label, qs in checks if qs.exists()]

    if deps:
        messages.error(request, _blocked_message(lesson.title, deps))
        return redirect("admin_lessons", course_id=course_id)

    title = lesson.title
    try:
        lesson.delete()
    except IntegrityError:
        messages.error(request, f"Không thể xóa bài học '{title}'.")
        return redirect("admin_lessons", course_id=course_id)

    messages.success(request, f"Đã xóa bài học '{title}'.")
    return redirect("admin_lessons", course_id=course_id)


# =========================================================
# NỘI DUNG BÀI HỌC: TỪ VỰNG, BÀI TẬP, BÀI KIỂM TRA
# =========================================================

def _back_to_vocab(request, lesson_id):
    url = reverse("admin_lesson_vocab", args=[lesson_id])
    params = {"f": "1"}
    for k in ("q", "level"):
        if request.POST.get(k):
            params[k] = request.POST.get(k)
    return redirect(f"{url}?{urlencode(params)}")


@admin_required
def lesson_vocab(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id)
    course = get_object_or_404(Course, id=lesson.course_id)

    # ---------- Từ vựng ----------
    links = list(
        LessonVocabulary.objects.filter(lesson_id=lesson.id)
        .select_related("vocabulary")
        .order_by("word_order", "id")
    )
    current_ids = [l.vocabulary_id for l in links]

    q = request.GET.get("q", "").strip()
    level = request.GET.get("level", "").strip()

    # Lần đầu mở trang: gợi ý sẵn các từ cùng cấp HSK với khóa học
    if "f" not in request.GET and not q and not level:
        level = str(course.hsk_level)

    found = Vocabulary.objects.exclude(id__in=current_ids).order_by("hsk_level", "id")
    if q:
        found = found.filter(
            Q(word__icontains=q) | Q(pinyin__icontains=q) | Q(meaning__icontains=q)
        )
    if level.isdigit():
        found = found.filter(hsk_level=int(level))
    candidates = list(found[:40])

    # ---------- Bài tập và bài kiểm tra ----------
    lessons_map = {l.id: l for l in Lesson.objects.all()}

    exercises = list(Exercise.objects.filter(lesson_id=lesson.id).order_by("id"))
    tests = list(Test.objects.filter(lesson_id=lesson.id).order_by("id"))

    ex_counts = dict(
        ExerciseQuestion.objects.filter(exercise_id__in=[e.id for e in exercises])
        .values_list("exercise_id")
        .annotate(n=Count("id"))
    )
    test_counts = dict(
        TestQuestion.objects.filter(test_id__in=[t.id for t in tests])
        .values_list("test_id")
        .annotate(n=Count("id"))
    )
    for e in exercises:
        e.q_count = ex_counts.get(e.id, 0)
    for t in tests:
        t.q_count = test_counts.get(t.id, 0)

    ex_candidates = list(Exercise.objects.exclude(lesson_id=lesson.id).order_by("-id")[:60])
    test_candidates = list(Test.objects.exclude(lesson_id=lesson.id).order_by("-id")[:60])
    for item in ex_candidates + test_candidates:
        item.current_lesson = lessons_map.get(item.lesson_id)

    return render(request, "admin_panel/lesson_vocab.html", {
        "lesson": lesson,
        "course": course,
        "links": links,
        "candidates": candidates,
        "q": q,
        "level": level,
        "levels": HSK_LEVELS,
        "exercises": exercises,
        "tests": tests,
        "ex_candidates": ex_candidates,
        "test_candidates": test_candidates,
        "ex_detachable": Exercise._meta.get_field("lesson_id").null,
        "test_detachable": Test._meta.get_field("lesson_id").null,
    })


@admin_required
@require_POST
def lesson_attach(request, lesson_id, kind):
    lesson = get_object_or_404(Lesson, id=lesson_id)
    cfg = ATTACH_KINDS.get(kind)
    if cfg is None:
        raise Http404

    back = f"{reverse('admin_lesson_vocab', args=[lesson.id])}?f=1#{kind}"

    ids = [int(x) for x in request.POST.getlist("item_ids") if x.isdigit()]
    if not ids:
        messages.error(request, f"Bạn chưa chọn {cfg['label']} nào.")
        return redirect(back)

    values = {"lesson_id": lesson.id, "updated_at": timezone.now()}
    if kind == "kiem-tra":
        values["course_id"] = lesson.course_id

    count = cfg["model"].objects.filter(id__in=ids).update(**values)

    messages.success(request, f"Đã thêm {count} {cfg['label']} vào bài học.")
    return redirect(back)


@admin_required
@require_POST
def lesson_detach(request, kind, item_id):
    cfg = ATTACH_KINDS.get(kind)
    if cfg is None:
        raise Http404

    model = cfg["model"]
    item = get_object_or_404(model, id=item_id)
    lesson_id = item.lesson_id

    if lesson_id is None:
        return redirect("admin_courses")

    back = f"{reverse('admin_lesson_vocab', args=[lesson_id])}?f=1#{kind}"

    if not model._meta.get_field("lesson_id").null:
        messages.error(
            request,
            f"Mỗi {cfg['label']} phải thuộc một bài học nên không gỡ ra được. "
            "Muốn chuyển, hãy thêm nó vào bài học khác."
        )
        return redirect(back)

    model.objects.filter(id=item.id).update(lesson_id=None, updated_at=timezone.now())

    messages.success(request, f"Đã gỡ {cfg['label']} khỏi bài học.")
    return redirect(back)


@admin_required
@require_POST
def lesson_vocab_add(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id)

    ids = [int(x) for x in request.POST.getlist("vocab_ids") if x.isdigit()]
    if not ids:
        messages.error(request, "Bạn chưa chọn từ nào.")
        return _back_to_vocab(request, lesson.id)

    existing = set(
        LessonVocabulary.objects.filter(lesson_id=lesson.id).values_list("vocabulary_id", flat=True)
    )
    last = LessonVocabulary.objects.filter(lesson_id=lesson.id).aggregate(m=Max("word_order"))["m"] or 0

    added = 0
    for v in Vocabulary.objects.filter(id__in=ids).order_by("id"):
        if v.id in existing:
            continue
        last += 1
        LessonVocabulary.objects.create(lesson=lesson, vocabulary=v, word_order=last)
        added += 1

    messages.success(request, f"Đã thêm {added} từ vào bài học.")
    return _back_to_vocab(request, lesson.id)


@admin_required
@require_POST
def lesson_vocab_order(request, lesson_id):
    changed = 0
    for link in LessonVocabulary.objects.filter(lesson_id=lesson_id):
        raw = request.POST.get(f"order_{link.id}", "").strip()
        if raw.isdigit() and int(raw) != link.word_order:
            link.word_order = int(raw)
            link.save(update_fields=["word_order"])
            changed += 1

    messages.success(request, "Đã lưu thứ tự." if changed else "Thứ tự không thay đổi.")
    return redirect("admin_lesson_vocab", lesson_id=lesson_id)


@admin_required
@require_POST
def lesson_vocab_remove(request, link_id):
    link = get_object_or_404(LessonVocabulary, id=link_id)
    lesson_id = link.lesson_id
    link.delete()

    messages.success(request, "Đã gỡ từ khỏi bài học.")
    return redirect("admin_lesson_vocab", lesson_id=lesson_id)
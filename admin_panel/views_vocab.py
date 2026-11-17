from django.contrib import messages
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from courses.models import LessonVocabulary
from vocabulary.models import Vocabulary, VocabularyCategories

from .decorators import admin_required

HSK_LEVELS = list(range(1, 7))

# Cột category có cho phép trống hay không (đọc thẳng từ model)
CATEGORY_NULLABLE = Vocabulary._meta.get_field("category").null

TEXT_FIELDS = [
    "word", "pinyin", "meaning",
    "example_sentence", "example_pinyin", "example_meaning",
    "audio",
]


# =========================================================
# TỪ VỰNG
# =========================================================

@admin_required
def vocab_list(request):
    q = request.GET.get("q", "").strip()
    level = request.GET.get("level", "").strip()
    category = request.GET.get("category", "").strip()

    items = Vocabulary.objects.select_related("category").order_by("-id")

    if q:
        items = items.filter(
            Q(word__icontains=q) | Q(pinyin__icontains=q) | Q(meaning__icontains=q)
        )
    if level.isdigit():
        items = items.filter(hsk_level=int(level))
    if category.isdigit():
        items = items.filter(category_id=int(category))

    page_obj = Paginator(items, 20).get_page(request.GET.get("page"))
    rows = list(page_obj)

    # Mỗi từ đang được dùng trong bao nhiêu bài học
    used = dict(
        LessonVocabulary.objects.filter(vocabulary_id__in=[v.id for v in rows])
        .values_list("vocabulary_id")
        .annotate(n=Count("id"))
    )
    for v in rows:
        v.used_in = used.get(v.id, 0)

    return render(request, "admin_panel/vocab_list.html", {
        "rows": rows,
        "page_obj": page_obj,
        "q": q,
        "level": level,
        "category": category,
        "levels": HSK_LEVELS,
        "categories": VocabularyCategories.objects.order_by("name"),
        "total": page_obj.paginator.count,
    })


@admin_required
def vocab_form(request, vocab_id=None):
    vocab = get_object_or_404(Vocabulary, id=vocab_id) if vocab_id else None
    categories = VocabularyCategories.objects.order_by("name")

    def render_form(values):
        return render(request, "admin_panel/vocab_form.html", {
            "vocab": vocab,
            "values": values,
            "levels": HSK_LEVELS,
            "categories": categories,
            "category_required": not CATEGORY_NULLABLE,
        })

    if request.method == "POST":
        data = {f: request.POST.get(f, "").strip() for f in TEXT_FIELDS}
        hsk_raw = request.POST.get("hsk_level", "").strip()
        cat_raw = request.POST.get("category", "").strip()

        values = {**data, "hsk_level": hsk_raw, "category": cat_raw}

        category = None
        if cat_raw.isdigit():
            category = VocabularyCategories.objects.filter(id=int(cat_raw)).first()

        error = None
        if not data["word"] or not data["meaning"]:
            error = "Vui lòng nhập từ và nghĩa."
        elif not (hsk_raw.isdigit() and int(hsk_raw) in HSK_LEVELS):
            error = "Trình độ HSK không hợp lệ."
        elif category is None and not CATEGORY_NULLABLE:
            error = "Vui lòng chọn danh mục."
        elif (
            Vocabulary.objects
            .filter(word=data["word"], pinyin=data["pinyin"])
            .exclude(id=vocab.id if vocab else None)
            .exists()
        ):
            error = "Từ này (cùng pinyin) đã có trong danh sách."

        if error:
            messages.error(request, error)
            return render_form(values)

        if vocab is None:
            vocab = Vocabulary(created_at=timezone.now())

        for f in TEXT_FIELDS:
            setattr(vocab, f, data[f])
        vocab.hsk_level = int(hsk_raw)
        vocab.category = category
        vocab.save()

        messages.success(request, f"Đã lưu từ '{vocab.word}'.")
        return redirect("admin_vocab")

    # GET: điền sẵn dữ liệu (nếu đang sửa)
    if vocab:
        values = {f: str(getattr(vocab, f) or "") for f in TEXT_FIELDS}
        values["hsk_level"] = vocab.hsk_level
        values["category"] = vocab.category_id
    else:
        values = {f: "" for f in TEXT_FIELDS}
        values["hsk_level"] = 1
        values["category"] = ""

    return render_form(values)


@admin_required
@require_POST
def vocab_delete(request, vocab_id):
    vocab = get_object_or_404(Vocabulary, id=vocab_id)

    used = LessonVocabulary.objects.filter(vocabulary_id=vocab.id).count()
    if used:
        messages.error(
            request,
            f"Từ '{vocab.word}' đang được dùng trong {used} bài học. "
            "Hãy gỡ khỏi bài học trước khi xóa."
        )
        return redirect("admin_vocab")

    word = vocab.word
    try:
        vocab.delete()
    except IntegrityError:
        messages.error(request, f"Không thể xóa '{word}' vì dữ liệu khác đang tham chiếu tới nó.")
        return redirect("admin_vocab")

    messages.success(request, f"Đã xóa từ '{word}'.")
    return redirect("admin_vocab")


# =========================================================
# DANH MỤC TỪ VỰNG
# =========================================================

@admin_required
def category_list(request):
    cats = list(VocabularyCategories.objects.order_by("name"))

    counts = dict(
        Vocabulary.objects.values_list("category_id").annotate(n=Count("id"))
    )
    for c in cats:
        c.count = counts.get(c.id, 0)

    return render(request, "admin_panel/categories.html", {"cats": cats})


@admin_required
@require_POST
def category_save(request, category_id=None):
    name = request.POST.get("name", "").strip()
    description = request.POST.get("description", "").strip()

    if not name:
        messages.error(request, "Tên danh mục không được để trống.")
        return redirect("admin_categories")

    dup = VocabularyCategories.objects.filter(name__iexact=name)
    if category_id:
        dup = dup.exclude(id=category_id)
    if dup.exists():
        messages.error(request, "Danh mục này đã tồn tại.")
        return redirect("admin_categories")

    if category_id:
        cat = get_object_or_404(VocabularyCategories, id=category_id)
        cat.name = name
        cat.description = description
        cat.save(update_fields=["name", "description"])
        messages.success(request, "Đã cập nhật danh mục.")
    else:
        VocabularyCategories.objects.create(
            name=name,
            description=description,
            created_at=timezone.now(),
        )
        messages.success(request, "Đã thêm danh mục.")

    return redirect("admin_categories")


@admin_required
@require_POST
def category_delete(request, category_id):
    cat = get_object_or_404(VocabularyCategories, id=category_id)

    count = Vocabulary.objects.filter(category_id=cat.id).count()
    if count:
        messages.error(
            request,
            f"Danh mục '{cat.name}' đang có {count} từ vựng. Hãy chuyển các từ sang danh mục khác trước."
        )
        return redirect("admin_categories")

    name = cat.name
    try:
        cat.delete()
    except IntegrityError:
        messages.error(request, f"Không thể xóa danh mục '{name}'.")
        return redirect("admin_categories")

    messages.success(request, f"Đã xóa danh mục '{name}'.")
    return redirect("admin_categories")
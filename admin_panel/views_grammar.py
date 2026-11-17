from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from courses.models import Grammar

from .decorators import admin_required

HSK_LEVELS = list(range(1, 7))

TEXT_FIELDS = ["title", "explanation", "examples", "notes"]


# =========================================================
# NGỮ PHÁP
# =========================================================

@admin_required
def grammar_list(request):
    q = request.GET.get("q", "").strip()
    level = request.GET.get("level", "").strip()

    items = Grammar.objects.order_by("hsk_level", "id")

    if q:
        items = items.filter(
            Q(title__icontains=q)
            | Q(explanation__icontains=q)
            | Q(examples__icontains=q)
        )

    if level.isdigit():
        items = items.filter(hsk_level=int(level))

    page_obj = Paginator(items, 20).get_page(request.GET.get("page"))

    return render(request, "admin_panel/grammar_list.html", {
        "rows": list(page_obj),
        "page_obj": page_obj,
        "q": q,
        "level": level,
        "levels": HSK_LEVELS,
        "total": page_obj.paginator.count,
    })


@admin_required
def grammar_form(request, grammar_id=None):
    grammar = get_object_or_404(Grammar, id=grammar_id) if grammar_id else None

    def render_form(values):
        return render(request, "admin_panel/grammar_form.html", {
            "grammar": grammar,
            "values": values,
            "levels": HSK_LEVELS,
        })

    if request.method == "POST":
        data = {f: request.POST.get(f, "").strip() for f in TEXT_FIELDS}
        hsk_raw = request.POST.get("hsk_level", "").strip()

        values = {**data, "hsk_level": hsk_raw}

        error = None

        if not data["title"] or not data["explanation"]:
            error = "Vui lòng nhập tiêu đề và phần giải thích."

        elif not (hsk_raw.isdigit() and int(hsk_raw) in HSK_LEVELS):
            error = "Trình độ HSK không hợp lệ."

        elif (
            Grammar.objects
            .filter(title__iexact=data["title"], hsk_level=int(hsk_raw))
            .exclude(id=grammar.id if grammar else None)
            .exists()
        ):
            error = "Điểm ngữ pháp này đã có trong cùng cấp HSK."

        if error:
            messages.error(request, error)
            return render_form(values)

        now = timezone.now()

        if grammar is None:
            grammar = Grammar(created_at=now)

        for f in TEXT_FIELDS:
            setattr(grammar, f, data[f])

        grammar.hsk_level = int(hsk_raw)
        grammar.updated_at = now
        grammar.save()

        messages.success(request, f"Đã lưu ngữ pháp '{grammar.title}'.")
        return redirect("admin_grammar")

    # GET: điền sẵn dữ liệu (nếu đang sửa)
    if grammar:
        values = {f: str(getattr(grammar, f) or "") for f in TEXT_FIELDS}
        values["hsk_level"] = grammar.hsk_level
    else:
        values = {f: "" for f in TEXT_FIELDS}
        values["hsk_level"] = 1

    return render_form(values)


@admin_required
@require_POST
def grammar_delete(request, grammar_id):
    grammar = get_object_or_404(Grammar, id=grammar_id)

    title = grammar.title
    grammar.delete()

    messages.success(request, f"Đã xóa ngữ pháp '{title}'.")
    return redirect("admin_grammar")
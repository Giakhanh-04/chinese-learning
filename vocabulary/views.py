
from django.shortcuts import render
from django.db.models import Count
from .models import Vocabulary


def vocabulary_list(request):
    selected_hsk = request.GET.get("hsk")

    # Đếm số từ vựng của từng cấp độ HSK
    hsk_counts = (
        Vocabulary.objects
        .values("hsk_level")
        .annotate(total=Count("id"))
    )

    counts = {
        item["hsk_level"]: item["total"]
        for item in hsk_counts
    }

    hsk_levels = [
        {"level": level, "count": counts.get(level, 0)}
        for level in range(1, 7)
    ]

    # Mặc định chưa hiển thị từ vựng
    vocabularies = Vocabulary.objects.none()

    # Chỉ hiển thị từ khi người dùng chọn một cấp độ HSK
    if selected_hsk:
        try:
            selected_hsk = int(selected_hsk)

            if selected_hsk in range(1, 7):
                vocabularies = Vocabulary.objects.filter(
                    hsk_level=selected_hsk
                ).order_by("id")
            else:
                selected_hsk = None

        except (ValueError, TypeError):
            selected_hsk = None

    context = {
        "vocabularies": vocabularies,
        "hsk_levels": hsk_levels,
        "selected_hsk": selected_hsk,
    }

    return render(
        request,
        "vocabulary/vocabulary_list.html",
        context
    )

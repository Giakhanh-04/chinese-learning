from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import Test, TestQuestion
from courses.models import UserProgress
from premium.utils import is_premium_user

# Mỗi cấp HSK có bao nhiêu đề miễn phí (tính theo thứ tự id nhỏ nhất)
FREE_TESTS_PER_LEVEL = 1


def _is_premium(request):
    """Admin và tài khoản Premium được làm mọi đề."""
    if request.session.get("role") == "admin":
        return True

    user_id = request.session.get("user_id")

    return bool(user_id) and is_premium_user(user_id)


def _free_test_ids(hsk_level):
    """Id của các đề miễn phí trong một cấp HSK."""
    return set(
        Test.objects
        .filter(status="published", hsk_level=hsk_level)
        .order_by("id")
        .values_list("id", flat=True)[:FREE_TESTS_PER_LEVEL]
    )


def test_list(request):
    hsk_level = request.GET.get("hsk", "1")

    try:
        hsk_level = int(hsk_level)
    except (TypeError, ValueError):
        hsk_level = 1

    if hsk_level not in range(1, 7):
        hsk_level = 1

    tests = list(
        Test.objects.filter(
            status="published",
            hsk_level=hsk_level
        ).order_by("id")
    )

    premium = _is_premium(request)
    free_ids = _free_test_ids(hsk_level)

    for t in tests:
        t.is_free = t.id in free_ids
        t.locked = (not t.is_free) and (not premium)

    return render(
        request,
        "testing/test_list.html",
        {
            "tests": tests,
            "selected_hsk": hsk_level,
            "is_premium": premium,
        }
    )


def test_detail(request, test_id):

    test = get_object_or_404(Test, id=test_id)

    # Đề trả phí: chưa có Premium thì không được làm (cả xem lẫn nộp bài)
    if test.id not in _free_test_ids(test.hsk_level) and not _is_premium(request):

        if request.method == "POST":
            return JsonResponse(
                {"success": False, "error": "Đề này dành cho tài khoản Premium."},
                status=403
            )

        return redirect("premium_list")

    questions = TestQuestion.objects.filter(
        test_id=test_id
    ).order_by("question_order")

    if request.method == "POST":

        score = 0
        total = questions.count()

        results = []

        for question in questions:

            user_answer = request.POST.get(
                f"question_{question.id}"
            )

            correct_answer = (
                question.correct_answer or ""
            ).strip().upper()

            is_correct = (
                user_answer is not None
                and user_answer.strip().upper()
                == correct_answer
            )

            if is_correct:
                score += 1

            results.append({
                "question_id": question.id,
                "user_answer": user_answer,
                "correct_answer": correct_answer,
                "is_correct": is_correct,
                "unanswered": user_answer is None,
            })

        percent = (
            round((score / total) * 100)
            if total > 0
            else 0
        )

        passed = percent >= float(test.passing_score)

        # ==============================
        # LƯU KẾT QUẢ VÀO USER_PROGRESS
        # ==============================

        user_id = request.session.get("user_id")

        if user_id and test.lesson_id:

            progress = UserProgress.objects.filter(
                user_id=user_id,
                lesson_id=test.lesson_id
            ).first()

            if progress:

                progress.progress_percent = 100
                progress.score = percent
                progress.test_id = test.id
                progress.status = "completed"
                progress.completed_at = timezone.now()
                progress.last_accessed = timezone.now()

                progress.save(
                    update_fields=[
                        "progress_percent",
                        "score",
                        "test_id",
                        "status",
                        "completed_at",
                        "last_accessed"
                    ]
                )

            else:

                UserProgress.objects.create(
                    user_id=user_id,
                    lesson_id=test.lesson_id,
                    test_id=test.id,
                    progress_percent=100,
                    score=percent,
                    status="completed",
                    last_accessed=timezone.now(),
                    completed_at=timezone.now()
                )

        return JsonResponse({
            "success": True,
            "score": score,
            "total": total,
            "percent": percent,
            "passing_score": float(test.passing_score),
            "passed": passed,
            "results": results,
        })

    return render(
        request,
        "testing/test_detail.html",
        {
            "test": test,
            "questions": questions,
        }
    )
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from .models import (
    Course,
    Lesson,
    LessonVocabulary,
    Grammar,
    Translation,
    Exercise,
    ExerciseQuestion,
    Test,
    TestQuestion,
    UserProgress
)


def course_list(request):
    hsk = request.GET.get("hsk", "").strip()

    courses = Course.objects.all().order_by("hsk_level", "id")

    selected_hsk = None

    if hsk.isdigit() and 1 <= int(hsk) <= 6:
        selected_hsk = int(hsk)
        courses = courses.filter(hsk_level=selected_hsk)

    return render(
        request,
        "courses/course_list.html",
        {
            "courses": courses,
            "selected_hsk": selected_hsk,
            "levels": range(1, 7),
        }
    )


def course_detail(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    lessons = Lesson.objects.filter(
        course_id=course_id
    ).order_by("lesson_order", "id")

    return render(
        request,
        "courses/course_detail.html",
        {
            "course": course,
            "lessons": lessons
        }
    )


def lesson_detail(request, lesson_id):
    lesson = get_object_or_404(
        Lesson,
        id=lesson_id
    )

    lesson_vocabularies = LessonVocabulary.objects.filter(
        lesson_id=lesson_id
    ).select_related("vocabulary").order_by("word_order")

    grammars = Grammar.objects.filter(
        hsk_level=lesson.course.hsk_level
    ).order_by("id")

    translations = Translation.objects.filter(
        lesson_id=lesson_id
    ).order_by("id")

    exercises = Exercise.objects.filter(
        lesson_id=lesson_id
    ).prefetch_related(
        "exercisequestion_set"
    ).order_by("id")

    tests = Test.objects.filter(
        lesson_id=lesson_id,
        status="published"
    ).order_by("id")

    # ==================== TIẾN ĐỘ HỌC ====================
    user_id = request.session.get("user_id")

    if not user_id:
        return redirect("login")

    progress = UserProgress.objects.filter(
        user_id=user_id,
        lesson_id=lesson_id
    ).first()

    if progress:
        if progress.status != "completed":
            progress.status = "in_progress"
            progress.last_accessed = timezone.now()

            progress.save(
                update_fields=[
                    "status",
                    "last_accessed"
                ]
            )
        else:
            progress.last_accessed = timezone.now()

            progress.save(
                update_fields=[
                    "last_accessed"
                ]
            )

    else:
        UserProgress.objects.create(
            user_id=user_id,
            lesson_id=lesson_id,
            progress_percent=0,
            score=0,
            status="in_progress",
            last_accessed=timezone.now()
        )

    return render(
        request,
        "courses/lesson_detail.html",
        {
            "lesson": lesson,
            "lesson_vocabularies": lesson_vocabularies,
            "grammars": grammars,
            "translations": translations,
            "exercises": exercises,
            "tests": tests
        }
    )


def test_detail(request, test_id):
    test = get_object_or_404(
        Test,
        id=test_id
    )

    questions = TestQuestion.objects.filter(
        test_id=test_id
    ).order_by("question_order")

    if request.method == "POST":

        print("DA NHAN POST TEST")

        user_id = request.session.get("user_id")

        if not user_id:
            return redirect("login")

        correct = 0
        total = questions.count()

        for question in questions:
            answer = request.POST.get(
                f"question_{question.id}"
            )

            if answer == question.correct_answer:
                correct += 1

        score = (correct / total * 100) if total > 0 else 0

        # Lưu kết quả vào tiến độ bài học
        if test.lesson_id:
            progress = UserProgress.objects.filter(
                user_id=user_id,
                lesson_id=test.lesson_id
            ).first()

            if progress:
                progress.progress_percent = 100
                progress.score = score
                progress.status = "completed"
                progress.completed_at = timezone.now()
                progress.last_accessed = timezone.now()

                progress.save(
                    update_fields=[
                        "progress_percent",
                        "score",
                        "status",
                        "completed_at",
                        "last_accessed"
                    ]
                )

            else:
                UserProgress.objects.create(
                    user_id=user_id,
                    lesson_id=test.lesson_id,
                    progress_percent=100,
                    score=score,
                    status="completed",
                    last_accessed=timezone.now(),
                    completed_at=timezone.now()
                )

        return render(
            request,
            "courses/test_result.html",
            {
                "test": test,
                "correct": correct,
                "total": total,
                "score": score
            }
        )

    return render(
        request,
        "courses/test_detail.html",
        {
            "test": test,
            "questions": questions
        }
    )


def progress_view(request):
    user_id = request.session.get("user_id")

    if not user_id:
        return render(
            request,
            "courses/progress.html",
            {
                "progress_list": [],
                "login_required": True
            }
        )

    progress_list = UserProgress.objects.filter(
        user_id=user_id
    ).select_related("lesson").order_by(
        "-last_accessed",
        "-id"
    )

    return render(
        request,
        "courses/progress.html",
        {
            "progress_list": progress_list,
            "login_required": False
        }
    )

def grammar_list(request):

    grammars = Grammar.objects.all().order_by(
        "hsk_level",
        "id"
    )

    return render(
        request,
        "courses/grammar_list.html",
        {
            "grammars": grammars
        }
    )

def exercise_detail(request, exercise_id):
    exercise = get_object_or_404(Exercise, id=exercise_id)

    questions = ExerciseQuestion.objects.filter(
        exercise_id=exercise_id
    ).order_by("question_order")

    if request.method == "POST":

        correct = 0
        total = questions.count()

        for question in questions:

            answer = request.POST.get(
                f"question_{question.id}"
            )

            if answer == question.correct_answer:
                correct += 1

        score = (correct / total * 100) if total > 0 else 0

        return render(
            request,
            "courses/exercise_result.html",
            {
                "exercise": exercise,
                "correct": correct,
                "total": total,
                "score": score,
            }
        )

    return render(
        request,
        "courses/exercise_detail.html",
        {
            "exercise": exercise,
            "questions": questions,
        }
    )
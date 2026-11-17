from django.http import JsonResponse
from django.shortcuts import render

from .models import Exercise, ExerciseQuestion


def exercise_list(request):

    exercises = Exercise.objects.all().order_by("id")

    return render(
        request,
        "exercise/exercise_list.html",
        {
            "exercises": exercises
        }
    )


def exercise_detail(request, exercise_id):

    exercise = Exercise.objects.get(id=exercise_id)

    questions = ExerciseQuestion.objects.filter(
        exercise_id=exercise_id
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
                "explanation": question.explanation or "",
            })

        return JsonResponse({
            "success": True,
            "score": score,
            "total": total,
            "results": results,
        })

    return render(
        request,
        "exercise/exercise_detail.html",
        {
            "exercise": exercise,
            "questions": questions,
        }
    )
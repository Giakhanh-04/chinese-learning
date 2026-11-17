from django.urls import path
from .views import (
    course_list,
    course_detail,
    lesson_detail,
    test_detail,
    progress_view,
    grammar_list,
    exercise_detail
)

urlpatterns = [
    path("", course_list, name="course_list"),
    path("<int:course_id>/", course_detail, name="course_detail"),
    path("lesson/<int:lesson_id>/", lesson_detail, name="lesson_detail"),
    path("test/<int:test_id>/", test_detail, name="test_detail"),
    path("progress/", progress_view, name="progress"),
    path("grammar/", grammar_list, name="grammar_list"),
    path("exercise/<int:exercise_id>/", exercise_detail, name="exercise_detail"),
]
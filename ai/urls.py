from django.urls import path
from .views import ai_chat, ai_learning_plans, ai_chat_stream

urlpatterns = [
    path("", ai_chat, name="ai_chat"),
    path(
        "learning-plans/",
        ai_learning_plans,
        name="ai_learning_plans"
    ),
    path("chat/stream/", ai_chat_stream, name="ai_chat_stream"),
]
from django.urls import path
from .views import vocabulary_list


urlpatterns = [
    path("", vocabulary_list, name="vocabulary_list"),
]
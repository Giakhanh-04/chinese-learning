from django.urls import path
from .views import translation_page

urlpatterns = [
    path("", translation_page, name="translation_page"),
]
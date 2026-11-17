from django.urls import path

from .views import test_list, test_detail


urlpatterns = [
    path("", test_list, name="test_list"),
    path("<int:test_id>/", test_detail, name="test_detail"),
]
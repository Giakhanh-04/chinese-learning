from django.contrib import admin
from django.urls import path, include
from core.views import home


urlpatterns = [
    path("admin/", admin.site.urls),
    path("vocabulary/", include("vocabulary.urls")),
    path("courses/", include("courses.urls")),
    path("ai/", include("ai.urls")),
    path("accounts/", include("accounts.urls")),
    path("premium/", include("premium.urls")),
    path("translation/", include("translation.urls")),
    path("exercise/", include("exercise.urls")),
    path("test/", include("testing.urls")),
    path("quan-tri/", include("admin_panel.urls")),
    path("community/", include("community.urls")),
    path("", home, name="home"),
]
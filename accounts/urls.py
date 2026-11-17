from django.urls import path
from .views import login_view, logout_view, register_view, profile_view, google_login
from . import password_reset

urlpatterns = [
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path("register/", register_view, name="register"),
    path("profile/", profile_view, name="profile"),
    path("google-login/", google_login, name="google_login"),
    path("quen-mat-khau/", password_reset.forgot_password_view, name="forgot_password"),
    path("dat-lai-mat-khau/<str:token>/", password_reset.reset_password_view, name="reset_password"),
]
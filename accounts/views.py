import json
import re
import secrets

from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from .models import User

from premium.models import UserPremium
from premium.utils import is_premium_user
from django.contrib.auth.hashers import check_password, identify_hasher, make_password

def _google_client_id():
    return getattr(settings, "GOOGLE_CLIENT_ID", "") or ""

def _safe_next(request):
    """Lấy trang người dùng định vào trước khi bị chuyển sang đăng nhập."""
    url = request.session.pop("next_url", "") or ""

    if url.startswith("/") and not url.startswith("//"):
        return url

    return ""
def _password_ok(user, raw):
    stored = user.password or ""

    try:
        identify_hasher(stored)
        is_hashed = True
    except ValueError:
        is_hashed = False

    if is_hashed:
        return check_password(raw, stored)

    # Mật khẩu cũ lưu chữ thường: nếu đúng thì tự nâng cấp thành mã hóa
    if stored and stored == raw:
        user.password = make_password(raw)
        user.save(update_fields=["password"])
        return True

    return False
def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        try:
            user = User.objects.get(username=username)

            if _password_ok(user, password):
                request.session["user_id"] = user.id
                request.session["username"] = user.username
                request.session["full_name"] = user.full_name
                request.session["role"] = user.role

                next_url = _safe_next(request)

                # Admin vào trang quản trị, học viên về trang đang định vào
                if user.role == "admin":
                    return redirect("admin_dashboard")

                return redirect(next_url or "home")

            messages.error(request, "Mật khẩu không đúng.")

        except User.DoesNotExist:
            messages.error(request, "Tài khoản không tồn tại.")

    return render(
        request,
        "accounts/login.html",
        {"google_client_id": _google_client_id()}
    )

# ==================================================
# ĐĂNG NHẬP BẰNG GOOGLE
# ==================================================

def _unique_username(email):
    base = re.sub(r"[^a-z0-9_.]", "", email.split("@")[0].lower()) or "user"
    base = base[:30]

    username = base
    n = 1

    while User.objects.filter(username=username).exists():
        n += 1
        username = f"{base}{n}"

    return username


@require_POST
def google_login(request):

    client_id = _google_client_id()

    if not client_id:
        return JsonResponse(
            {"success": False, "error": "Chưa cấu hình đăng nhập Google."},
            status=500
        )

    try:
        data = json.loads(request.body)
        token = data.get("credential", "")

        # Kiểm tra chữ ký, hạn dùng và Client ID của mã do Google cấp
        info = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            client_id,
            clock_skew_in_seconds=10,
        )

    except Exception as e:
        print("GOOGLE LOGIN ERROR:", type(e).__name__, e)

        return JsonResponse(
            {"success": False, "error": "Đăng nhập Google không hợp lệ."},
            status=400
        )

    if not info.get("email_verified"):
        return JsonResponse(
            {"success": False, "error": "Email Google chưa được xác minh."},
            status=400
        )

    email = info["email"].strip().lower()
    name = info.get("name") or email.split("@")[0]

    user = User.objects.filter(email__iexact=email).first()

    if not user:
        user = User.objects.create(
            username=_unique_username(email),
            email=email,
            password=make_password(secrets.token_urlsafe(32)),  # mật khẩu ngẫu nhiên
            full_name=name,
            role="student",
            hsk_level=1,
        )

    request.session.cycle_key()
    request.session["user_id"] = user.id
    request.session["username"] = user.username
    request.session["full_name"] = user.full_name
    request.session["role"] = user.role

    next_url = _safe_next(request)

    if user.role == "admin":
        destination = reverse("admin_dashboard")
    else:
        destination = next_url or reverse("home")

    return JsonResponse({"success": True, "redirect": destination})

MIN_PASSWORD_LENGTH = 6


def register_view(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        password2 = request.POST.get("password2", "")
        full_name = request.POST.get("full_name", "").strip()

        # giữ lại dữ liệu đã nhập khi báo lỗi (không giữ mật khẩu)
        values = {"full_name": full_name, "username": username, "email": email}

        def fail(message):
            messages.error(request, message)
            return render(request, "accounts/register.html", {"values": values})

        if len(password) < MIN_PASSWORD_LENGTH:
            return fail(f"Mật khẩu phải có ít nhất {MIN_PASSWORD_LENGTH} ký tự.")

        if password != password2:
            return fail("Mật khẩu nhập lại không khớp.")

        if User.objects.filter(username=username).exists():
            return fail("Tên đăng nhập đã tồn tại.")

        if User.objects.filter(email__iexact=email).exists():
            return fail("Email đã được sử dụng.")

        User.objects.create(
            username=username,
            email=email,
            password=make_password(password),
            full_name=full_name,
            role="student",
            hsk_level=1,
        )

        messages.success(
            request,
            "Đăng ký thành công. Vui lòng đăng nhập."
        )

        return redirect("login")

    return render(request, "accounts/register.html", {"values": {}})


def logout_view(request):
    request.session.flush()
    return redirect("home")


def profile_view(request):

    user_id = request.session.get("user_id")

    if not user_id:
        return redirect("login")

    # Tài khoản có thể đã bị admin xóa trong khi session vẫn còn
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        request.session.flush()
        messages.error(request, "Tài khoản không còn tồn tại.")
        return redirect("login")

    # ==============================
    # KIỂM TRA PREMIUM
    # ==============================

    premium = UserPremium.objects.filter(
        user_id=user_id,
        status="active"
    ).order_by("-end_date").first()

    premium_active = is_premium_user(user_id)

    # ==============================
    # CẬP NHẬT HỒ SƠ
    # ==============================

    if request.method == "POST":

        full_name = request.POST.get("full_name", "").strip()
        email = request.POST.get("email", "").strip()
        phone = request.POST.get("phone", "").strip()
        hsk_level = request.POST.get("hsk_level", "").strip()
        learning_goal = request.POST.get("learning_goal", "").strip()

        # Kiểm tra email đã được tài khoản khác sử dụng chưa

        if User.objects.filter(email=email).exclude(id=user.id).exists():

            messages.error(
                request,
                "Email này đã được tài khoản khác sử dụng."
            )

            return render(
                request,
                "accounts/profile.html",
                {
                    "user": user,
                    "premium": premium,
                    "premium_active": premium_active,
                }
            )

        user.full_name = full_name
        user.email = email
        user.phone = phone

        # Nếu nhập sai kiểu số thì về mặc định 1, không bị lỗi 500
        try:
            user.hsk_level = int(hsk_level) if hsk_level else 1
        except ValueError:
            user.hsk_level = 1

        user.learning_goal = learning_goal

        user.save(
            update_fields=[
                "full_name",
                "email",
                "phone",
                "hsk_level",
                "learning_goal"
            ]
        )

        # Cập nhật tên hiển thị trong session

        request.session["full_name"] = user.full_name

        messages.success(
            request,
            "Cập nhật hồ sơ thành công."
        )

        return redirect("profile")

    # ==============================
    # HIỂN THỊ HỒ SƠ
    # ==============================

    return render(
        request,
        "accounts/profile.html",
        {
            "user": user,
            "premium": premium,
            "premium_active": premium_active,
        }
    )
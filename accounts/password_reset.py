import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.core import signing
from django.core.cache import cache
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.crypto import constant_time_compare, salted_hmac

from .models import User

logger = logging.getLogger(__name__)

SITE_NAME = "Hanzii"
RESET_SALT = "accounts.password-reset"
RESET_MAX_AGE = 30 * 60          # liên kết sống 30 phút
MIN_PASSWORD_LENGTH = 6
MAX_REQUESTS_PER_EMAIL = 3       # tối đa 3 lần/giờ cho mỗi email
MAX_REQUESTS_PER_IP = 10         # tối đa 10 lần/giờ cho mỗi địa chỉ IP

GENERIC_MESSAGE = (
    "Nếu email này đã đăng ký, chúng tôi vừa gửi hướng dẫn đặt lại mật khẩu. "
    "Vui lòng kiểm tra hộp thư (kể cả mục Spam)."
)


# =========================================================
# MÃ LIÊN KẾT
# =========================================================

def _fingerprint(user):
    # Dấu vân tay của mật khẩu hiện tại: đổi mật khẩu xong thì mã cũ tự hết hiệu lực
    return salted_hmac(RESET_SALT, user.password or "").hexdigest()[:20]


def _make_token(user):
    return signing.dumps({"uid": user.id, "fp": _fingerprint(user)}, salt=RESET_SALT)


def _read_token(token):
    try:
        data = signing.loads(token, salt=RESET_SALT, max_age=RESET_MAX_AGE)
    except signing.BadSignature:      # gồm cả trường hợp hết hạn
        return None

    if not isinstance(data, dict):
        return None

    user = User.objects.filter(id=data.get("uid")).first()
    if user is None:
        return None

    if not constant_time_compare(_fingerprint(user), str(data.get("fp", ""))):
        return None

    return user


# =========================================================
# TIỆN ÍCH
# =========================================================

def _client_ip(request):
    return request.META.get("HTTP_CF_CONNECTING_IP") or request.META.get("REMOTE_ADDR", "")


def _too_many(key, limit, window=3600):
    """Đếm số lần trong một khung thời gian. True nếu vượt giới hạn."""
    cache.add(key, 0, window)
    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, window)
        count = 1
    return count > limit


def _base_url(request):
    # Chạy thật: dùng SITE_URL. Chạy thử trên máy: dùng đúng địa chỉ đang mở.
    if settings.DEBUG:
        return request.build_absolute_uri("/").rstrip("/")
    return settings.SITE_URL


# =========================================================
# BƯỚC 1: NHẬP EMAIL
# =========================================================

def forgot_password_view(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()

        if not email or "@" not in email:
            messages.error(request, "Vui lòng nhập email hợp lệ.")
            return render(request, "accounts/forgot_password.html", {"email": email})

        if (
            _too_many(f"pwreset:ip:{_client_ip(request)}", MAX_REQUESTS_PER_IP)
            or _too_many(f"pwreset:email:{email}", MAX_REQUESTS_PER_EMAIL)
        ):
            messages.error(request, "Bạn đã yêu cầu quá nhiều lần. Vui lòng thử lại sau 1 giờ.")
            return render(request, "accounts/forgot_password.html", {"email": email})

        user = User.objects.filter(email__iexact=email).first()

        if user:
            link = _base_url(request) + reverse("reset_password", args=[_make_token(user)])

            body = (
                f"Xin chào {user.full_name or user.username},\n\n"
                f"Bạn (hoặc ai đó) vừa yêu cầu đặt lại mật khẩu cho tài khoản "
                f"\"{user.username}\" trên {SITE_NAME}.\n\n"
                f"Nhấn vào liên kết dưới đây để đặt mật khẩu mới. "
                f"Liên kết có hiệu lực trong {RESET_MAX_AGE // 60} phút và chỉ dùng được một lần:\n\n"
                f"{link}\n\n"
                f"Nếu bạn không yêu cầu, hãy bỏ qua email này. Mật khẩu của bạn sẽ không thay đổi.\n"
            )

            try:
                send_mail(f"Đặt lại mật khẩu {SITE_NAME}", body, None, [user.email])
            except Exception:
                # Lỗi gửi mail chỉ ghi vào log, không báo cho người dùng biết email có tồn tại hay không
                logger.exception("Không gửi được email đặt lại mật khẩu")

        # Luôn hiện cùng một thông báo, dù email có tồn tại hay không
        messages.success(request, GENERIC_MESSAGE)
        return redirect("forgot_password")

    return render(request, "accounts/forgot_password.html")


# =========================================================
# BƯỚC 2: ĐẶT MẬT KHẨU MỚI
# =========================================================

def reset_password_view(request, token):
    user = _read_token(token)

    if user is None:
        return render(request, "accounts/reset_password.html", {"invalid": True}, status=400)

    if request.method == "POST":
        password = request.POST.get("password", "")
        password2 = request.POST.get("password2", "")

        error = None
        if len(password) < MIN_PASSWORD_LENGTH:
            error = f"Mật khẩu phải có ít nhất {MIN_PASSWORD_LENGTH} ký tự."
        elif password != password2:
            error = "Hai mật khẩu không khớp."

        if error:
            messages.error(request, error)
            return render(request, "accounts/reset_password.html", {"username": user.username})

        user.password = make_password(password)
        user.save(update_fields=["password"])

        messages.success(request, "Đặt lại mật khẩu thành công. Vui lòng đăng nhập bằng mật khẩu mới.")
        return redirect("login")

    return render(request, "accounts/reset_password.html", {"username": user.username})
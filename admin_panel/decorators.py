from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from accounts.models import User


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user_id = request.session.get("user_id")

        if not user_id:
            return redirect("login")

        # Kiểm tra role trong DB mỗi lần, không tin session
        if not User.objects.filter(id=user_id, role="admin").exists():
            messages.error(request, "Bạn không có quyền truy cập trang quản trị.")
            return redirect("home")

        return view_func(request, *args, **kwargs)

    return wrapper
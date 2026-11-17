from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import User
from premium.models import UserPremium
from premium.utils import is_premium_user

from .decorators import admin_required

# Nếu web có thêm role khác (ví dụ "teacher") thì thêm vào đây
ROLE_CHOICES = ["student", "admin"]


@admin_required
def dashboard(request):
    # Đếm theo từng người, và theo đúng logic is_premium_user của web
    premium_user_ids = (
        UserPremium.objects.filter(status="active")
        .values_list("user_id", flat=True)
        .distinct()
    )
    active_premium = sum(1 for uid in premium_user_ids if is_premium_user(uid))

    context = {
        "total_users": User.objects.count(),
        "total_students": User.objects.filter(role="student").count(),
        "active_premium": active_premium,
        "latest_users": User.objects.order_by("-id")[:5],
    }
    return render(request, "admin_panel/dashboard.html", context)


@admin_required
def user_list(request):
    q = request.GET.get("q", "").strip()
    role = request.GET.get("role", "").strip()

    users = User.objects.all().order_by("-id")

    if q:
        users = users.filter(
            Q(username__icontains=q)
            | Q(full_name__icontains=q)
            | Q(email__icontains=q)
        )

    if role in ROLE_CHOICES:
        users = users.filter(role=role)

    page_obj = Paginator(users, 15).get_page(request.GET.get("page"))

    rows = []
    for u in page_obj:
        u.is_premium = is_premium_user(u.id)
        rows.append(u)

    return render(request, "admin_panel/users.html", {
        "rows": rows,
        "page_obj": page_obj,
        "q": q,
        "role": role,
        "roles": ROLE_CHOICES,
        "total": page_obj.paginator.count,
    })


@admin_required
def user_edit(request, user_id):
    target = get_object_or_404(User, id=user_id)
    me = request.session.get("user_id")

    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        email = request.POST.get("email", "").strip()
        phone = request.POST.get("phone", "").strip()
        learning_goal = request.POST.get("learning_goal", "").strip()
        role = request.POST.get("role", target.role)
        hsk_raw = request.POST.get("hsk_level", "").strip()

        if role not in ROLE_CHOICES:
            role = target.role

        try:
            hsk_level = int(hsk_raw) if hsk_raw else 1
        except ValueError:
            hsk_level = 1

        if User.objects.filter(email=email).exclude(id=target.id).exists():
            messages.error(request, "Email này đã được tài khoản khác sử dụng.")
            return redirect("admin_user_edit", user_id=target.id)

        # Không cho admin tự hạ quyền chính mình (tránh mất quyền quản trị)
        if target.id == me and role != "admin":
            messages.error(request, "Bạn không thể tự hạ quyền của chính mình.")
            return redirect("admin_user_edit", user_id=target.id)

        target.full_name = full_name
        target.email = email
        target.phone = phone
        target.learning_goal = learning_goal
        target.role = role
        target.hsk_level = hsk_level

        target.save(update_fields=[
            "full_name", "email", "phone",
            "learning_goal", "role", "hsk_level",
        ])

        messages.success(request, "Đã cập nhật người dùng.")
        return redirect("admin_users")

    return render(request, "admin_panel/user_edit.html", {
        "target": target,
        "roles": ROLE_CHOICES,
        "levels": range(1, 7),
        "is_me": target.id == me,
    })


@admin_required
@require_POST
def user_delete(request, user_id):
    target = get_object_or_404(User, id=user_id)

    if target.id == request.session.get("user_id"):
        messages.error(request, "Bạn không thể xóa chính tài khoản của mình.")
        return redirect("admin_users")

    name = target.username
    target.delete()

    messages.success(request, f"Đã xóa tài khoản {name}.")
    return redirect("admin_users")
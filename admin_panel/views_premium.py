from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, DateTimeField, Q, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import User
from premium.models import Payment, PremiumPackage, UserPremium

from .decorators import admin_required

# ---- SỬA 3 DÒNG NÀY CHO KHỚP GIÁ TRỊ THẬT TRONG DB ----
PAID_STATUSES = ["success", "paid", "completed"]   # các trạng thái nghĩa là "đã thanh toán"
PACKAGE_STATUSES = ["active", "inactive"]          # trạng thái hiện / ẩn của gói
EXPIRED_STATUS = "expired"                         # trạng thái của gói đã kết thúc
# --------------------------------------------------------


def _month_start(dt, back=0):
    """Ngày đầu tháng, lùi `back` tháng so với dt."""
    y, m = dt.year, dt.month - back
    while m <= 0:
        m += 12
        y -= 1
    return dt.replace(year=y, month=m, day=1, hour=0, minute=0, second=0, microsecond=0)


def _paid_qs():
    # Ngày ghi nhận doanh thu = paid_at, nếu trống thì lấy created_at
    return Payment.objects.filter(status__in=PAID_STATUSES).annotate(
        pay_date=Coalesce("paid_at", "created_at", output_field=DateTimeField())
    )


def _clean_statuses(model):
    return sorted(s for s in model.objects.values_list("status", flat=True).distinct() if s)


# =========================================================
# DOANH THU & GIAO DỊCH
# =========================================================

@admin_required
def payment_list(request):
    now = timezone.localtime()
    paid = _paid_qs()

    total_revenue = paid.aggregate(t=Sum("amount"))["t"] or 0
    month_revenue = paid.filter(pay_date__gte=_month_start(now)).aggregate(t=Sum("amount"))["t"] or 0
    paid_count = paid.count()
    other_count = Payment.objects.exclude(status__in=PAID_STATUSES).count()

    # Biểu đồ 6 tháng gần nhất (cộng bằng Python để không phụ thuộc múi giờ MySQL)
    buckets = {}
    for i in range(5, -1, -1):
        d = _month_start(now, back=i)
        buckets[(d.year, d.month)] = 0

    first = _month_start(now, back=5)
    for row in paid.filter(pay_date__gte=first).values("amount", "pay_date"):
        d = timezone.localtime(row["pay_date"])
        key = (d.year, d.month)
        if key in buckets:
            buckets[key] += row["amount"] or 0

    peak = max(buckets.values()) or 1
    chart = [
        {"label": f"{m:02d}/{y}", "value": v, "px": round(v * 140 / peak)}
        for (y, m), v in buckets.items()
    ]

    # Danh sách giao dịch
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()

    payments = Payment.objects.all().order_by("-id")

    if status:
        payments = payments.filter(status=status)

    if q:
        uids = list(
            User.objects.filter(Q(username__icontains=q) | Q(full_name__icontains=q))
            .values_list("id", flat=True)
        )
        payments = payments.filter(Q(transaction_code__icontains=q) | Q(user_id__in=uids))

    page_obj = Paginator(payments, 15).get_page(request.GET.get("page"))
    rows = list(page_obj)

    users = User.objects.in_bulk([p.user_id for p in rows])
    packages = PremiumPackage.objects.in_bulk([p.package_id for p in rows])

    for p in rows:
        p.user_obj = users.get(p.user_id)
        p.package_obj = packages.get(p.package_id)
        p.is_paid = p.status in PAID_STATUSES

    return render(request, "admin_panel/payments.html", {
        "total_revenue": total_revenue,
        "month_revenue": month_revenue,
        "paid_count": paid_count,
        "other_count": other_count,
        "chart": chart,
        "rows": rows,
        "page_obj": page_obj,
        "q": q,
        "status": status,
        "statuses": _clean_statuses(Payment),
        "total": page_obj.paginator.count,
        "report_years": [now.year - i for i in range(5)],
        "report_months": range(1, 13),
        "report_year": now.year,
        "report_month": now.month,
    })


# =========================================================
# GÓI PREMIUM
# =========================================================

@admin_required
def package_list(request):
    packages = list(PremiumPackage.objects.all().order_by("-id"))

    sold = dict(
        Payment.objects.filter(status__in=PAID_STATUSES)
        .values_list("package_id")
        .annotate(n=Count("id"))
    )

    for p in packages:
        p.sold = sold.get(p.id, 0)

    return render(request, "admin_panel/packages.html", {"packages": packages})


@admin_required
def package_form(request, package_id=None):
    package = get_object_or_404(PremiumPackage, id=package_id) if package_id else None

    def render_form(form=None, current_status=None):
        # Giá trị hiển thị trong ô nhập: ưu tiên dữ liệu vừa gửi (khi báo lỗi),
        # sau đó đến dữ liệu của gói đang sửa, cuối cùng là ô trống.
        if form is not None:
            values = {
                "name": form.get("name", ""),
                "description": form.get("description", ""),
                "price": form.get("price", ""),
                "duration_days": form.get("duration_days", ""),
            }
        elif package:
            values = {
                "name": package.name,
                "description": package.description or "",
                "price": package.price,
                "duration_days": package.duration_days,
            }
        else:
            values = {"name": "", "description": "", "price": "", "duration_days": ""}

        return render(request, "admin_panel/package_form.html", {
            "package": package,
            "values": values,
            "statuses": PACKAGE_STATUSES,
            "current_status": current_status or (package.status if package else PACKAGE_STATUSES[0]),
        })

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        status = request.POST.get("status", PACKAGE_STATUSES[0])

        if status not in PACKAGE_STATUSES:
            status = PACKAGE_STATUSES[0]

        try:
            price = Decimal(request.POST.get("price", "").strip())
            duration = int(request.POST.get("duration_days", "").strip())
        except (InvalidOperation, ValueError):
            price, duration = None, None

        if not name or price is None or price < 0 or duration is None or duration <= 0:
            messages.error(request, "Vui lòng nhập tên, giá (từ 0 trở lên) và số ngày (lớn hơn 0) hợp lệ.")
            return render_form(form=request.POST, current_status=status)

        now = timezone.now()

        if package:
            package.name = name
            package.description = description
            package.price = price
            package.duration_days = duration
            package.status = status
            package.updated_at = now
            package.save(update_fields=[
                "name", "description", "price", "duration_days", "status", "updated_at",
            ])
            messages.success(request, "Đã cập nhật gói.")
        else:
            PremiumPackage.objects.create(
                name=name,
                description=description,
                price=price,
                duration_days=duration,
                status=status,
                created_at=now,
                updated_at=now,
            )
            messages.success(request, "Đã tạo gói mới.")

        return redirect("admin_packages")

    return render_form()


@admin_required
@require_POST
def package_toggle(request, package_id):
    package = get_object_or_404(PremiumPackage, id=package_id)

    visible, hidden = PACKAGE_STATUSES[0], PACKAGE_STATUSES[1]
    package.status = hidden if package.status == visible else visible
    package.updated_at = timezone.now()
    package.save(update_fields=["status", "updated_at"])

    messages.success(request, f"Đã chuyển gói '{package.name}' sang trạng thái {package.status}.")
    return redirect("admin_packages")


# =========================================================
# NGƯỜI DÙNG PREMIUM
# =========================================================

@admin_required
def premium_user_list(request):
    status = request.GET.get("status", "").strip()

    items = UserPremium.objects.all().order_by("-id")
    if status:
        items = items.filter(status=status)

    page_obj = Paginator(items, 15).get_page(request.GET.get("page"))
    rows = list(page_obj)

    users = User.objects.in_bulk([r.user_id for r in rows])
    packages = PremiumPackage.objects.in_bulk([r.package_id for r in rows])

    for r in rows:
        r.user_obj = users.get(r.user_id)
        r.package_obj = packages.get(r.package_id)

    return render(request, "admin_panel/premium_users.html", {
        "rows": rows,
        "page_obj": page_obj,
        "status": status,
        "statuses": _clean_statuses(UserPremium),
        "all_users": User.objects.order_by("username"),
        "all_packages": PremiumPackage.objects.filter(status=PACKAGE_STATUSES[0]),
        "total": page_obj.paginator.count,
    })


@admin_required
@require_POST
def premium_grant(request):
    """Tặng gói thủ công cho một người dùng (không qua thanh toán)."""
    try:
        user = User.objects.get(id=int(request.POST.get("user_id", "")))
        package = PremiumPackage.objects.get(id=int(request.POST.get("package_id", "")))
    except (ValueError, User.DoesNotExist, PremiumPackage.DoesNotExist):
        messages.error(request, "Vui lòng chọn người dùng và gói hợp lệ.")
        return redirect("admin_premium_users")

    now = timezone.now()

    UserPremium.objects.create(
        user_id=user.id,
        package_id=package.id,
        start_date=now,
        end_date=now + timedelta(days=package.duration_days),
        status="active",
        created_at=now,
    )

    messages.success(request, f"Đã tặng gói '{package.name}' cho {user.username}.")
    return redirect("admin_premium_users")


@admin_required
@require_POST
def premium_end(request, premium_id):
    item = get_object_or_404(UserPremium, id=premium_id)

    item.status = EXPIRED_STATUS
    item.end_date = timezone.now()
    item.save(update_fields=["status", "end_date"])

    messages.success(request, "Đã kết thúc gói Premium của người dùng này.")
    return redirect("admin_premium_users")
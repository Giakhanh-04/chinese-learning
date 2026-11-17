import calendar
import io
from collections import Counter
from datetime import datetime

from django.db.models import DateTimeField, Sum
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.utils import timezone

from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from accounts.models import User
from premium.models import Payment, PremiumPackage

from .decorators import admin_required
from .views_premium import PAID_STATUSES

STATUS_LABELS = {
    "success": "Thành công",
    "paid": "Thành công",
    "completed": "Thành công",
    "pending": "Chờ xử lý",
    "failed": "Thất bại",
    "cancelled": "Đã hủy",
}

METHOD_LABELS = {
    "bank_transfer": "Chuyển khoản",
    "momo": "MoMo",
    "vnpay": "VNPay",
    "paypal": "PayPal",
}

NAVY = "354A7D"
SOFT = "E9EEF8"


# =========================================================
# THU THẬP DỮ LIỆU
# =========================================================

def _to_int(value, default, low, high):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default

    return max(low, min(high, number))


def _aware(year, month):
    return timezone.make_aware(datetime(year, month, 1))


def _collect(request):

    now = timezone.localtime()

    mode = request.GET.get("period", "month")
    if mode not in ("month", "year"):
        mode = "month"

    year = _to_int(request.GET.get("year"), now.year, 2000, now.year + 1)
    month = _to_int(request.GET.get("month"), now.month, 1, 12)

    # ---------- Khoảng thời gian của kỳ báo cáo và kỳ trước ----------
    if mode == "month":
        start = _aware(year, month)
        end = _aware(year + 1, 1) if month == 12 else _aware(year, month + 1)

        prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
        prev_start = _aware(prev_year, prev_month)
        prev_end = start

        label = f"Tháng {month:02d}/{year}"
        prev_label = f"Tháng {prev_month:02d}/{prev_year}"

        series_title = "Ngày"
        keys = list(range(1, calendar.monthrange(year, month)[1] + 1))
        key_labels = {k: f"{k:02d}/{month:02d}/{year}" for k in keys}

    else:
        start = _aware(year, 1)
        end = _aware(year + 1, 1)

        prev_start = _aware(year - 1, 1)
        prev_end = start

        label = f"Năm {year}"
        prev_label = f"Năm {year - 1}"

        series_title = "Tháng"
        keys = list(range(1, 13))
        key_labels = {k: f"Tháng {k:02d}/{year}" for k in keys}

    # ---------- Ngày ghi nhận: ngày thanh toán, không có thì lấy ngày tạo ----------
    base = Payment.objects.annotate(
        event=Coalesce("paid_at", "created_at", output_field=DateTimeField())
    )

    rows = list(
        base.filter(event__gte=start, event__lt=end).order_by("event", "id")
    )

    prev_revenue = (
        base.filter(
            status__in=PAID_STATUSES,
            event__gte=prev_start,
            event__lt=prev_end,
        ).aggregate(t=Sum("amount"))["t"] or 0
    )

    undated = base.filter(event__isnull=True).count()

    # ---------- Tổng hợp ----------
    paid_rows = [p for p in rows if p.status in PAID_STATUSES]
    other_rows = [p for p in rows if p.status not in PAID_STATUSES]

    total_revenue = float(sum(p.amount or 0 for p in paid_rows))

    series = {k: [0, 0.0] for k in keys}

    for p in paid_rows:
        d = timezone.localtime(p.event)
        k = d.day if mode == "month" else d.month

        if k in series:
            series[k][0] += 1
            series[k][1] += float(p.amount or 0)

    by_package = {}
    for p in paid_rows:
        item = by_package.setdefault(p.package_id, [0, 0.0])
        item[0] += 1
        item[1] += float(p.amount or 0)

    packages = PremiumPackage.objects.in_bulk(list(by_package))

    package_rows = sorted(
        (
            (
                packages[pid].name if pid in packages else "(gói đã xóa)",
                count,
                money,
            )
            for pid, (count, money) in by_package.items()
        ),
        key=lambda r: r[2],
        reverse=True,
    )

    by_method = {}
    for p in paid_rows:
        item = by_method.setdefault(p.payment_method, [0, 0.0])
        item[0] += 1
        item[1] += float(p.amount or 0)

    method_rows = sorted(
        (
            (METHOD_LABELS.get(m, m or "Khác"), count, money)
            for m, (count, money) in by_method.items()
        ),
        key=lambda r: r[2],
        reverse=True,
    )

    status_counts = Counter(
        STATUS_LABELS.get(p.status, p.status or "Không rõ") for p in other_rows
    )

    users = User.objects.in_bulk(list({p.user_id for p in rows}))
    all_packages = PremiumPackage.objects.in_bulk(list({p.package_id for p in rows}))

    detail = []

    for p in rows:
        u = users.get(p.user_id)
        pk = all_packages.get(p.package_id)

        detail.append((
            p.id,
            p.transaction_code or "",
            u.username if u else "(đã xóa)",
            pk.name if pk else "(đã xóa)",
            float(p.amount or 0),
            METHOD_LABELS.get(p.payment_method, p.payment_method or ""),
            STATUS_LABELS.get(p.status, p.status or ""),
            timezone.localtime(p.event).strftime("%d/%m/%Y %H:%M"),
        ))

    return {
        "mode": mode,
        "label": label,
        "prev_label": prev_label,
        "generated": now.strftime("%d/%m/%Y %H:%M"),
        "total_revenue": total_revenue,
        "prev_revenue": float(prev_revenue),
        "paid_count": len(paid_rows),
        "other_count": len(other_rows),
        "total_count": len(rows),
        "status_counts": sorted(status_counts.items(), key=lambda r: -r[1]),
        "undated": undated,
        "series_title": series_title,
        "series": [(key_labels[k], series[k][0], series[k][1]) for k in keys],
        "packages": package_rows,
        "methods": method_rows,
        "detail": detail,
    }


# =========================================================
# TẠO FILE EXCEL
# =========================================================

def _style_header(ws, row, ncols):

    thin = Side(style="thin", color="D5DAE6")

    for col in range(1, ncols + 1):
        cell = ws.cell(row=row, column=col)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=NAVY)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)

    ws.row_dimensions[row].height = 24


def _style_body(ws, first_row, last_row, ncols, money_cols=(), int_cols=(), pct_cols=()):

    thin = Side(style="thin", color="E3E7F0")

    for r in range(first_row, last_row + 1):
        for c in range(1, ncols + 1):
            cell = ws.cell(row=r, column=c)
            cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)

            if c in money_cols or c in int_cols:
                cell.number_format = "#,##0"
                cell.alignment = Alignment(horizontal="right")

            if c in pct_cols:
                cell.number_format = "0.0%"
                cell.alignment = Alignment(horizontal="right")


def _widths(ws, widths):
    for index, width in enumerate(widths, start=1):
        ws.column_dimensions[ws.cell(row=1, column=index).column_letter].width = width


def _table(ws, headers, rows, start_row=1, money_cols=(), int_cols=(), pct_cols=(), total=None):
    """Ghi bảng có dòng tiêu đề; trả về dòng cuối cùng của dữ liệu."""

    for c, text in enumerate(headers, start=1):
        ws.cell(row=start_row, column=c, value=text)

    _style_header(ws, start_row, len(headers))

    r = start_row
    for r, row in enumerate(rows, start=start_row + 1):
        for c, value in enumerate(row, start=1):
            ws.cell(row=r, column=c, value=value)

    last = r

    _style_body(ws, start_row + 1, last, len(headers), money_cols, int_cols, pct_cols)

    if total is not None:
        last += 1

        for c, value in enumerate(total, start=1):
            cell = ws.cell(row=last, column=c, value=value)
            cell.font = Font(bold=True)
            cell.fill = PatternFill("solid", fgColor=SOFT)

        _style_body(ws, last, last, len(headers), money_cols, int_cols, pct_cols)

        for c in range(1, len(headers) + 1):
            ws.cell(row=last, column=c).fill = PatternFill("solid", fgColor=SOFT)
            ws.cell(row=last, column=c).font = Font(bold=True)

    return last


def build_workbook(data):

    wb = Workbook()

    revenue = data["total_revenue"]
    paid = data["paid_count"]
    average = revenue / paid if paid else 0

    # ======================= Tổng quan =======================
    ws = wb.active
    ws.title = "Tổng quan"

    ws["A1"] = "BÁO CÁO DOANH THU - HANZII"
    ws["A1"].font = Font(bold=True, size=16, color=NAVY)

    ws["A2"] = f"Kỳ báo cáo: {data['label']}"
    ws["A2"].font = Font(bold=True, size=12)

    ws["A3"] = f"Ngày xuất báo cáo: {data['generated']}"
    ws["A3"].font = Font(italic=True, color="666666")

    prev = data["prev_revenue"]

    if prev > 0:
        growth = (revenue - prev) / prev
        growth_text = f"{growth:+.1%}"
    else:
        growth_text = "Không có dữ liệu kỳ trước" if revenue == 0 else "Kỳ trước chưa có doanh thu"

    ok_rate = paid / data["total_count"] if data["total_count"] else 0

    best = max(data["series"], key=lambda r: r[2]) if data["series"] else None

    kpis = [
        ("Tổng doanh thu (đ)", revenue),
        (f"Doanh thu {data['prev_label']} (đ)", prev),
        (f"Tăng giảm so với {data['prev_label']}", growth_text),
        ("Số giao dịch thành công", paid),
        ("Doanh thu trung bình mỗi giao dịch (đ)", round(average)),
        ("Số giao dịch chưa thành công", data["other_count"]),
    ]

    for name, count in data["status_counts"]:
        kpis.append((f"      - {name}", count))

    kpis.append(("Tổng số giao dịch trong kỳ", data["total_count"]))
    kpis.append(("Tỷ lệ giao dịch thành công", ok_rate))

    if best and best[2] > 0:
        kpis.append((f"{data['series_title']} có doanh thu cao nhất", f"{best[0]} ({best[2]:,.0f} đ)"))

    last = _table(ws, ["Chỉ tiêu", "Giá trị"], kpis, start_row=5)

    for r in range(6, last + 1):
        label = ws.cell(row=r, column=1).value or ""
        value_cell = ws.cell(row=r, column=2)

        value_cell.alignment = Alignment(horizontal="right")

        if isinstance(value_cell.value, (int, float)):
            value_cell.number_format = "0.0%" if label.startswith("Tỷ lệ") else "#,##0"

    note_row = last + 2

    ws.cell(row=note_row, column=1, value="Ghi chú:").font = Font(bold=True)

    notes = [
        "- Doanh thu chỉ tính các giao dịch có trạng thái thành công.",
        "- Ngày ghi nhận là ngày thanh toán; nếu không có thì lấy ngày tạo giao dịch.",
    ]

    if data["undated"]:
        notes.append(
            f"- Có {data['undated']} giao dịch không có ngày nên không thuộc kỳ nào trong báo cáo."
        )

    for i, text in enumerate(notes, start=1):
        ws.cell(row=note_row + i, column=1, value=text).font = Font(color="666666")

    _widths(ws, [46, 34])

    # ======================= Theo ngày / tháng =======================
    ws2 = wb.create_sheet(f"Theo {data['series_title'].lower()}")

    total_row = ("Tổng", paid, revenue)

    last2 = _table(
        ws2,
        [data["series_title"], "Số giao dịch thành công", "Doanh thu (đ)"],
        data["series"],
        money_cols=(3,),
        int_cols=(2,),
        total=total_row,
    )

    _widths(ws2, [22, 24, 20])

    n = len(data["series"])

    chart = BarChart()
    chart.type = "col"
    chart.title = f"Doanh thu theo {data['series_title'].lower()} - {data['label']}"
    chart.y_axis.title = "Doanh thu (đ)"
    chart.x_axis.title = data["series_title"]
    chart.legend = None
    chart.height = 9
    chart.width = 22
    chart.x_axis.delete = False
    chart.y_axis.delete = False

    chart.add_data(Reference(ws2, min_col=3, min_row=1, max_row=n + 1), titles_from_data=True)
    chart.set_categories(Reference(ws2, min_col=1, min_row=2, max_row=n + 1))

    ws2.add_chart(chart, "E2")

    # ======================= Theo gói =======================
    ws3 = wb.create_sheet("Theo gói")

    package_rows = [
        (name, count, money, (money / revenue) if revenue else 0)
        for name, count, money in data["packages"]
    ]

    _table(
        ws3,
        ["Gói Premium", "Số lượt bán", "Doanh thu (đ)", "Tỷ trọng"],
        package_rows,
        money_cols=(3,),
        int_cols=(2,),
        pct_cols=(4,),
        total=("Tổng", paid, revenue, 1 if revenue else 0),
    )

    _widths(ws3, [32, 16, 20, 14])

    # ======================= Theo phương thức =======================
    ws4 = wb.create_sheet("Theo phương thức")

    method_rows = [
        (name, count, money, (money / revenue) if revenue else 0)
        for name, count, money in data["methods"]
    ]

    _table(
        ws4,
        ["Phương thức thanh toán", "Số giao dịch", "Doanh thu (đ)", "Tỷ trọng"],
        method_rows,
        money_cols=(3,),
        int_cols=(2,),
        pct_cols=(4,),
        total=("Tổng", paid, revenue, 1 if revenue else 0),
    )

    _widths(ws4, [30, 16, 20, 14])

    # ======================= Chi tiết giao dịch =======================
    ws5 = wb.create_sheet("Giao dịch")

    _table(
        ws5,
        ["ID", "Mã giao dịch", "Người dùng", "Gói", "Số tiền (đ)",
         "Phương thức", "Trạng thái", "Thời gian"],
        data["detail"],
        money_cols=(5,),
    )

    _widths(ws5, [8, 26, 20, 26, 16, 18, 16, 18])
    ws5.freeze_panes = "A2"

    if data["detail"]:
        ws5.auto_filter.ref = f"A1:H{len(data['detail']) + 1}"

    return wb


# =========================================================
# VIEW
# =========================================================

@admin_required
def payment_report(request):

    data = _collect(request)
    wb = build_workbook(data)

    buffer = io.BytesIO()
    wb.save(buffer)

    if data["mode"] == "month":
        # "Tháng 10/2026" -> 2026-10
        month, year = data["label"].replace("Tháng ", "").split("/")
        name = f"bao_cao_doanh_thu_{year}-{month}.xlsx"
    else:
        name = f"bao_cao_doanh_thu_{data['label'].replace('Năm ', '')}.xlsx"

    response = HttpResponse(
        buffer.getvalue(),
        content_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
    )

    response["Content-Disposition"] = f'attachment; filename="{name}"'

    return response
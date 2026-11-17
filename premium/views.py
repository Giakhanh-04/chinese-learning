from django.contrib import messages

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from django.conf import settings

from datetime import timedelta
from decimal import Decimal

import hashlib
import hmac
import urllib.parse
import uuid

from .models import PremiumPackage, UserPremium, Payment

def get_owned_packages(user_id):
    """Trả về {package_id: ngày hết hạn} của các gói đang còn hiệu lực."""
    if not user_id:
        return {}

    rows = UserPremium.objects.filter(
        user_id=user_id,
        status="active",
        end_date__gte=timezone.now(),
    ).order_by("end_date")

    owned = {}
    for r in rows:
        owned[r.package_id] = r.end_date   # lấy ngày hết hạn muộn nhất
    return owned
# ==========================================================
# VNPAY - TẠO URL THANH TOÁN
# ==========================================================

def vnpay_create_payment_url(payment, request):

    amount = int(Decimal(str(payment.amount)) * 100)

    txn_ref = f"PAY{payment.id}_{uuid.uuid4().hex[:8]}"

    payment.transaction_code = txn_ref
    payment.save(update_fields=["transaction_code"])

    # Thời gian GMT+7
    now = timezone.localtime(timezone.now())

    create_date = now.strftime("%Y%m%d%H%M%S")

    # Hết hạn sau 15 phút
    expire_date = (
        now + timedelta(minutes=15)
    ).strftime("%Y%m%d%H%M%S")

    ip_addr = request.META.get(
        "HTTP_X_FORWARDED_FOR",
        request.META.get("REMOTE_ADDR", "127.0.0.1")
    )

    if "," in ip_addr:
        ip_addr = ip_addr.split(",")[0].strip()

    params = {
        "vnp_Version": "2.1.0",
        "vnp_Command": "pay",
        "vnp_TmnCode": settings.VNPAY_TMN_CODE,
        "vnp_Amount": amount,
        "vnp_CurrCode": "VND",
        "vnp_TxnRef": txn_ref,
        "vnp_OrderInfo": f"Thanh toan Premium payment {payment.id}",
        "vnp_OrderType": "other",
        "vnp_Locale": "vn",
        "vnp_ReturnUrl": settings.VNPAY_RETURN_URL,
        "vnp_IpAddr": ip_addr,
        "vnp_CreateDate": create_date,
        "vnp_ExpireDate": expire_date,
    }

    # Sắp xếp tham số
    sorted_params = sorted(params.items())

    # Chuỗi hash theo mẫu VNPAY
    hash_data = urllib.parse.urlencode(
        sorted_params,
        quote_via=urllib.parse.quote_plus
    )

    # HMAC SHA512
    secure_hash = hmac.new(
        settings.VNPAY_HASH_SECRET.encode("utf-8"),
        hash_data.encode("utf-8"),
        hashlib.sha512
    ).hexdigest()

    # Query gửi sang VNPAY
    query_string = urllib.parse.urlencode(
        sorted_params,
        quote_via=urllib.parse.quote_plus
    )

    payment_url = (
        f"{settings.VNPAY_URL}"
        f"?{query_string}"
        f"&vnp_SecureHash={secure_hash}"
    )

    return payment_url


# ==========================================================
# PREMIUM
# ==========================================================

def premium_list(request):

    user_id = request.session.get("user_id")
    owned = get_owned_packages(user_id)

    packages = list(
        PremiumPackage.objects.filter(status="active").order_by("price")
    )

    for p in packages:
        p.owned_until = owned.get(p.id)   # None nếu chưa mua / đã hết hạn

    return render(
        request,
        "premium/premium_list.html",
        {
            "packages": packages,
            "user_id": user_id,
        }
    )

# ==========================================================
# TẠO THANH TOÁN
# ==========================================================

def payment_create(request, package_id):
    user_id = request.session.get("user_id")

    if not user_id:
        return redirect("login")

    # 1. Lấy package TRƯỚC
    package = get_object_or_404(
        PremiumPackage,
        id=package_id,
        status="active"
    )

    # 2. Rồi mới kiểm tra gói đang dùng
    owned = get_owned_packages(user_id)

    if package.id in owned:
        messages.error(
            request,
            f"Bạn đang sử dụng gói {package.name} "
            f"(hết hạn {timezone.localtime(owned[package.id]).strftime('%d/%m/%Y')}). "
            f"Vui lòng chọn gói khác."
        )
        return redirect("premium_list")

    if request.method == "POST":
        ...  # giữ nguyên phần còn lại
        payment_method = request.POST.get("payment_method", "")

        # Website chỉ hỗ trợ VNPay
        if payment_method != "vnpay":
            return render(
                request,
                "premium/payment_create.html",
                {
                    "package": package,
                    "error": "Website hiện chỉ hỗ trợ thanh toán qua VNPay."
                }
            )

        payment = Payment.objects.create(
            user_id=user_id,
            package_id=package.id,
            amount=package.price,
            payment_method="vnpay",
            status="pending",
        )

        payment_url = vnpay_create_payment_url(
            payment,
            request
        )

        return redirect(payment_url)

    return render(
        request,
        "premium/payment_create.html",
        {
            "package": package
        }
    )


# ==========================================================
# ADMIN - DANH SÁCH THANH TOÁN
# ==========================================================

def payment_admin(request):

    user_id = request.session.get("user_id")

    if not user_id:
        return redirect("login")

    if request.session.get("role") != "admin":
        return redirect("home")

    payments = Payment.objects.all().order_by(
        "-created_at",
        "-id"
    )

    return render(
        request,
        "premium/payment_admin.html",
        {
            "payments": payments,
        }
    )


# ==========================================================
# VNPAY RETURN
# ==========================================================

def vnpay_return(request):

    user_id = request.session.get("user_id")

    if not user_id:
        return redirect("login")

    input_data = request.GET.dict()

    secure_hash = input_data.pop(
        "vnp_SecureHash",
        None
    )

    input_data.pop(
        "vnp_SecureHashType",
        None
    )

    if not secure_hash:

        return render(
            request,
            "premium/payment_success.html",
            {
                "payment": None,
                "package": None,
                "start_date": None,
                "end_date": None,
                "error": "Không tìm thấy chữ ký giao dịch VNPAY."
            }
        )

    # Sắp xếp tham số
    sorted_params = sorted(input_data.items())

    hash_data = urllib.parse.urlencode(
        sorted_params,
        quote_via=urllib.parse.quote_plus
    )

    calculated_hash = hmac.new(
        settings.VNPAY_HASH_SECRET.encode("utf-8"),
        hash_data.encode("utf-8"),
        hashlib.sha512
    ).hexdigest()

    # Kiểm tra chữ ký
    if not hmac.compare_digest(
        calculated_hash,
        secure_hash
    ):

        return render(
            request,
            "premium/payment_success.html",
            {
                "payment": None,
                "package": None,
                "start_date": None,
                "end_date": None,
                "error": "Chữ ký giao dịch VNPAY không hợp lệ."
            }
        )

    txn_ref = input_data.get(
        "vnp_TxnRef"
    )

    response_code = input_data.get(
        "vnp_ResponseCode"
    )

    transaction_status = input_data.get(
        "vnp_TransactionStatus"
    )

    payment = Payment.objects.filter(
        transaction_code=txn_ref,
        user_id=user_id
    ).first()

    if not payment:

        return render(
            request,
            "premium/payment_success.html",
            {
                "payment": None,
                "package": None,
                "start_date": None,
                "end_date": None,
                "error": "Không tìm thấy giao dịch thanh toán."
            }
        )

    package = get_object_or_404(
        PremiumPackage,
        id=payment.package_id
    )

    # Kiểm tra số tiền
    vnpay_amount = input_data.get(
        "vnp_Amount"
    )

    expected_amount = int(
        Decimal(str(payment.amount)) * 100
    )

    if str(vnpay_amount) != str(expected_amount):

        return render(
            request,
            "premium/payment_success.html",
            {
                "payment": payment,
                "package": package,
                "start_date": None,
                "end_date": None,
                "error": "Số tiền giao dịch không hợp lệ."
            }
        )

    # Thanh toán thành công
    if (
        response_code == "00"
        and transaction_status == "00"
    ):

        if payment.status != "success":

            payment.status = "success"
            payment.paid_at = timezone.now()

            payment.save(
                update_fields=[
                    "status",
                    "paid_at"
                ]
            )

            start_date = timezone.now()

            end_date = start_date + timedelta(
                days=package.duration_days
            )

            UserPremium.objects.create(
                user_id=payment.user_id,
                package_id=package.id,
                start_date=start_date,
                end_date=end_date,
                status="active"
            )

        premium = UserPremium.objects.filter(
            user_id=payment.user_id,
            package_id=package.id
        ).order_by("-id").first()

        return render(
            request,
            "premium/payment_success.html",
            {
                "payment": payment,
                "package": package,
                "start_date": premium.start_date if premium else None,
                "end_date": premium.end_date if premium else None,
            }
        )

    # Thanh toán thất bại
        # Thanh toán thất bại hoặc bị hủy
    if payment.status == "pending":
        payment.status = "failed"
        payment.save(update_fields=["status"])

    if response_code == "24":
        message = "Bạn đã hủy giao dịch thanh toán."
    elif response_code == "11":
        message = "Giao dịch đã hết thời gian thanh toán."
    elif response_code == "51":
        message = "Tài khoản không đủ số dư."
    else:
        message = f"Thanh toán thất bại. Mã phản hồi VNPAY: {response_code}"

    return render(
        request,
        "premium/payment_success.html",
        {
            "payment": payment,
            "package": package,
            "start_date": None,
            "end_date": None,
            "error": message,
        }
    )


# ==========================================================
# VNPAY IPN
# ==========================================================

def vnpay_ipn(request):

    input_data = request.GET.dict()

    secure_hash = input_data.pop(
        "vnp_SecureHash",
        None
    )

    input_data.pop(
        "vnp_SecureHashType",
        None
    )

    if not secure_hash:
        return JsonResponse({
            "RspCode": "97",
            "Message": "Invalid Signature"
        })

    # Sắp xếp tham số
    sorted_params = sorted(input_data.items())

    # Tạo chuỗi hash giống VNPAY Return
    hash_data = urllib.parse.urlencode(
        sorted_params,
        quote_via=urllib.parse.quote_plus
    )

    calculated_hash = hmac.new(
        settings.VNPAY_HASH_SECRET.encode("utf-8"),
        hash_data.encode("utf-8"),
        hashlib.sha512
    ).hexdigest()

    # Kiểm tra chữ ký
    if not hmac.compare_digest(
        calculated_hash,
        secure_hash
    ):
        return JsonResponse({
            "RspCode": "97",
            "Message": "Invalid Signature"
        })

    txn_ref = input_data.get(
        "vnp_TxnRef"
    )

    response_code = input_data.get(
        "vnp_ResponseCode"
    )

    transaction_status = input_data.get(
        "vnp_TransactionStatus"
    )

    payment = Payment.objects.filter(
        transaction_code=txn_ref
    ).first()

    if not payment:
        return JsonResponse({
            "RspCode": "01",
            "Message": "Order Not Found"
        })

    # Nếu giao dịch đã xử lý rồi
    if payment.status == "success":
        return JsonResponse({
            "RspCode": "02",
            "Message": "Order Already Confirmed"
        })

    # Kiểm tra số tiền
    vnpay_amount = input_data.get(
        "vnp_Amount"
    )

    expected_amount = int(
        Decimal(str(payment.amount)) * 100
    )

    if str(vnpay_amount) != str(expected_amount):
        return JsonResponse({
            "RspCode": "04",
            "Message": "Invalid Amount"
        })

    package = get_object_or_404(
        PremiumPackage,
        id=payment.package_id
    )

    # Thanh toán thành công
    if (
        response_code == "00"
        and transaction_status == "00"
    ):

        payment.status = "success"
        payment.paid_at = timezone.now()

        payment.save(
            update_fields=[
                "status",
                "paid_at"
            ]
        )

        # Kiểm tra Premium đã được tạo chưa
        existing_premium = UserPremium.objects.filter(
            user_id=payment.user_id,
            package_id=package.id,
            status="active",
            end_date__gte=timezone.now()
        ).order_by("-id").first()

        if not existing_premium:

            start_date = timezone.now()

            end_date = start_date + timedelta(
                days=package.duration_days
            )

            UserPremium.objects.create(
                user_id=payment.user_id,
                package_id=package.id,
                start_date=start_date,
                end_date=end_date,
                status="active"
            )

        return JsonResponse({
            "RspCode": "00",
            "Message": "Confirm Success"
        })

    # Thanh toán thất bại
    payment.status = "failed"

    payment.save(
        update_fields=["status"]
    )

    return JsonResponse({
        "RspCode": "00",
        "Message": "Confirm Success"
    })
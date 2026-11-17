from django.urls import path

from .views import (
    premium_list,
    payment_create,
    payment_admin,
    vnpay_return,
    vnpay_ipn,
)

urlpatterns = [
    path("", premium_list, name="premium_list"),
    path("payment/<int:package_id>/", payment_create, name="payment_create"),
    path("payment/vnpay-return/", vnpay_return, name="vnpay_return"),
    path("payment/vnpay-ipn/", vnpay_ipn, name="vnpay_ipn"),
    path("admin/payments/", payment_admin, name="payment_admin"),
]
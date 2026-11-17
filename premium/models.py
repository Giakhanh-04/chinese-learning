from django.db import models


class PremiumPackage(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    duration_days = models.IntegerField()

    status = models.CharField(
        max_length=10,
        choices=[
            ("active", "Active"),
            ("inactive", "Inactive"),
        ],
        default="active",
        null=True,
    )

    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "premium_packages"

    def __str__(self):
        return self.name


class UserPremium(models.Model):
    id = models.AutoField(primary_key=True)
    user_id = models.IntegerField()
    package_id = models.IntegerField()
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()

    status = models.CharField(
        max_length=10,
        choices=[
            ("active", "Active"),
            ("expired", "Expired"),
            ("cancelled", "Cancelled"),
        ],
        default="active",
        null=True,
    )

    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "user_premium"


class Payment(models.Model):
    id = models.AutoField(primary_key=True)
    user_id = models.IntegerField()
    package_id = models.IntegerField()
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    payment_method = models.CharField(
        max_length=20,
        choices=[
            ("bank_transfer", "Bank Transfer"),
            ("momo", "MoMo"),
            ("vnpay", "VNPay"),
            ("paypal", "PayPal"),
        ],
    )

    transaction_code = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=10,
        choices=[
            ("pending", "Pending"),
            ("success", "Success"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
        ],
        default="pending",
        null=True,
    )

    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "payments"
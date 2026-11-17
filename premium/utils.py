from django.utils import timezone

from .models import UserPremium


def is_premium_user(user_id):

    if not user_id:
        return False

    now = timezone.now()

    premium = UserPremium.objects.filter(
        user_id=user_id,
        status="active",
        start_date__lte=now,
        end_date__gte=now
    ).first()

    if premium:
        return True

    # Nếu Premium đã hết hạn
    UserPremium.objects.filter(
        user_id=user_id,
        status="active",
        end_date__lt=now
    ).update(
        status="expired"
    )

    return False
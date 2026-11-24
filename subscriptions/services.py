from subscriptions.models import KitchenSafeSubscription


def get_user_kitchen_safe_subscription(user):
    """Return the customer's current (non-cancelled) KITCHENSafe subscription, if any."""
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    return (
        KitchenSafeSubscription.objects.filter(user=user)
        .exclude(status=KitchenSafeSubscription.Status.CANCELLED)
        .order_by('-created_at')
        .first()
    )

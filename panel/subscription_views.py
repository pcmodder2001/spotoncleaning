from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from audit.actions import SUBSCRIPTION_PAYMENT_RECORDED, SUBSCRIPTION_UPDATED
from audit.services import log_action
from panel.decorators import admin_required
from subscriptions.forms import SubscriptionPaymentForm, SubscriptionStatusForm
from subscriptions.models import KitchenSafeSubscription


@admin_required
def subscription_list_view(request):
    status = request.GET.get('status', '')
    subscriptions = (
        KitchenSafeSubscription.objects.select_related('user')
        .prefetch_related('payments')
    )
    if status:
        subscriptions = subscriptions.filter(status=status)
    subscriptions = subscriptions.order_by('-created_at')
    return render(request, 'panel/subscriptions/list.html', {
        'subscriptions': subscriptions,
        'status_filter': status,
        'status_choices': KitchenSafeSubscription.Status.choices,
        'plan_name': KitchenSafeSubscription.PLAN_NAME,
    })


@admin_required
def subscription_detail_view(request, pk):
    subscription = get_object_or_404(
        KitchenSafeSubscription.objects.select_related('user').prefetch_related(
            'payments',
            'payments__recorded_by',
        ),
        pk=pk,
    )
    payment_form = SubscriptionPaymentForm(
        default_amount=subscription.monthly_price,
        initial={'payment_date': timezone.localdate()},
    )
    status_form = SubscriptionStatusForm(instance=subscription)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_payment':
            payment_form = SubscriptionPaymentForm(request.POST)
            if payment_form.is_valid():
                payment = payment_form.save(commit=False)
                payment.subscription = subscription
                payment.recorded_by = request.user
                payment.save()
                if subscription.status == KitchenSafeSubscription.Status.PENDING:
                    subscription.mark_active()
                log_action(
                    SUBSCRIPTION_PAYMENT_RECORDED,
                    (
                        f'Recorded £{payment.amount} payment for '
                        f'{subscription.contact_name} on {payment.payment_date}.'
                    ),
                    request=request,
                    target_type='subscription',
                    target_id=subscription.pk,
                    target_label=f'KITCHENSafe #{subscription.pk}',
                    metadata={
                        'amount': str(payment.amount),
                        'payment_date': payment.payment_date.isoformat(),
                        'method': payment.method,
                    },
                )
                messages.success(
                    request,
                    f'Payment of £{payment.amount} recorded for {payment.payment_date:%d %b %Y}.',
                )
                return redirect('panel:subscription_detail', pk=subscription.pk)
        elif action == 'update_status':
            status_form = SubscriptionStatusForm(request.POST, instance=subscription)
            if status_form.is_valid():
                updated = status_form.save(commit=False)
                if (
                    updated.status == KitchenSafeSubscription.Status.ACTIVE
                    and not updated.started_at
                ):
                    updated.started_at = timezone.now()
                if updated.status == KitchenSafeSubscription.Status.CANCELLED:
                    updated.cancelled_at = timezone.now()
                elif updated.status != KitchenSafeSubscription.Status.CANCELLED:
                    updated.cancelled_at = None
                updated.save()
                log_action(
                    SUBSCRIPTION_UPDATED,
                    f'Updated KITCHENSafe #{subscription.pk} status to {updated.get_status_display()}.',
                    request=request,
                    target_type='subscription',
                    target_id=subscription.pk,
                    target_label=f'KITCHENSafe #{subscription.pk}',
                    metadata={'status': updated.status},
                )
                messages.success(request, 'Subscription updated.')
                return redirect('panel:subscription_detail', pk=subscription.pk)

    return render(request, 'panel/subscriptions/detail.html', {
        'subscription': subscription,
        'payments': subscription.payments.all(),
        'payment_form': payment_form,
        'status_form': status_form,
        'plan_name': KitchenSafeSubscription.PLAN_NAME,
    })

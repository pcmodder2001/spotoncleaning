from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse

from audit.actions import SUBSCRIPTION_CREATED, SUBSCRIPTION_UPDATED
from audit.services import log_action
from subscriptions.forms import KitchenSafeManageForm, KitchenSafeSignupForm
from subscriptions.models import KitchenSafeSubscription
from subscriptions.services import get_user_kitchen_safe_subscription


@login_required
def kitchen_safe_signup_view(request):
    existing = get_user_kitchen_safe_subscription(request.user)
    if existing:
        return redirect('subscriptions:kitchen_safe_manage')

    initial = {
        'contact_name': request.user.full_name,
        'contact_phone': request.user.phone_number or '',
        'contact_email': request.user.email,
        'photo_email_1': request.user.email,
    }
    if not request.user.is_business_account:
        from accounts.addresses import get_default_saved_address

        default_address = get_default_saved_address(request.user)
        if default_address:
            initial.update({
                'address_line_1': default_address.address_line_1,
                'address_line_2': default_address.address_line_2 or '',
                'city': default_address.city,
                'postcode': default_address.postcode,
            })

    if request.method == 'POST':
        form = KitchenSafeSignupForm(request.POST)
        if form.is_valid():
            subscription = form.save(user=request.user)
            log_action(
                SUBSCRIPTION_CREATED,
                (
                    f'KITCHENSafe signup for {subscription.contact_name} '
                    f'({subscription.postcode}) by {request.user.email}.'
                ),
                request=request,
                target_type='subscription',
                target_id=subscription.pk,
                target_label=f'KITCHENSafe #{subscription.pk}',
                metadata={
                    'plan': KitchenSafeSubscription.PLAN_CODE,
                    'monthly_price': str(subscription.monthly_price),
                    'photo_emails': subscription.photo_emails,
                },
            )
            messages.success(
                request,
                'Thanks — your KITCHENSafe subscription is set up. We’ll confirm bank transfer details shortly.',
            )
            return redirect('subscriptions:kitchen_safe_manage')
    else:
        form = KitchenSafeSignupForm(initial=initial)

    return render(request, 'subscriptions/kitchen_safe_signup.html', {
        'form': form,
        'plan_name': KitchenSafeSubscription.PLAN_NAME,
        'monthly_price': KitchenSafeSubscription.DEFAULT_MONTHLY_PRICE,
        'login_url': reverse('accounts:login'),
    })


@login_required
def kitchen_safe_manage_view(request):
    subscription = get_user_kitchen_safe_subscription(request.user)
    if not subscription:
        return redirect('website:kitchen_safe')

    if request.method == 'POST':
        form = KitchenSafeManageForm(request.POST, instance=subscription)
        if form.is_valid():
            form.save()
            log_action(
                SUBSCRIPTION_UPDATED,
                (
                    f'Customer updated KITCHENSafe #{subscription.pk} '
                    f'({subscription.contact_name}).'
                ),
                request=request,
                target_type='subscription',
                target_id=subscription.pk,
                target_label=f'KITCHENSafe #{subscription.pk}',
                metadata={'photo_emails': subscription.photo_emails},
            )
            messages.success(request, 'Your KITCHENSafe details have been updated.')
            return redirect('subscriptions:kitchen_safe_manage')
    else:
        form = KitchenSafeManageForm(instance=subscription)

    return render(request, 'subscriptions/kitchen_safe_manage.html', {
        'form': form,
        'subscription': subscription,
        'plan_name': KitchenSafeSubscription.PLAN_NAME,
        'monthly_price': subscription.monthly_price,
        'latest_payment': subscription.latest_payment,
    })


@login_required
def kitchen_safe_thanks_view(request):
    return redirect('subscriptions:kitchen_safe_manage')

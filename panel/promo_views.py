from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from bookings.models import PromoCode
from bookings.promo import bookings_using_promo
from audit.actions import PROMO_CREATED, PROMO_DELETED, PROMO_UPDATED
from audit.services import log_action
from panel.decorators import sysadmin_required


@sysadmin_required
def promo_list_view(request):
    promos = PromoCode.objects.all()
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            code = request.POST.get('code', '').strip()
            auto_apply = request.POST.get('auto_apply') == '1'
            min_appliances = request.POST.get('min_appliance_count') or None
            if not code:
                messages.error(request, 'Enter a promo code.')
            elif auto_apply and not min_appliances:
                messages.error(request, 'Auto promos need a minimum appliance count.')
            else:
                try:
                    max_uses = request.POST.get('max_uses') or None
                    PromoCode.objects.create(
                        code=code,
                        description=request.POST.get('description', ''),
                        discount_type=request.POST.get(
                            'discount_type', PromoCode.DiscountType.PERCENT
                        ),
                        discount_value=Decimal(request.POST.get('discount_value', '0')),
                        max_uses=int(max_uses) if max_uses else None,
                        min_order_amount=Decimal(request.POST.get('min_order_amount') or '0'),
                        auto_apply=request.POST.get('auto_apply') == '1',
                        stackable=request.POST.get('stackable') == '1',
                        count_addons=request.POST.get('count_addons') == '1',
                        requires_account=request.POST.get('requires_account') == '1',
                        first_order_only=request.POST.get('first_order_only') == '1',
                        requires_signup_or_mailing_list=(
                            request.POST.get('requires_signup_or_mailing_list') == '1'
                        ),
                        min_appliance_count=(
                            int(request.POST.get('min_appliance_count'))
                            if request.POST.get('min_appliance_count')
                            else None
                        ),
                    )
                    log_action(
                        PROMO_CREATED,
                        f'Created promo code {code.upper()}.',
                        request=request,
                        target_type='promo',
                        target_label=code.upper(),
                    )
                    messages.success(request, f'Promo code {code.upper()} created.')
                except (InvalidOperation, ValueError):
                    messages.error(request, 'Could not create promo code. Check values are valid.')
        elif action == 'toggle':
            promo = get_object_or_404(PromoCode, pk=request.POST.get('promo_id'))
            promo.active = not promo.active
            promo.save(update_fields=['active'])
            log_action(
                PROMO_UPDATED,
                f'{"Activated" if promo.active else "Deactivated"} promo code {promo.code}.',
                request=request,
                target_type='promo',
                target_id=promo.pk,
                target_label=promo.code,
            )
            messages.success(request, f'{promo.code} updated.')
        elif action == 'toggle_count_addons':
            promo = get_object_or_404(PromoCode, pk=request.POST.get('promo_id'))
            promo.count_addons = not promo.count_addons
            promo.save(update_fields=['count_addons'])
            log_action(
                PROMO_UPDATED,
                (
                    f'{"Enabled" if promo.count_addons else "Disabled"} add-ons counting '
                    f'for promo code {promo.code}.'
                ),
                request=request,
                target_type='promo',
                target_id=promo.pk,
                target_label=promo.code,
            )
            messages.success(
                request,
                (
                    f'{promo.code}: add-ons now count toward the minimum.'
                    if promo.count_addons
                    else f'{promo.code}: only main appliances count toward the minimum.'
                ),
            )
        elif action == 'delete':
            if not request.user.is_sysadmin:
                messages.error(request, 'Only system admins can delete promo codes.')
            else:
                promo = get_object_or_404(PromoCode, pk=request.POST.get('promo_id'))
                code = promo.code
                promo_id = promo.pk
                promo.delete()
                log_action(
                    PROMO_DELETED,
                    f'Deleted promo code {code}.',
                    request=request,
                    target_type='promo',
                    target_id=promo_id,
                    target_label=code,
                )
                messages.success(request, f'Promo code {code} deleted.')
        return redirect('panel:promo_list')

    return render(request, 'panel/promos/list.html', {
        'promos': promos,
        'can_delete_promos': request.user.is_sysadmin,
    })


@sysadmin_required
def promo_detail_view(request, pk):
    promo = get_object_or_404(PromoCode, pk=pk)
    bookings = bookings_using_promo(promo)
    return render(request, 'panel/promos/detail.html', {
        'promo': promo,
        'bookings': bookings,
        'usage_count': bookings.count(),
    })

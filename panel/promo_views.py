from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from bookings.models import PromoCode
from audit.actions import PROMO_CREATED, PROMO_DELETED, PROMO_UPDATED
from audit.services import log_action
from panel.decorators import admin_required


@admin_required
def promo_list_view(request):
    promos = PromoCode.objects.all()
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            code = request.POST.get('code', '').strip()
            if not code:
                messages.error(request, 'Enter a promo code.')
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
        elif action == 'delete':
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

    return render(request, 'panel/promos/list.html', {'promos': promos})

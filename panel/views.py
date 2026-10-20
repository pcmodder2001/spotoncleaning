from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from bookings.forms import AdminBookingForm, AdminCreateBookingForm, BookingForm
from bookings.models import (
    BlockedDate,
    Booking,
    BookingPhoto,
    BookingStatus,
    TimeSlot,
    WeeklySchedule,
)
from bookings.checklist import checklist_from_post, merge_checklist
from bookings.promo import release_booking_promos
from bookings.utils import cancel_booking
from bookings.notifications import send_booking_created_email, send_booking_status_email
from accounts.account_types import AccountType
from accounts.roles import UserRole
from audit.actions import (
    AVAILABILITY_UPDATED,
    BOOKING_CANCELLED,
    BOOKING_CREATED,
    BOOKING_DELETED,
    BOOKING_STATUS_CHANGED,
    BOOKING_UPDATED,
    ENQUIRY_DELETED,
    ENQUIRY_READ,
    HOMEPAGE_OFFER_UPDATED,
    SERVICE_CREATED,
    SERVICE_DELETED,
    SERVICE_UPDATED,
    USER_DELETED,
    USER_UPDATED,
)
from audit.services import log_action
from panel.business_insights import booking_business_payload, user_business_summary
from panel.decorators import admin_required, panel_required, sysadmin_required
from panel.marketing_stats import get_marketing_dashboard_context
from panel.email_debug import (
    EMAIL_TEST_TYPES,
    get_email_config_summary,
    get_sysadmin_recipients,
    parse_debug_recipients,
    send_all_test_emails,
    send_test_email,
)
from services.models import Service, ServiceType
from website.forms import HomepageOfferForm
from website.models import ContactMessage, HomepageOffer

User = get_user_model()


@panel_required
def dashboard_view(request):
    from hr.services import redirect_if_onboarding_required

    onboarding_redirect = redirect_if_onboarding_required(request)
    if onboarding_redirect:
        return onboarding_redirect

    today = timezone.localdate()
    stats = {
        'total_users': User.objects.count(),
        'business_accounts': User.objects.filter(account_type=AccountType.BUSINESS).count(),
        'total_bookings': Booking.objects.count(),
        'today_bookings': Booking.objects.filter(date=today).exclude(status=BookingStatus.CANCELLED).count(),
        'pending_bookings': Booking.objects.filter(status=BookingStatus.PENDING).count(),
        'confirmed_bookings': Booking.objects.filter(status=BookingStatus.CONFIRMED).count(),
        'completed_jobs': Booking.objects.filter(status=BookingStatus.COMPLETED).count(),
    }
    recent_bookings = Booking.objects.select_related(
        'user',
        'user__business_profile',
        'rental_property',
        'service',
    ).order_by('-created_at')[:10]
    recent_users = User.objects.select_related('business_profile').order_by('-date_joined')[:10]
    unread_messages = ContactMessage.objects.filter(is_read=False).count()
    return render(request, 'panel/dashboard.html', {
        'stats': stats,
        'recent_bookings': recent_bookings,
        'recent_users': recent_users,
        'unread_messages': unread_messages,
    })


@sysadmin_required
def user_list_view(request):
    query = request.GET.get('q', '')
    account_type = request.GET.get('account_type', '')
    users = User.objects.select_related('business_profile').annotate(
        property_count=Count('properties', distinct=True),
    )
    if query:
        users = users.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
            | Q(phone_number__icontains=query)
            | Q(business_profile__company_name__icontains=query)
        )
    if account_type:
        users = users.filter(account_type=account_type)
    return render(request, 'panel/users/list.html', {
        'users': users,
        'query': query,
        'account_type_filter': account_type,
        'account_type_choices': AccountType.choices,
    })


@sysadmin_required
def user_edit_view(request, pk):
    user = get_object_or_404(
        User.objects.select_related('business_profile').annotate(
            property_count=Count('properties', distinct=True),
            booking_count=Count('bookings', distinct=True),
        ),
        pk=pk,
    )
    if request.method == 'POST':
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.phone_number = request.POST.get('phone_number', user.phone_number)
        if not user.is_sysadmin:
            user.email = request.POST.get('email', user.email)
            user.is_active = request.POST.get('is_active') == 'on'
            role = request.POST.get('role', user.role)
            if role in UserRole.values:
                user.role = role
        else:
            user.is_active = True
        user.save()
        log_action(
            USER_UPDATED,
            f'Updated user {user.email} (role: {user.get_role_display()}).',
            request=request,
            target_type='user',
            target_id=user.pk,
            target_label=user.email,
            metadata={'role': user.role, 'is_active': user.is_active},
        )
        messages.success(request, f'User {user.email} updated successfully.')
        return redirect('panel:user_list')
    return render(request, 'panel/users/edit.html', {
        'edit_user': user,
        'role_choices': UserRole.choices,
        'business_summary': user_business_summary(user),
        'partner_properties': user.properties.all() if user.is_business_account else [],
    })


@sysadmin_required
@require_POST
def user_delete_view(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user == request.user:
        messages.error(request, 'You cannot delete your own account.')
        return redirect('panel:user_list')
    if user.is_sysadmin:
        messages.error(request, 'The system administrator account cannot be deleted.')
        return redirect('panel:user_list')
    email = user.email
    user_id = user.pk
    try:
        user.delete()
    except PermissionDenied:
        messages.error(request, 'The system administrator account cannot be deleted.')
        return redirect('panel:user_list')
    log_action(
        USER_DELETED,
        f'Deleted user {email}.',
        request=request,
        target_type='user',
        target_id=user_id,
        target_label=email,
    )
    messages.success(request, f'User {email} deleted.')
    return redirect('panel:user_list')


@panel_required
def booking_list_view(request):
    query = request.GET.get('q', '')
    status = request.GET.get('status', '')
    date_filter = request.GET.get('date', '')
    partner_filter = request.GET.get('partner', '')
    bookings = Booking.objects.select_related(
        'user',
        'user__business_profile',
        'rental_property',
        'service',
        'time_slot',
    )
    if query:
        bookings = bookings.filter(
            Q(user__email__icontains=query)
            | Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(postcode__icontains=query)
            | Q(city__icontains=query)
            | Q(user__business_profile__company_name__icontains=query)
            | Q(rental_property__reference__icontains=query)
            | Q(guest_email__icontains=query)
        )
    if status:
        bookings = bookings.filter(status=status)
    if date_filter:
        bookings = bookings.filter(date=date_filter)
    if partner_filter == '1':
        bookings = bookings.filter(user__account_type=AccountType.BUSINESS)
    bookings = bookings.order_by('-date', '-time_slot__time', '-pk')
    paginator = Paginator(bookings, 50)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'panel/bookings/list.html', {
        'page_obj': page_obj,
        'query': query,
        'status_filter': status,
        'date_filter': date_filter,
        'partner_filter': partner_filter,
        'status_choices': BookingStatus.choices,
        'can_manage_site': request.user.can_manage_site,
        'is_sysadmin': request.user.is_sysadmin,
    })


@admin_required
def booking_create_view(request):
    if request.method == 'POST':
        form = AdminCreateBookingForm(request.POST)
        if form.is_valid():
            booking = form.save()
            metadata = {
                'created_by_admin': True,
                'services': booking.service_summary,
            }
            if form.schedule_warnings:
                metadata['schedule_warnings'] = form.schedule_warnings
            log_action(
                BOOKING_CREATED,
                f'Admin created booking #{booking.pk} for {booking.contact_full_name} on {booking.date}.',
                request=request,
                target_type='booking',
                target_id=booking.pk,
                target_label=f'Booking #{booking.pk}',
                metadata=metadata,
            )
            if booking.status == BookingStatus.CONFIRMED:
                email_sent = send_booking_status_email(booking)
            else:
                email_sent = send_booking_created_email(booking)
            if email_sent:
                success_message = f'Booking #{booking.pk} created and the customer has been emailed.'
            else:
                success_message = (
                    f'Booking #{booking.pk} created, but the customer email could not be sent.'
                )
            if form.schedule_warnings:
                messages.warning(
                    request,
                    f'{success_message} Schedule conflicts were ignored: '
                    + '; '.join(form.schedule_warnings),
                )
            else:
                messages.success(request, success_message)
            return redirect('panel:booking_edit', pk=booking.pk)
    else:
        form = AdminCreateBookingForm()

    selected_service_ids = set()
    if form.is_bound and form.data.getlist('services'):
        selected_service_ids = {int(pk) for pk in form.data.getlist('services') if pk.isdigit()}

    services = form.fields['services'].queryset
    return render(request, 'panel/bookings/create.html', {
        'form': form,
        'oven_services': services.filter(service_type=ServiceType.OVEN),
        'addon_services': services.filter(service_type=ServiceType.ADDON),
        'selected_service_ids': selected_service_ids,
        'schedule_warnings': getattr(form, 'schedule_warnings', []),
    })


@admin_required
def booking_edit_view(request, pk):
    booking = get_object_or_404(
        Booking.objects.select_related('user', 'user__business_profile', 'rental_property'),
        pk=pk,
    )
    old_status = booking.status
    if request.method == 'POST':
        form = AdminBookingForm(request.POST, instance=booking)
        if form.is_valid():
            booking = form.save()
            booking.access_instructions = request.POST.get('access_instructions', '')
            booking.staff_notes = request.POST.get('staff_notes', '')
            booking.checklist = checklist_from_post(request.POST)
            booking.save(update_fields=[
                'access_instructions', 'staff_notes', 'checklist', 'updated_at',
            ])
            for photo_type, field_name in (
                (BookingPhoto.PhotoType.BEFORE, 'photo_before'),
                (BookingPhoto.PhotoType.AFTER, 'photo_after'),
            ):
                if field_name in request.FILES:
                    BookingPhoto.objects.create(
                        booking=booking,
                        image=request.FILES[field_name],
                        photo_type=photo_type,
                    )
            if booking.status != old_status:
                send_booking_status_email(booking)
            log_action(
                BOOKING_UPDATED,
                f'Updated booking #{booking.pk} (status: {booking.get_status_display()}).',
                request=request,
                target_type='booking',
                target_id=booking.pk,
                target_label=f'Booking #{booking.pk} — {booking.contact_full_name}',
                metadata={'old_status': old_status, 'new_status': booking.status},
            )
            messages.success(request, 'Booking updated successfully.')
            return redirect('panel:booking_list')
    else:
        form = AdminBookingForm(instance=booking)

    selected_service_ids = set()
    if form.is_bound and form.data.getlist('services'):
        selected_service_ids = {int(pk) for pk in form.data.getlist('services') if pk.isdigit()}
    elif booking.pk:
        selected_service_ids = set(booking.get_services().values_list('pk', flat=True))

    services = form.fields['services'].queryset
    return render(request, 'panel/bookings/edit.html', {
        'form': form,
        'booking': booking,
        'business_insights': booking_business_payload(booking),
        'oven_services': services.filter(service_type=ServiceType.OVEN),
        'addon_services': services.filter(service_type=ServiceType.ADDON),
        'selected_service_ids': selected_service_ids,
        'checklist_items': merge_checklist(booking.checklist),
        'photos': booking.photos.all(),
    })


@admin_required
@require_POST
def booking_cancel_view(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    next_url = request.POST.get('next') or 'panel:booking_list'
    if cancel_booking(booking):
        log_action(
            BOOKING_CANCELLED,
            f'Admin cancelled booking #{booking.pk} ({booking.contact_full_name}).',
            request=request,
            target_type='booking',
            target_id=booking.pk,
            target_label=f'Booking #{booking.pk}',
        )
        messages.success(request, f'Booking #{booking.pk} cancelled.')
    else:
        messages.info(request, f'Booking #{booking.pk} is already cancelled.')
    return redirect(next_url)


@admin_required
@require_POST
def booking_confirm_view(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    next_url = request.POST.get('next') or 'panel:booking_list'

    if booking.status != BookingStatus.PENDING:
        messages.warning(request, f'Booking #{booking.pk} is not pending and cannot be confirmed.')
        return redirect(next_url)

    booking.status = BookingStatus.CONFIRMED
    booking.save(update_fields=['status', 'updated_at'])
    email_sent = send_booking_status_email(booking)
    log_action(
        BOOKING_STATUS_CHANGED,
        f'Confirmed booking #{booking.pk} ({booking.contact_full_name}).',
        request=request,
        target_type='booking',
        target_id=booking.pk,
        target_label=f'Booking #{booking.pk}',
        metadata={
            'old_status': BookingStatus.PENDING,
            'new_status': BookingStatus.CONFIRMED,
            'email_sent': email_sent,
        },
    )
    if email_sent:
        messages.success(
            request,
            f'Booking #{booking.pk} confirmed. Confirmation email sent to {booking.contact_email}.',
        )
    else:
        messages.warning(
            request,
            f'Booking #{booking.pk} confirmed, but the confirmation email could not be sent.',
        )
    return redirect(next_url)


@sysadmin_required
@require_POST
def booking_delete_view(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    next_url = request.POST.get('next') or 'panel:booking_list'
    booking_id = booking.pk
    customer = booking.contact_full_name

    if booking.status != BookingStatus.CANCELLED and booking.applied_promo_ids():
        release_booking_promos(booking)

    for photo in booking.photos.all():
        photo.image.delete(save=False)

    booking.delete()
    log_action(
        BOOKING_DELETED,
        f'Deleted booking #{booking_id} ({customer}).',
        request=request,
        target_type='booking',
        target_id=booking_id,
        target_label=f'Booking #{booking_id}',
    )
    messages.success(request, f'Booking #{booking_id} deleted.')
    return redirect(next_url)


@sysadmin_required
def availability_view(request):
    from datetime import datetime, timedelta

    weekly_schedule = WeeklySchedule.objects.all()
    time_slots = TimeSlot.objects.all()
    today = timezone.localdate()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'weekly':
            for schedule in weekly_schedule:
                schedule.is_available = request.POST.get(f'day_{schedule.day_of_week}') == 'on'
                schedule.save(update_fields=['is_available'])
            log_action(AVAILABILITY_UPDATED, 'Updated weekly schedule.', request=request, target_type='availability')
            messages.success(request, 'Weekly schedule updated.')
        elif action == 'add_slot':
            time_str = request.POST.get('time')
            if time_str:
                time_obj = datetime.strptime(time_str, '%H:%M').time()
                TimeSlot.objects.get_or_create(time=time_obj)
                log_action(AVAILABILITY_UPDATED, f'Added time slot {time_str}.', request=request, target_type='availability')
                messages.success(request, f'Time slot {time_str} added.')
        elif action == 'toggle_slot':
            slot = get_object_or_404(TimeSlot, pk=request.POST.get('slot_id'))
            slot.active = not slot.active
            slot.save(update_fields=['active'])
            log_action(AVAILABILITY_UPDATED, f'Toggled time slot {slot}.', request=request, target_type='availability')
            messages.success(request, f'Time slot {slot} updated.')
        elif action == 'delete_slot':
            if not request.user.is_sysadmin:
                messages.error(request, 'Only system admins can delete time slots.')
            else:
                slot = get_object_or_404(TimeSlot, pk=request.POST.get('slot_id'))
                slot.delete()
                log_action(AVAILABILITY_UPDATED, 'Deleted a time slot.', request=request, target_type='availability')
                messages.success(request, 'Time slot deleted.')
        elif action == 'block_date':
            date_str = request.POST.get('date')
            reason = (request.POST.get('reason') or '').strip()
            closure_type = request.POST.get('closure_type', BlockedDate.ClosureType.CLOSED)
            if closure_type not in BlockedDate.ClosureType.values:
                closure_type = BlockedDate.ClosureType.CLOSED
            if date_str:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                if not reason:
                    reason = (
                        'Fully booked'
                        if closure_type == BlockedDate.ClosureType.FULL
                        else 'Closed'
                    )
                BlockedDate.objects.update_or_create(
                    date=date_obj,
                    defaults={
                        'reason': reason,
                        'closure_type': closure_type,
                    },
                )
                log_action(
                    AVAILABILITY_UPDATED,
                    f'Blocked date {date_str} ({closure_type}).',
                    request=request,
                    target_type='availability',
                )
                label = 'fully booked' if closure_type == BlockedDate.ClosureType.FULL else 'closed'
                messages.success(request, f'{date_obj.strftime("%d %b %Y")} marked as {label}.')
        elif action == 'unblock_date':
            blocked = get_object_or_404(BlockedDate, pk=request.POST.get('blocked_id'))
            blocked.delete()
            log_action(AVAILABILITY_UPDATED, 'Unblocked a date.', request=request, target_type='availability')
            messages.success(request, 'Date unblocked.')
        elif action == 'close_tomorrow':
            target = today + timedelta(days=1)
            BlockedDate.objects.update_or_create(
                date=target,
                defaults={
                    'reason': request.POST.get('reason') or 'Closed',
                    'closure_type': BlockedDate.ClosureType.CLOSED,
                },
            )
            log_action(
                AVAILABILITY_UPDATED,
                f'Quick-closed tomorrow ({target}).',
                request=request,
                target_type='availability',
            )
            messages.success(request, f'{target.strftime("%d %b %Y")} marked as closed.')
        elif action == 'full_today':
            BlockedDate.objects.update_or_create(
                date=today,
                defaults={
                    'reason': request.POST.get('reason') or 'Fully booked',
                    'closure_type': BlockedDate.ClosureType.FULL,
                },
            )
            log_action(
                AVAILABILITY_UPDATED,
                f'Quick-marked today full ({today}).',
                request=request,
                target_type='availability',
            )
            messages.success(request, f'{today.strftime("%d %b %Y")} marked as fully booked.')
        return redirect('panel:availability')

    when_filter = (request.GET.get('when') or 'upcoming').lower()
    kind_filter = (request.GET.get('kind') or 'all').lower()
    blocked_qs = BlockedDate.objects.all()
    if when_filter == 'past':
        blocked_qs = blocked_qs.filter(date__lt=today)
    elif when_filter == 'all':
        pass
    else:
        when_filter = 'upcoming'
        blocked_qs = blocked_qs.filter(date__gte=today)

    if kind_filter == 'closed':
        blocked_qs = blocked_qs.filter(closure_type=BlockedDate.ClosureType.CLOSED)
    elif kind_filter == 'full':
        blocked_qs = blocked_qs.filter(closure_type=BlockedDate.ClosureType.FULL)
    else:
        kind_filter = 'all'

    if when_filter == 'past':
        blocked_qs = blocked_qs.order_by('-date')
    else:
        blocked_qs = blocked_qs.order_by('date')

    this_week_monday = today - timedelta(days=today.weekday())
    next_week_monday = this_week_monday + timedelta(days=7)

    return render(request, 'panel/availability.html', {
        'weekly_schedule': weekly_schedule,
        'time_slots': time_slots,
        'blocked_dates': blocked_qs,
        'blocked_total': BlockedDate.objects.count(),
        'when_filter': when_filter,
        'kind_filter': kind_filter,
        'today': today,
        'tomorrow': today + timedelta(days=1),
        'this_week_monday': this_week_monday,
        'next_week_monday': next_week_monday,
        'can_delete_slots': request.user.is_sysadmin,
        'active_slot_count': TimeSlot.objects.filter(active=True).count(),
    })


@admin_required
def enquiry_list_view(request):
    messages_qs = ContactMessage.objects.all()
    return render(request, 'panel/enquiries/list.html', {'enquiries': messages_qs})


@admin_required
def enquiry_detail_view(request, pk):
    enquiry = get_object_or_404(ContactMessage, pk=pk)
    if not enquiry.is_read:
        enquiry.is_read = True
        enquiry.save(update_fields=['is_read'])
        log_action(
            ENQUIRY_READ,
            f'Opened enquiry from {enquiry.name}.',
            request=request,
            target_type='enquiry',
            target_id=enquiry.pk,
            target_label=enquiry.email,
        )
    return render(request, 'panel/enquiries/detail.html', {'enquiry': enquiry})


@admin_required
@require_POST
def enquiry_mark_read_view(request, pk):
    enquiry = get_object_or_404(ContactMessage, pk=pk)
    enquiry.is_read = True
    enquiry.save()
    log_action(ENQUIRY_READ, f'Marked enquiry #{enquiry.pk} as read.', request=request, target_type='enquiry', target_id=enquiry.pk)
    messages.success(request, 'Enquiry marked as read.')
    return redirect('panel:enquiry_detail', pk=pk)


@admin_required
@require_POST
def enquiry_delete_view(request, pk):
    enquiry = get_object_or_404(ContactMessage, pk=pk)
    enquiry_id = enquiry.pk
    enquiry_email = enquiry.email
    enquiry.delete()
    log_action(
        ENQUIRY_DELETED,
        f'Deleted enquiry from {enquiry_email}.',
        request=request,
        target_type='enquiry',
        target_id=enquiry_id,
        target_label=enquiry_email,
    )
    messages.success(request, 'Enquiry deleted.')
    return redirect('panel:enquiry_list')


@admin_required
def service_list_view(request):
    services = Service.objects.all()
    status_filter = (request.GET.get('status') or 'all').lower()
    type_filter = (request.GET.get('type') or 'all').lower()
    query = (request.GET.get('q') or '').strip()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            name = request.POST.get('name', '').strip()
            description = request.POST.get('description', '').strip()
            service_type = request.POST.get('service_type', ServiceType.OVEN)
            exclusive_group = (
                'hob'
                if name.lower().startswith(('4 hob', '5 hob', '6-8 hob', '6–8 hob'))
                else ''
            )
            try:
                duration = int(request.POST.get('duration_minutes') or 60)
                sort_order = int(request.POST.get('sort_order') or 0)
                service = Service.objects.create(
                    name=name,
                    description=description,
                    price=request.POST.get('price'),
                    sort_order=sort_order,
                    service_type=service_type,
                    exclusive_group=exclusive_group,
                    duration_minutes=max(15, duration),
                )
                log_action(
                    SERVICE_CREATED,
                    f'Created service {service.name}.',
                    request=request,
                    target_type='service',
                    target_id=service.pk,
                    target_label=service.name,
                )
                messages.success(request, 'Service added.')
            except (ValueError, TypeError):
                messages.error(request, 'Could not add service. Check the values and try again.')
        elif action == 'toggle':
            service = get_object_or_404(Service, pk=request.POST.get('service_id'))
            service.active = not service.active
            service.save(update_fields=['active'])
            log_action(
                SERVICE_UPDATED,
                f'{"Activated" if service.active else "Deactivated"} service {service.name}.',
                request=request,
                target_type='service',
                target_id=service.pk,
                target_label=service.name,
            )
            messages.success(request, f'Service {service.name} updated.')
        elif action == 'update_price':
            service = get_object_or_404(Service, pk=request.POST.get('service_id'))
            try:
                service.price = request.POST.get('price')
                service.save(update_fields=['price'])
                log_action(
                    SERVICE_UPDATED,
                    f'Updated price for {service.name} to £{service.price}.',
                    request=request,
                    target_type='service',
                    target_id=service.pk,
                    target_label=service.name,
                )
                messages.success(request, f'Price updated for {service.name}.')
            except (ValueError, TypeError):
                messages.error(request, 'Please enter a valid price.')
        elif action == 'bulk_delete_inactive':
            if not request.user.is_sysadmin:
                messages.error(request, 'Only system admins can bulk-delete inactive services.')
            else:
                inactive = list(Service.objects.filter(active=False))
                deleted = 0
                skipped = 0
                for service in inactive:
                    has_bookings = (
                        Booking.objects.filter(services=service).exists()
                        or Booking.objects.filter(service=service).exists()
                    )
                    if has_bookings:
                        skipped += 1
                        continue
                    name = service.name
                    service.delete()
                    log_action(
                        SERVICE_DELETED,
                        f'Deleted inactive service {name}.',
                        request=request,
                        target_type='service',
                        target_label=name,
                    )
                    deleted += 1
                if deleted and skipped:
                    messages.success(
                        request,
                        f'Deleted {deleted} inactive service(s). Skipped {skipped} still linked to bookings.',
                    )
                elif deleted:
                    messages.success(request, f'Deleted {deleted} inactive service(s).')
                elif skipped:
                    messages.warning(
                        request,
                        f'No services deleted — {skipped} inactive service(s) are linked to bookings.',
                    )
                else:
                    messages.info(request, 'No inactive services to delete.')
        return redirect('panel:service_list')

    active_count = Service.objects.filter(active=True).count()
    inactive_count = Service.objects.filter(active=False).count()

    if status_filter == 'active':
        services = services.filter(active=True)
    elif status_filter == 'inactive':
        services = services.filter(active=False)
    else:
        status_filter = 'all'

    if type_filter in (ServiceType.OVEN, ServiceType.ADDON):
        services = services.filter(service_type=type_filter)
    else:
        type_filter = 'all'

    if query:
        services = services.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        )

    return render(request, 'panel/services/list.html', {
        'services': services,
        'status_filter': status_filter,
        'type_filter': type_filter,
        'query': query,
        'filtered_count': services.count(),
        'active_count': active_count,
        'inactive_count': inactive_count,
    })


@admin_required
def service_edit_view(request, pk):
    service = get_object_or_404(Service, pk=pk)
    if request.method == 'POST':
        service.name = request.POST.get('name', service.name)
        service.description = request.POST.get('description', service.description)
        service.sort_order = request.POST.get('sort_order', service.sort_order) or 0
        service.active = request.POST.get('is_active') == 'on'
        service_type = request.POST.get('service_type', service.service_type)
        service.service_type = service_type
        service.exclusive_group = 'hob' if service.name.lower().startswith(('4 hob', '5 hob', '6-8 hob', '6–8 hob')) else ''
        try:
            service.price = request.POST.get('price')
            service.duration_minutes = int(request.POST.get('duration_minutes', service.duration_minutes))
            service.save()
            log_action(
                SERVICE_UPDATED,
                f'Updated service {service.name}.',
                request=request,
                target_type='service',
                target_id=service.pk,
                target_label=service.name,
            )
            messages.success(request, f'Service {service.name} updated.')
            return redirect('panel:service_list')
        except (ValueError, TypeError):
            messages.error(request, 'Please enter a valid price.')
    return render(request, 'panel/services/edit.html', {
        'edit_service': service,
        'can_delete_service': request.user.is_sysadmin,
    })


@admin_required
@require_POST
def service_delete_view(request, pk):
    if not request.user.is_sysadmin:
        messages.error(request, 'Only system admins can delete services.')
        return redirect('panel:service_list')
    service = get_object_or_404(Service, pk=pk)
    has_bookings = (
        Booking.objects.filter(services=service).exists()
        or Booking.objects.filter(service=service).exists()
    )
    if has_bookings:
        messages.error(
            request,
            f'Cannot delete {service.name} — it is linked to existing bookings. Deactivate it instead.',
        )
        return redirect('panel:service_list')
    name = service.name
    service.delete()
    log_action(
        SERVICE_DELETED,
        f'Deleted service {name}.',
        request=request,
        target_type='service',
        target_label=name,
    )
    messages.success(request, f'Service {name} deleted.')
    return redirect('panel:service_list')


@sysadmin_required
def marketing_view(request):
    from django.conf import settings

    offer = HomepageOffer.get_solo()
    if request.method == 'POST' and request.POST.get('form') == 'homepage_offer':
        offer_form = HomepageOfferForm(request.POST, instance=offer)
        if offer_form.is_valid():
            offer_form.save()
            log_action(
                HOMEPAGE_OFFER_UPDATED,
                f'Updated homepage offer: {offer.headline}'
                + (' (visible)' if offer.enabled else ' (hidden)'),
                request=request,
                target_type='homepage_offer',
                target_label=offer.headline,
            )
            messages.success(request, 'Homepage offer banner updated.')
            return redirect('panel:marketing')
    else:
        offer_form = HomepageOfferForm(instance=offer)

    pixel_id = getattr(settings, 'META_PIXEL_ID', '')
    context = get_marketing_dashboard_context(days=30)
    context.update({
        'offer_form': offer_form,
        'meta_pixel_id': pixel_id,
        'meta_pixel_active': bool(pixel_id),
        'meta_events_manager_url': 'https://business.facebook.com/events_manager2',
        'meta_ads_manager_url': 'https://adsmanager.facebook.com/',
    })
    return render(request, 'panel/marketing.html', context)


@sysadmin_required
def debug_view(request):
    return render(request, 'panel/debug.html', {
        'email_tests': EMAIL_TEST_TYPES,
        'email_config': get_email_config_summary(),
        'sysadmin_recipients': get_sysadmin_recipients(),
        'posted_recipient': request.GET.get('recipient', ''),
    })


def _flash_email_send_results(request, email_meta, results, recipients_label):
    if not results:
        messages.error(request, 'No recipients configured. Enter an email address or set SYSADMIN_EMAILS.')
        return

    sent = [email for email, ok in results if ok]
    failed = [email for email, ok in results if not ok]

    if sent and not failed:
        messages.success(
            request,
            f"Test email '{email_meta['name']}' sent to {recipients_label}.",
        )
    elif sent and failed:
        messages.warning(
            request,
            f"Partially sent '{email_meta['name']}' to {recipients_label} — "
            f"succeeded: {', '.join(sent)}; failed: {', '.join(failed)}.",
        )
    else:
        messages.error(
            request,
            f"Failed to send '{email_meta['name']}' to {recipients_label}. Check server logs.",
        )


def _flash_bulk_email_send_results(request, summaries, recipients_label):
    if not summaries:
        messages.error(request, 'No email types configured.')
        return

    succeeded = []
    partial = []
    failed = []

    for email_meta, results in summaries:
        if not results:
            failed.append(email_meta['name'])
            continue
        sent_count = sum(1 for _, ok in results if ok)
        failed_count = sum(1 for _, ok in results if not ok)
        if failed_count == 0:
            succeeded.append(email_meta['name'])
        elif sent_count == 0:
            failed.append(email_meta['name'])
        else:
            partial.append(email_meta['name'])

    total = len(summaries)
    ok_count = len(succeeded)

    if ok_count == total:
        messages.success(
            request,
            f'All {total} test emails sent to {recipients_label}.',
        )
    elif ok_count == 0 and not partial:
        messages.error(
            request,
            f'Failed to send test emails to {recipients_label}. Check server logs.',
        )
    else:
        detail_parts = []
        if succeeded:
            detail_parts.append(f'sent: {", ".join(succeeded)}')
        if partial:
            detail_parts.append(f'partial: {", ".join(partial)}')
        if failed:
            detail_parts.append(f'failed: {", ".join(failed)}')
        messages.warning(
            request,
            f'Sent {ok_count} of {total} test email types to {recipients_label} ({"; ".join(detail_parts)}).',
        )


def _debug_redirect_after_send(request):
    from urllib.parse import urlencode
    from django.urls import reverse

    recipient = request.POST.get('recipient', '').strip()
    if recipient:
        return redirect(f'{reverse("panel:debug")}?{urlencode({"recipient": recipient})}')
    return redirect('panel:debug')


@sysadmin_required
@require_POST
def debug_send_email_view(request, email_type):
    try:
        recipients = parse_debug_recipients(request.POST.get('recipient', ''))
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect('panel:debug')

    email_meta, results = send_test_email(email_type, recipients=recipients)
    if email_meta is None:
        messages.error(request, 'Unknown email type.')
        return redirect('panel:debug')

    _flash_email_send_results(request, email_meta, results, ', '.join(recipients))
    return _debug_redirect_after_send(request)


@sysadmin_required
@require_POST
def debug_send_all_emails_view(request):
    try:
        recipients = parse_debug_recipients(request.POST.get('recipient', ''))
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect('panel:debug')

    summaries = send_all_test_emails(recipients=recipients)
    _flash_bulk_email_send_results(request, summaries, ', '.join(recipients))
    return _debug_redirect_after_send(request)

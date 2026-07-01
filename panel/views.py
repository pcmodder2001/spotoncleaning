from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from bookings.forms import AdminBookingForm, BookingForm
from bookings.models import (
    BlockedDate,
    Booking,
    BookingPhoto,
    BookingStatus,
    TimeSlot,
    WeeklySchedule,
)
from bookings.checklist import checklist_from_post, merge_checklist
from bookings.utils import cancel_booking
from bookings.notifications import send_booking_status_email
from accounts.roles import UserRole
from audit.actions import (
    AVAILABILITY_UPDATED,
    BOOKING_CANCELLED,
    BOOKING_UPDATED,
    ENQUIRY_DELETED,
    ENQUIRY_READ,
    SERVICE_CREATED,
    SERVICE_DELETED,
    SERVICE_UPDATED,
    USER_DELETED,
    USER_UPDATED,
)
from audit.services import log_action
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
from website.models import ContactMessage

User = get_user_model()


@panel_required
def dashboard_view(request):
    today = timezone.localdate()
    stats = {
        'total_users': User.objects.count(),
        'total_bookings': Booking.objects.count(),
        'today_bookings': Booking.objects.filter(date=today).exclude(status=BookingStatus.CANCELLED).count(),
        'pending_bookings': Booking.objects.filter(status=BookingStatus.PENDING).count(),
        'confirmed_bookings': Booking.objects.filter(status=BookingStatus.CONFIRMED).count(),
        'completed_jobs': Booking.objects.filter(status=BookingStatus.COMPLETED).count(),
    }
    recent_bookings = Booking.objects.select_related('user', 'service').order_by('-created_at')[:10]
    recent_users = User.objects.order_by('-date_joined')[:10]
    unread_messages = ContactMessage.objects.filter(is_read=False).count()
    return render(request, 'panel/dashboard.html', {
        'stats': stats,
        'recent_bookings': recent_bookings,
        'recent_users': recent_users,
        'unread_messages': unread_messages,
    })


@admin_required
def user_list_view(request):
    query = request.GET.get('q', '')
    users = User.objects.all()
    if query:
        users = users.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
            | Q(phone_number__icontains=query)
        )
    return render(request, 'panel/users/list.html', {'users': users, 'query': query})


@admin_required
def user_edit_view(request, pk):
    user = get_object_or_404(User, pk=pk)
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
    })


@admin_required
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
    bookings = Booking.objects.select_related('user', 'service', 'time_slot')
    if query:
        bookings = bookings.filter(
            Q(user__email__icontains=query)
            | Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(postcode__icontains=query)
            | Q(city__icontains=query)
        )
    if status:
        bookings = bookings.filter(status=status)
    if date_filter:
        bookings = bookings.filter(date=date_filter)
    return render(request, 'panel/bookings/list.html', {
        'bookings': bookings,
        'query': query,
        'status_filter': status,
        'date_filter': date_filter,
        'status_choices': BookingStatus.choices,
        'can_manage_site': request.user.can_manage_site,
    })


@admin_required
def booking_edit_view(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
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
    return redirect('panel:booking_list')


@admin_required
def availability_view(request):
    weekly_schedule = WeeklySchedule.objects.all()
    time_slots = TimeSlot.objects.all()
    blocked_dates = BlockedDate.objects.all()
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'weekly':
            for schedule in weekly_schedule:
                schedule.is_available = request.POST.get(f'day_{schedule.day_of_week}') == 'on'
                schedule.save()
            log_action(AVAILABILITY_UPDATED, 'Updated weekly schedule.', request=request, target_type='availability')
            messages.success(request, 'Weekly schedule updated.')
        elif action == 'add_slot':
            time_str = request.POST.get('time')
            if time_str:
                from datetime import datetime
                time_obj = datetime.strptime(time_str, '%H:%M').time()
                TimeSlot.objects.get_or_create(time=time_obj)
                log_action(AVAILABILITY_UPDATED, f'Added time slot {time_str}.', request=request, target_type='availability')
                messages.success(request, f'Time slot {time_str} added.')
        elif action == 'toggle_slot':
            slot = get_object_or_404(TimeSlot, pk=request.POST.get('slot_id'))
            slot.active = not slot.active
            slot.save()
            log_action(AVAILABILITY_UPDATED, f'Toggled time slot {slot}.', request=request, target_type='availability')
            messages.success(request, f'Time slot {slot} updated.')
        elif action == 'delete_slot':
            slot = get_object_or_404(TimeSlot, pk=request.POST.get('slot_id'))
            slot.delete()
            log_action(AVAILABILITY_UPDATED, 'Deleted a time slot.', request=request, target_type='availability')
            messages.success(request, 'Time slot deleted.')
        elif action == 'block_date':
            date_str = request.POST.get('date')
            reason = request.POST.get('reason', '')
            if date_str:
                from datetime import datetime
                date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                BlockedDate.objects.update_or_create(
                    date=date_obj,
                    defaults={
                        'reason': reason,
                        'closure_type': BlockedDate.ClosureType.CLOSED,
                    },
                )
                log_action(AVAILABILITY_UPDATED, f'Blocked date {date_str}.', request=request, target_type='availability')
                messages.success(request, f'Date {date_str} blocked.')
        elif action == 'unblock_date':
            blocked = get_object_or_404(BlockedDate, pk=request.POST.get('blocked_id'))
            blocked.delete()
            log_action(AVAILABILITY_UPDATED, 'Unblocked a date.', request=request, target_type='availability')
            messages.success(request, 'Date unblocked.')
        return redirect('panel:availability')
    return render(request, 'panel/availability.html', {
        'weekly_schedule': weekly_schedule,
        'time_slots': time_slots,
        'blocked_dates': blocked_dates,
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
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            name = request.POST.get('name', '')
            service_type = request.POST.get('service_type', ServiceType.OVEN)
            exclusive_group = 'hob' if name.lower().startswith(('4 hob', '5 hob', '6-8 hob', '6–8 hob')) else ''
            service = Service.objects.create(
                name=name,
                description=request.POST.get('description'),
                price=request.POST.get('price'),
                sort_order=request.POST.get('sort_order', 0),
                service_type=service_type,
                exclusive_group=exclusive_group,
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
        elif action == 'toggle':
            service = get_object_or_404(Service, pk=request.POST.get('service_id'))
            service.active = not service.active
            service.save()
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
                service.save()
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
        return redirect('panel:service_list')
    return render(request, 'panel/services/list.html', {'services': services})


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
    return render(request, 'panel/services/edit.html', {'edit_service': service})


@admin_required
@require_POST
def service_delete_view(request, pk):
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


@admin_required
def marketing_view(request):
    from django.conf import settings

    pixel_id = getattr(settings, 'META_PIXEL_ID', '')
    context = get_marketing_dashboard_context(days=30)
    context.update({
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

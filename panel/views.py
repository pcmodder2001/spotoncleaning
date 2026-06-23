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
    BookingStatus,
    TimeSlot,
    WeeklySchedule,
)
from bookings.utils import cancel_booking
from bookings.notifications import send_booking_status_email
from panel.decorators import staff_required
from services.models import Service, ServiceType
from website.models import ContactMessage

User = get_user_model()


@staff_required
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


@staff_required
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


@staff_required
def user_edit_view(request, pk):
    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        if not user.is_sysadmin:
            user.email = request.POST.get('email', user.email)
            user.is_active = request.POST.get('is_active') == 'on'
            user.is_staff = request.POST.get('is_staff') == 'on'
        else:
            user.is_active = True
            user.is_staff = True
        user.phone_number = request.POST.get('phone_number', user.phone_number)
        user.save()
        messages.success(request, f'User {user.email} updated successfully.')
        return redirect('panel:user_list')
    return render(request, 'panel/users/edit.html', {'edit_user': user})


@staff_required
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
    try:
        user.delete()
    except PermissionDenied:
        messages.error(request, 'The system administrator account cannot be deleted.')
        return redirect('panel:user_list')
    messages.success(request, f'User {email} deleted.')
    return redirect('panel:user_list')


@staff_required
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
    })


@staff_required
def booking_edit_view(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    old_status = booking.status
    if request.method == 'POST':
        form = AdminBookingForm(request.POST, instance=booking)
        if form.is_valid():
            booking = form.save()
            if booking.status != old_status:
                send_booking_status_email(booking)
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
    })


@staff_required
@require_POST
def booking_cancel_view(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    if cancel_booking(booking):
        messages.success(request, f'Booking #{booking.pk} cancelled.')
    else:
        messages.info(request, f'Booking #{booking.pk} is already cancelled.')
    return redirect('panel:booking_list')


@staff_required
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
            messages.success(request, 'Weekly schedule updated.')
        elif action == 'add_slot':
            time_str = request.POST.get('time')
            if time_str:
                from datetime import datetime
                time_obj = datetime.strptime(time_str, '%H:%M').time()
                TimeSlot.objects.get_or_create(time=time_obj)
                messages.success(request, f'Time slot {time_str} added.')
        elif action == 'toggle_slot':
            slot = get_object_or_404(TimeSlot, pk=request.POST.get('slot_id'))
            slot.active = not slot.active
            slot.save()
            messages.success(request, f'Time slot {slot} updated.')
        elif action == 'delete_slot':
            slot = get_object_or_404(TimeSlot, pk=request.POST.get('slot_id'))
            slot.delete()
            messages.success(request, 'Time slot deleted.')
        elif action == 'block_date':
            date_str = request.POST.get('date')
            reason = request.POST.get('reason', '')
            if date_str:
                from datetime import datetime
                date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                BlockedDate.objects.get_or_create(date=date_obj, defaults={'reason': reason})
                messages.success(request, f'Date {date_str} blocked.')
        elif action == 'unblock_date':
            blocked = get_object_or_404(BlockedDate, pk=request.POST.get('blocked_id'))
            blocked.delete()
            messages.success(request, 'Date unblocked.')
        return redirect('panel:availability')
    return render(request, 'panel/availability.html', {
        'weekly_schedule': weekly_schedule,
        'time_slots': time_slots,
        'blocked_dates': blocked_dates,
    })


@staff_required
def enquiry_list_view(request):
    messages_qs = ContactMessage.objects.all()
    return render(request, 'panel/enquiries/list.html', {'enquiries': messages_qs})


@staff_required
@require_POST
def enquiry_mark_read_view(request, pk):
    enquiry = get_object_or_404(ContactMessage, pk=pk)
    enquiry.is_read = True
    enquiry.save()
    messages.success(request, 'Enquiry marked as read.')
    return redirect('panel:enquiry_list')


@staff_required
@require_POST
def enquiry_delete_view(request, pk):
    enquiry = get_object_or_404(ContactMessage, pk=pk)
    enquiry.delete()
    messages.success(request, 'Enquiry deleted.')
    return redirect('panel:enquiry_list')


@staff_required
def service_list_view(request):
    services = Service.objects.all()
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            service_type = request.POST.get('service_type', ServiceType.OVEN)
            exclusive_group = 'oven' if service_type == ServiceType.OVEN else ''
            Service.objects.create(
                name=request.POST.get('name'),
                description=request.POST.get('description'),
                price=request.POST.get('price'),
                sort_order=request.POST.get('sort_order', 0),
                service_type=service_type,
                exclusive_group=exclusive_group,
            )
            messages.success(request, 'Service added.')
        elif action == 'toggle':
            service = get_object_or_404(Service, pk=request.POST.get('service_id'))
            service.active = not service.active
            service.save()
            messages.success(request, f'Service {service.name} updated.')
        elif action == 'update_price':
            service = get_object_or_404(Service, pk=request.POST.get('service_id'))
            try:
                service.price = request.POST.get('price')
                service.save()
                messages.success(request, f'Price updated for {service.name}.')
            except (ValueError, TypeError):
                messages.error(request, 'Please enter a valid price.')
        return redirect('panel:service_list')
    return render(request, 'panel/services/list.html', {'services': services})


@staff_required
def service_edit_view(request, pk):
    service = get_object_or_404(Service, pk=pk)
    if request.method == 'POST':
        service.name = request.POST.get('name', service.name)
        service.description = request.POST.get('description', service.description)
        service.sort_order = request.POST.get('sort_order', service.sort_order) or 0
        service.active = request.POST.get('is_active') == 'on'
        service_type = request.POST.get('service_type', service.service_type)
        service.service_type = service_type
        service.exclusive_group = 'oven' if service_type == ServiceType.OVEN else ''
        try:
            service.price = request.POST.get('price')
            service.duration_minutes = int(request.POST.get('duration_minutes', service.duration_minutes))
            service.save()
            messages.success(request, f'Service {service.name} updated.')
            return redirect('panel:service_list')
        except (ValueError, TypeError):
            messages.error(request, 'Please enter a valid price.')
    return render(request, 'panel/services/edit.html', {'edit_service': service})


@staff_required
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
    messages.success(request, f'Service {name} deleted.')
    return redirect('panel:service_list')

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST

from django.contrib.auth import get_user_model
from django.urls import reverse

import logging

from bookings.guest import attach_guest_bookings_to_user
from bookings.models import Booking, BookingStatus
from bookings.notifications import send_branded_email, send_registration_email
from bookings.tokens import booking_from_account_token
from audit.actions import (
    AUTH_ACCOUNT_FROM_BOOKING,
    AUTH_LOGIN,
    AUTH_LOGOUT,
    AUTH_PASSWORD_CHANGE,
    AUTH_PROFILE_UPDATE,
    AUTH_REGISTER,
)
from audit.services import log_action

from .forms import (
    BusinessProfileForm,
    CompleteAccountFromBookingForm,
    CustomPasswordChangeForm,
    LoginForm,
    ProfileForm,
    PropertyForm,
    RegistrationForm,
    SavedAddressForm,
    UpgradeToBusinessForm,
)
from .models import Property, SavedAddress
from accounts.account_types import AccountType
from accounts.business import ensure_business_profile, get_business_profile

User = get_user_model()
logger = logging.getLogger(__name__)


def register_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')
    next_url = request.GET.get('next')
    is_business = request.GET.get('type') == 'business'
    initial = {'account_type': AccountType.BUSINESS} if is_business else {}
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            if not send_registration_email(user):
                messages.warning(
                    request,
                    'Your account was created, but we could not send the welcome email. '
                    'You can still log in and use the site.',
                )
            else:
                if user.is_business_account:
                    messages.success(
                        request,
                        'Your property partner account is ready. Add your first property to start booking.',
                    )
                else:
                    messages.success(request, 'Your account has been created successfully. Welcome!')
            login(request, user)
            log_action(
                AUTH_REGISTER,
                f'Registered new {"property partner" if user.is_business_account else ""} account ({user.email}).',
                request=request,
                user=user,
                target_type='user',
                target_id=user.pk,
                target_label=user.email,
                metadata={'account_type': user.account_type},
            )
            post_next = request.POST.get('next') or next_url
            if user.is_business_account and not post_next:
                return redirect('accounts:properties')
            return redirect(post_next or 'accounts:dashboard')
    else:
        form = RegistrationForm(initial=initial)
    return render(request, 'accounts/register.html', {
        'form': form,
        'next_url': next_url,
        'is_business_registration': is_business,
    })


def login_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            log_action(
                AUTH_LOGIN,
                f'Logged in ({user.email}).',
                request=request,
                user=user,
                target_type='user',
                target_id=user.pk,
                target_label=user.email,
            )
            if not form.cleaned_data.get('remember_me'):
                request.session.set_expiry(0)
            messages.success(request, f'Welcome back, {user.first_name}!')
            next_url = request.GET.get('next') or request.POST.get('next')
            return redirect(next_url or 'accounts:dashboard')
    else:
        form = LoginForm()
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    if request.user.is_authenticated:
        log_action(
            AUTH_LOGOUT,
            f'Logged out ({request.user.email}).',
            request=request,
            user=request.user,
            target_type='user',
            target_id=request.user.pk,
            target_label=request.user.email,
        )
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('website:home')


def complete_account_from_booking_view(request, token=None):
    token = (token or request.GET.get('token', '')).strip()
    if not token:
        messages.error(
            request,
            'This account setup link is invalid or has expired. Please contact us if you need help.',
        )
        return redirect('accounts:login')

    booking = booking_from_account_token(token)
    if not booking:
        messages.error(
            request,
            'This account setup link is invalid or has expired. Please contact us if you need help.',
        )
        return redirect('accounts:login')

    if User.objects.filter(email__iexact=booking.guest_email).exists():
        messages.info(
            request,
            'An account already exists for this email. Log in to view your bookings.',
        )
        return redirect(f'{reverse("accounts:login")}?next={reverse("accounts:my_bookings")}')

    if request.method == 'POST':
        form = CompleteAccountFromBookingForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(
                email=booking.guest_email,
                password=form.cleaned_data['password1'],
                first_name=booking.guest_first_name,
                last_name=booking.guest_last_name,
                phone_number=booking.guest_phone,
            )
            attach_guest_bookings_to_user(user, booking.guest_email)
            if not send_registration_email(user):
                messages.warning(
                    request,
                    'Your account was created, but we could not send the welcome email. '
                    'You can still use your account.',
                )
            login(request, user)
            log_action(
                AUTH_ACCOUNT_FROM_BOOKING,
                f'Created account from booking link ({user.email}).',
                request=request,
                user=user,
                target_type='user',
                target_id=user.pk,
                target_label=user.email,
                metadata={'booking_id': booking.pk},
            )
            messages.success(
                request,
                'Your account is ready. You can now view and manage your bookings.',
            )
            return redirect('accounts:my_bookings')
    else:
        form = CompleteAccountFromBookingForm()

    return render(request, 'accounts/complete_booking_account.html', {
        'form': form,
        'booking': booking,
    })


@login_required
def dashboard_view(request):
    today = timezone.localdate()
    booking_qs = Booking.objects.filter(user=request.user).select_related(
        'time_slot', 'promo_code',
    ).prefetch_related('services')
    bookings = booking_qs
    upcoming = bookings.filter(
        date__gte=today,
    ).exclude(status=BookingStatus.CANCELLED).order_by('date', 'time_slot__time')[:5]
    completed_count = bookings.filter(status=BookingStatus.COMPLETED).count()
    context = {
        'upcoming_bookings': upcoming,
        'completed_count': completed_count,
        'total_bookings': bookings.count(),
        'pending_count': bookings.filter(status=BookingStatus.PENDING).count(),
        'business_profile': get_business_profile(request.user),
        'property_count': request.user.properties.count() if request.user.is_business_account else 0,
    }
    return render(request, 'accounts/dashboard.html', context)


@login_required
def my_bookings_view(request):
    status_filter = request.GET.get('status', '')
    bookings = (
        Booking.objects.filter(user=request.user)
        .select_related('time_slot', 'promo_code')
        .prefetch_related('services')
        .order_by('-date', '-created_at')
    )
    if status_filter:
        bookings = bookings.filter(status=status_filter)
    return render(request, 'accounts/my_bookings.html', {
        'bookings': bookings,
        'status_filter': status_filter,
        'status_choices': BookingStatus.choices,
    })


@login_required
def properties_view(request):
    if not request.user.is_business_account:
        messages.info(
            request,
            'Property management is for property partner accounts. '
            'Upgrade your account from your profile, or register a partner account.',
        )
        return redirect('accounts:profile')

    editing = None
    show_property_modal = False
    modal_action = 'add'
    form = PropertyForm()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            modal_action = 'add'
            form = PropertyForm(request.POST)
            if form.is_valid():
                prop = form.save(commit=False)
                prop.user = request.user
                prop.save()
                messages.success(request, 'Property saved.')
                return redirect('accounts:properties')
            show_property_modal = True
        elif action == 'edit':
            modal_action = 'edit'
            editing = get_object_or_404(
                Property,
                pk=request.POST.get('property_id'),
                user=request.user,
            )
            form = PropertyForm(request.POST, instance=editing)
            if form.is_valid():
                form.save()
                messages.success(request, 'Property updated.')
                return redirect('accounts:properties')
            show_property_modal = True
        elif action == 'delete':
            prop = get_object_or_404(
                Property,
                pk=request.POST.get('property_id'),
                user=request.user,
            )
            was_default = prop.is_default
            prop.delete()
            if was_default:
                next_property = Property.objects.filter(user=request.user).first()
                if next_property:
                    next_property.is_default = True
                    next_property.save(update_fields=['is_default', 'updated_at'])
            messages.success(request, 'Property removed.')
            return redirect('accounts:properties')
        elif action == 'set_default':
            prop = get_object_or_404(
                Property,
                pk=request.POST.get('property_id'),
                user=request.user,
            )
            prop.is_default = True
            prop.save(update_fields=['is_default', 'updated_at'])
            messages.success(request, f'"{prop.display_label}" is now your default property.')
            return redirect('accounts:properties')

    properties = Property.objects.filter(user=request.user)
    business_profile = get_business_profile(request.user)
    return render(request, 'accounts/properties.html', {
        'properties': properties,
        'form': form,
        'editing': editing,
        'show_property_modal': show_property_modal,
        'modal_action': modal_action,
        'business_profile': business_profile,
    })


@login_required
def saved_addresses_view(request):
    from accounts.addresses import import_addresses_from_bookings

    imported = import_addresses_from_bookings(request.user)
    if imported:
        messages.info(
            request,
            f'We imported {imported} address{"es" if imported != 1 else ""} from your past bookings.',
        )

    editing = None
    show_address_modal = False
    modal_action = 'add'
    form = SavedAddressForm()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            modal_action = 'add'
            form = SavedAddressForm(request.POST)
            if form.is_valid():
                address = form.save(commit=False)
                address.user = request.user
                address.save()
                messages.success(request, 'Address saved.')
                return redirect('accounts:addresses')
            show_address_modal = True
        elif action == 'edit':
            modal_action = 'edit'
            editing = get_object_or_404(
                SavedAddress,
                pk=request.POST.get('address_id'),
                user=request.user,
            )
            form = SavedAddressForm(request.POST, instance=editing)
            if form.is_valid():
                form.save()
                messages.success(request, 'Address updated.')
                return redirect('accounts:addresses')
            show_address_modal = True
        elif action == 'delete':
            address = get_object_or_404(
                SavedAddress,
                pk=request.POST.get('address_id'),
                user=request.user,
            )
            was_default = address.is_default
            address.delete()
            if was_default:
                next_address = SavedAddress.objects.filter(user=request.user).first()
                if next_address:
                    next_address.is_default = True
                    next_address.save(update_fields=['is_default', 'updated_at'])
            messages.success(request, 'Address removed.')
            return redirect('accounts:addresses')
        elif action == 'set_default':
            address = get_object_or_404(
                SavedAddress,
                pk=request.POST.get('address_id'),
                user=request.user,
            )
            address.is_default = True
            address.save(update_fields=['is_default', 'updated_at'])
            messages.success(request, f'"{address.display_label}" is now your default address.')
            return redirect('accounts:addresses')

    addresses = SavedAddress.objects.filter(user=request.user)
    return render(request, 'accounts/addresses.html', {
        'addresses': addresses,
        'form': form,
        'editing': editing,
        'show_address_modal': show_address_modal,
        'modal_action': modal_action,
    })


@login_required
def profile_view(request):
    business_profile = get_business_profile(request.user)
    upgrade_form = UpgradeToBusinessForm()
    business_form = BusinessProfileForm(instance=business_profile) if business_profile else None

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'profile':
            profile_form = ProfileForm(request.POST, instance=request.user)
            password_form = CustomPasswordChangeForm(request.user)
            if profile_form.is_valid():
                profile_form.save()
                log_action(
                    AUTH_PROFILE_UPDATE,
                    f'Updated profile ({request.user.email}).',
                    request=request,
                    target_type='user',
                    target_id=request.user.pk,
                    target_label=request.user.email,
                )
                messages.success(request, 'Your profile has been updated.')
                return redirect('accounts:profile')
        elif action == 'password':
            profile_form = ProfileForm(instance=request.user)
            password_form = CustomPasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                log_action(
                    AUTH_PASSWORD_CHANGE,
                    f'Changed password ({user.email}).',
                    request=request,
                    user=user,
                    target_type='user',
                    target_id=user.pk,
                    target_label=user.email,
                )
                messages.success(request, 'Your password has been changed.')
                return redirect('accounts:profile')
        elif action == 'upgrade_business' and not request.user.is_business_account:
            upgrade_form = UpgradeToBusinessForm(request.POST)
            profile_form = ProfileForm(instance=request.user)
            password_form = CustomPasswordChangeForm(request.user)
            if upgrade_form.is_valid():
                ensure_business_profile(
                    request.user,
                    company_name=upgrade_form.cleaned_data['company_name'],
                    invoice_email=upgrade_form.cleaned_data['invoice_email'],
                )
                messages.success(
                    request,
                    'Your account is now a property partner account. Add your properties to book void cleans.',
                )
                return redirect('accounts:properties')
        elif action == 'business_profile' and request.user.is_business_account and business_profile:
            business_form = BusinessProfileForm(request.POST, instance=business_profile)
            profile_form = ProfileForm(instance=request.user)
            password_form = CustomPasswordChangeForm(request.user)
            if business_form.is_valid():
                business_form.save()
                messages.success(request, 'Business details updated.')
                return redirect('accounts:profile')
        else:
            profile_form = ProfileForm(instance=request.user)
            password_form = CustomPasswordChangeForm(request.user)
    else:
        profile_form = ProfileForm(instance=request.user)
        password_form = CustomPasswordChangeForm(request.user)

    return render(request, 'accounts/profile.html', {
        'profile_form': profile_form,
        'password_form': password_form,
        'business_profile': business_profile,
        'business_form': business_form,
        'upgrade_form': upgrade_form,
    })


class CustomPasswordResetView(PasswordResetView):
    template_name = 'accounts/password_reset.html'
    email_template_name = 'accounts/password_reset_email.html'
    html_email_template_name = 'emails/password_reset.html'
    subject_template_name = 'accounts/password_reset_subject.txt'
    success_url = reverse_lazy('accounts:password_reset_done')

    def send_mail(
        self,
        subject_template_name,
        email_template_name,
        context,
        from_email,
        to_email,
        html_email_template_name=None,
    ):
        subject = render_to_string(subject_template_name, context).strip()
        plain_body = render_to_string(email_template_name, context)
        html_template = html_email_template_name or self.html_email_template_name
        try:
            send_branded_email(
                subject=subject,
                recipient=to_email,
                html_template=html_template,
                context=context,
                plain_message=plain_body,
            )
        except Exception:
            logger.exception('Failed to send password reset email to %s', to_email)
            raise


class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'accounts/password_reset_done.html'


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'accounts/password_reset_confirm.html'
    success_url = reverse_lazy('accounts:password_reset_complete')


class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'accounts/password_reset_complete.html'

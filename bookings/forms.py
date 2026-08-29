from datetime import datetime, time

from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from bookings.models import Booking, BookingStatus, TimeSlot
from bookings.scheduling import get_admin_schedule_warnings, validate_booking_schedule
from bookings.utils import get_available_slots_for_date, get_time_slots_for_booking_edit
from services.models import Service, ServiceType
from website.legal import accept_terms_field

User = get_user_model()


def appointment_hour_choices():
    return [('', 'Hour')] + [(f'{hour:02d}', f'{hour:02d}') for hour in range(24)]


def appointment_minute_choices():
    return [('', 'Min'), ('00', '00'), ('15', '15'), ('30', '30'), ('45', '45')]


class BookingForm(forms.ModelForm):
    promo_code = forms.CharField(
        required=False,
        max_length=40,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Promo code (optional)',
            'autocomplete': 'off',
        }),
    )
    services = forms.ModelMultipleChoiceField(
        queryset=Service.objects.filter(active=True),
        widget=forms.MultipleHiddenInput(),
    )
    date = forms.DateField(widget=forms.HiddenInput())
    time_slot = forms.ModelChoiceField(
        queryset=TimeSlot.objects.none(),
        widget=forms.HiddenInput(),
    )

    class Meta:
        model = Booking
        fields = [
            'date', 'time_slot',
            'address_line_1', 'address_line_2', 'city', 'postcode', 'notes',
        ]
        widgets = {
            'address_line_1': forms.TextInput(attrs={'class': 'form-control'}),
            'address_line_2': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'postcode': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        selected_date = None
        if self.data.get('date'):
            try:
                selected_date = datetime.strptime(self.data['date'], '%Y-%m-%d').date()
            except ValueError:
                pass
        elif self.initial.get('date'):
            val = self.initial['date']
            if isinstance(val, str):
                try:
                    selected_date = datetime.strptime(val, '%Y-%m-%d').date()
                except ValueError:
                    pass
            else:
                selected_date = val
        if selected_date:
            service_ids = self._selected_service_ids()
            postcode = self.data.get('postcode', '')
            city = self.data.get('city', '')
            self.fields['time_slot'].queryset = get_available_slots_for_date(
                selected_date,
                service_ids=service_ids,
                postcode=postcode,
                city=city,
            )

    def _selected_service_ids(self):
        if not self.data:
            return []
        if hasattr(self.data, 'getlist'):
            raw = self.data.getlist('services')
        else:
            raw = self.data.get('services', [])
            if raw is None:
                raw = []
            elif not isinstance(raw, (list, tuple)):
                raw = [raw]
        return [int(pk) for pk in raw if str(pk).isdigit()]

    def clean_services(self):
        services = self.cleaned_data.get('services')
        if not services:
            raise forms.ValidationError('Please select at least one service.')

        hob_services = [s for s in services if s.exclusive_group == 'hob']
        if len(hob_services) > 1:
            raise forms.ValidationError('Please select only one hob size.')

        return services

    def clean_date(self):
        date = self.cleaned_data['date']
        if date < timezone.localdate():
            raise forms.ValidationError('Please select a future date.')
        return date

    def clean_postcode(self):
        postcode = self.cleaned_data['postcode']
        from bookings.routing import is_valid_uk_postcode, normalize_postcode
        from bookings.service_area import postcode_service_area_error

        normalized = normalize_postcode(postcode)
        if not is_valid_uk_postcode(normalized):
            raise forms.ValidationError('Please enter a valid UK postcode.')
        area_error = postcode_service_area_error(normalized)
        if area_error:
            raise forms.ValidationError(area_error)
        return normalized

    def clean(self):
        cleaned_data = super().clean()
        date = cleaned_data.get('date')
        time_slot = cleaned_data.get('time_slot')
        postcode = cleaned_data.get('postcode')
        city = cleaned_data.get('city', '')
        services = cleaned_data.get('services')
        promo_code = cleaned_data.get('promo_code', '')
        if date and time_slot and postcode and services:
            service_ids = [s.pk for s in services]
            ok, message = validate_booking_schedule(
                date,
                time_slot.time,
                service_ids,
                postcode,
                city=city,
            )
            if not ok:
                raise forms.ValidationError(message)

        if promo_code and services:
            from bookings.promo import PromoError, resolve_promos_for_services
            try:
                pricing = resolve_promos_for_services(services, manual_code=promo_code)
                if not pricing['has_promo']:
                    raise PromoError('This promo code could not be applied to your booking.')
                self._apply_promo_pricing(cleaned_data, pricing)
            except PromoError:
                # Invalid typed code — keep any automatic offers instead of blocking.
                pricing = resolve_promos_for_services(services)
                if pricing['has_promo']:
                    self._apply_promo_pricing(cleaned_data, pricing)
                    cleaned_data['promo_code'] = ''
                else:
                    cleaned_data['promo_code'] = ''
        elif services:
            from bookings.promo import resolve_promos_for_services
            pricing = resolve_promos_for_services(services)
            if pricing['has_promo']:
                self._apply_promo_pricing(cleaned_data, pricing)
        return cleaned_data

    def _apply_promo_pricing(self, cleaned_data, pricing):
        from bookings.models import PromoCode

        codes = [row['code'] for row in pricing['promos']]
        by_code = {p.code: p for p in PromoCode.objects.filter(code__in=codes)}
        promos = [by_code[c] for c in codes if c in by_code]
        cleaned_data['_promo'] = promos[0] if promos else None
        cleaned_data['_promos'] = promos
        cleaned_data['_discount'] = pricing['discount']
        cleaned_data['_applied_promos'] = [
            {
                'id': by_code[row['code']].pk,
                'code': row['code'],
                'description': row.get('description', ''),
                'discount': row['discount'],
                'auto': bool(row.get('auto')),
                'stackable': bool(row.get('stackable')),
            }
            for row in pricing['promos']
            if row['code'] in by_code
        ]

    def save(self, commit=True):
        booking = super().save(commit=False)
        promo = self.cleaned_data.get('_promo')
        promos = self.cleaned_data.get('_promos') or ([promo] if promo else [])
        discount = self.cleaned_data.get('_discount')
        applied = self.cleaned_data.get('_applied_promos')
        if discount:
            booking.discount_amount = discount
        if applied is not None:
            booking.applied_promos = applied
        if promos:
            primary = next((p for p in promos if not p.auto_apply), None) or promos[0]
            booking.promo_code = primary
        elif promo:
            booking.promo_code = promo
            booking.discount_amount = discount
        if commit:
            booking.save()
            service_ids = [s.pk for s in self.cleaned_data['services']]
            booking.services.set(self.cleaned_data['services'])
            booking.sync_pricing_snapshot(self.cleaned_data['services'], save=True)
            booking.geocode_and_set_duration(service_ids)
        return booking


class GuestBookingForm(BookingForm):
    guest_first_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    guest_last_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    guest_email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
    )
    guest_phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    accept_terms = accept_terms_field()

    def clean_guest_email(self):
        email = self.cleaned_data['guest_email'].lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                'An account already exists with this email. Please log in to book.'
            )
        return email

    def save(self, commit=True):
        booking = super().save(commit=False)
        booking.user = None
        booking.guest_email = self.cleaned_data['guest_email']
        booking.guest_first_name = self.cleaned_data['guest_first_name']
        booking.guest_last_name = self.cleaned_data['guest_last_name']
        booking.guest_phone = self.cleaned_data.get('guest_phone', '')
        if commit:
            booking.save()
            booking.services.set(self.cleaned_data['services'])
            service_ids = [s.pk for s in self.cleaned_data['services']]
            booking.sync_pricing_snapshot(self.cleaned_data['services'], save=True)
            booking.geocode_and_set_duration(service_ids)
        return booking


class AdminBookingForm(forms.ModelForm):
    services = forms.ModelMultipleChoiceField(
        queryset=Service.objects.none(),
        widget=forms.CheckboxSelectMultiple(),
    )

    class Meta:
        model = Booking
        fields = [
            'user', 'services', 'date', 'time_slot', 'status',
            'address_line_1', 'address_line_2', 'city', 'postcode', 'notes',
        ]
        widgets = {
            'user': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'},
                format='%Y-%m-%d',
            ),
            'time_slot': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'address_line_1': forms.TextInput(attrs={'class': 'form-control'}),
            'address_line_2': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'postcode': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.ignore_availability = kwargs.pop('ignore_availability', False)
        super().__init__(*args, **kwargs)
        self.fields['date'].input_formats = ['%Y-%m-%d']
        self.fields['user'].queryset = User.objects.order_by('first_name', 'last_name', 'email')
        self.fields['user'].required = False

        selected_ids = []
        if self.instance.pk:
            selected_ids = list(self.instance.get_services().values_list('pk', flat=True))
            self.fields['services'].initial = selected_ids

        service_qs = Service.objects.filter(active=True)
        if selected_ids:
            service_qs = Service.objects.filter(
                Q(active=True) | Q(pk__in=selected_ids)
            ).distinct()
        self.fields['services'].queryset = service_qs.order_by('sort_order', 'name')

        selected_date = self._resolve_date()
        service_ids = self._selected_service_ids() or selected_ids
        postcode = self.data.get('postcode', '') if self.data else ''
        city = self.data.get('city', '') if self.data else ''
        if not postcode and self.instance.pk:
            postcode = self.instance.postcode
            city = self.instance.city

        if 'time_slot' in self.fields:
            if selected_date and not self.ignore_availability:
                self.fields['time_slot'].queryset = get_time_slots_for_booking_edit(
                    selected_date,
                    booking_pk=self.instance.pk,
                    service_ids=service_ids,
                    postcode=postcode,
                    city=city,
                )
            elif self.instance.pk:
                self.fields['time_slot'].queryset = TimeSlot.objects.filter(
                    Q(active=True) | Q(pk=self.instance.time_slot_id)
                ).order_by('time')
            else:
                self.fields['time_slot'].queryset = TimeSlot.objects.filter(active=True).order_by('time')

    def _resolve_date(self):
        if self.data.get('date'):
            try:
                return datetime.strptime(self.data['date'], '%Y-%m-%d').date()
            except ValueError:
                pass
        if self.instance.pk and self.instance.date:
            return self.instance.date
        return None

    def _selected_service_ids(self):
        if not self.data:
            return []
        if hasattr(self.data, 'getlist'):
            raw = self.data.getlist('services')
        else:
            raw = self.data.get('services', [])
            if raw is None:
                raw = []
            elif not isinstance(raw, (list, tuple)):
                raw = [raw]
        return [int(pk) for pk in raw if str(pk).isdigit()]

    def clean_services(self):
        services = self.cleaned_data.get('services')
        if not services:
            raise forms.ValidationError('Select at least one service.')
        hob_services = [s for s in services if s.exclusive_group == 'hob']
        if len(hob_services) > 1:
            raise forms.ValidationError('Only one hob size allowed per booking.')
        return services

    def clean_postcode(self):
        postcode = self.cleaned_data.get('postcode', '')
        from bookings.routing import is_valid_uk_postcode, normalize_postcode
        from bookings.service_area import postcode_service_area_error

        normalized = normalize_postcode(postcode)
        if not is_valid_uk_postcode(normalized):
            raise forms.ValidationError('Please enter a valid UK postcode.')
        area_error = postcode_service_area_error(normalized)
        if area_error:
            raise forms.ValidationError(area_error)
        return normalized

    def clean(self):
        cleaned_data = super().clean()
        date = cleaned_data.get('date')
        time_slot = cleaned_data.get('time_slot')
        status = cleaned_data.get('status')
        postcode = cleaned_data.get('postcode')
        city = cleaned_data.get('city', '')
        services = cleaned_data.get('services')

        if (
            not self.ignore_availability
            and date
            and time_slot
            and status != BookingStatus.CANCELLED
            and postcode
            and services
        ):
            service_ids = [s.pk for s in services]
            ok, message = validate_booking_schedule(
                date,
                time_slot.time,
                service_ids,
                postcode,
                city=city,
                exclude_booking_pk=self.instance.pk,
            )
            if not ok:
                raise forms.ValidationError(message)

        if (
            status == BookingStatus.IN_PROGRESS
            and self.instance.pk
            and self.instance.status != BookingStatus.IN_PROGRESS
        ):
            raise forms.ValidationError(
                'Confirm the booking first, then use Start job in the booking view to begin work.'
            )

        if (
            status == BookingStatus.COMPLETED
            and self.instance.pk
            and self.instance.status != BookingStatus.COMPLETED
        ):
            workflow_errors = self.instance.job_workflow_errors(services=services)
            if workflow_errors:
                raise forms.ValidationError(
                    'This booking cannot be marked completed until the full job workflow is done: '
                    + '; '.join(workflow_errors)
                    + ' Use Start job and Complete job in the booking view.'
                )

        if self.instance.pk and self.instance.pricing_is_locked and services:
            current_ids = set(self.instance.get_services().values_list('pk', flat=True))
            new_ids = {s.pk for s in services}
            if current_ids != new_ids:
                raise forms.ValidationError(
                    'Cannot change services on a completed or cancelled booking.'
                )

        return cleaned_data

    def save(self, commit=True):
        booking = super().save(commit=False)
        if commit:
            booking.save()
            service_ids = [s.pk for s in self.cleaned_data['services']]
            booking.services.set(self.cleaned_data['services'])
            if not booking.pricing_is_locked:
                booking.sync_pricing_snapshot(self.cleaned_data['services'], save=True)
                booking.recalculate_pricing(save=True)
            booking.geocode_and_set_duration(service_ids)
        return booking


class AdminBookingStatusForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['status']
        widgets = {'status': forms.Select(attrs={'class': 'form-select'})}


class AdminCreateBookingForm(AdminBookingForm):
    appointment_hour = forms.ChoiceField(
        choices=appointment_hour_choices(),
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    appointment_minute = forms.ChoiceField(
        choices=appointment_minute_choices(),
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    guest_first_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    guest_last_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    guest_email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
    )
    guest_phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )

    class Meta(AdminBookingForm.Meta):
        fields = [
            'user', 'services', 'date', 'status',
            'address_line_1', 'address_line_2', 'city', 'postcode', 'notes',
        ]
        widgets = {
            key: widget
            for key, widget in AdminBookingForm.Meta.widgets.items()
            if key != 'time_slot'
        }

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('ignore_availability', True)
        super().__init__(*args, **kwargs)
        self.schedule_warnings = []
        if not self.instance.pk:
            self.fields['status'].initial = BookingStatus.PENDING

    def clean(self):
        cleaned_data = super().clean()
        user = cleaned_data.get('user')
        if not user:
            for field_name, label in (
                ('guest_first_name', 'First name'),
                ('guest_last_name', 'Last name'),
                ('guest_email', 'Email'),
            ):
                if not cleaned_data.get(field_name):
                    self.add_error(field_name, f'{label} is required when no customer account is selected.')

        hour = cleaned_data.get('appointment_hour')
        minute = cleaned_data.get('appointment_minute')
        if hour and minute:
            cleaned_data['appointment_time'] = time(int(hour), int(minute))

        date = cleaned_data.get('date')
        appointment_time = cleaned_data.get('appointment_time')
        status = cleaned_data.get('status')
        postcode = cleaned_data.get('postcode', '')
        city = cleaned_data.get('city', '')
        services = cleaned_data.get('services')

        if date and appointment_time and status != BookingStatus.CANCELLED:
            service_ids = [s.pk for s in services] if services else []
            self.schedule_warnings = get_admin_schedule_warnings(
                date,
                appointment_time,
                service_ids,
                postcode,
                city=city,
            )

        return cleaned_data

    def save(self, commit=True):
        booking = super(AdminBookingForm, self).save(commit=False)
        appointment_time = self.cleaned_data['appointment_time']
        time_slot, _ = TimeSlot.objects.get_or_create(
            time=appointment_time,
            defaults={'active': False},
        )
        booking.time_slot = time_slot
        user = self.cleaned_data.get('user')
        if user:
            booking.guest_email = ''
            booking.guest_first_name = ''
            booking.guest_last_name = ''
            booking.guest_phone = ''
        else:
            booking.guest_email = self.cleaned_data['guest_email']
            booking.guest_first_name = self.cleaned_data['guest_first_name']
            booking.guest_last_name = self.cleaned_data['guest_last_name']
            booking.guest_phone = self.cleaned_data.get('guest_phone', '')
        if commit:
            booking.save()
            service_ids = [s.pk for s in self.cleaned_data['services']]
            booking.services.set(self.cleaned_data['services'])
            if not booking.pricing_is_locked:
                booking.sync_pricing_snapshot(self.cleaned_data['services'], save=True)
                booking.recalculate_pricing(save=True)
            booking.geocode_and_set_duration(service_ids)
        return booking


class RescheduleBookingForm(forms.Form):
    date = forms.DateField(
        widget=forms.HiddenInput(attrs={'id': 'id_date'}),
        input_formats=['%Y-%m-%d'],
    )
    time_slot = forms.ModelChoiceField(
        queryset=TimeSlot.objects.none(),
        widget=forms.HiddenInput(attrs={'id': 'id_time_slot'}),
    )

    def __init__(self, *args, booking=None, **kwargs):
        self.booking = booking
        super().__init__(*args, **kwargs)
        self.fields['date'].input_formats = ['%Y-%m-%d']
        self.fields['time_slot'].queryset = TimeSlot.objects.filter(active=True)
        if booking and not self.data:
            self.fields['date'].initial = booking.date
            self.fields['time_slot'].initial = booking.time_slot_id

    def clean_date(self):
        date = self.cleaned_data['date']
        if date < timezone.localdate():
            raise forms.ValidationError('Please select a future date.')
        return date

    def clean(self):
        cleaned_data = super().clean()
        date = cleaned_data.get('date')
        time_slot = cleaned_data.get('time_slot')
        if date and time_slot and self.booking:
            service_ids = list(self.booking.get_services().values_list('pk', flat=True))
            ok, message = validate_booking_schedule(
                date,
                time_slot.time,
                service_ids,
                self.booking.postcode,
                city=self.booking.city,
                exclude_booking_pk=self.booking.pk,
            )
            if not ok:
                raise forms.ValidationError(message)
        return cleaned_data

from datetime import datetime

from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from bookings.models import Booking, BookingStatus, TimeSlot
from bookings.scheduling import validate_booking_schedule
from bookings.utils import get_available_slots_for_date, get_time_slots_for_booking_edit
from services.models import Service, ServiceType

User = get_user_model()


class BookingForm(forms.ModelForm):
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
        raw = self.data.getlist('services') if self.data else []
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
        normalized = normalize_postcode(postcode)
        if not is_valid_uk_postcode(normalized):
            raise forms.ValidationError('Please enter a valid UK postcode.')
        return normalized

    def clean(self):
        cleaned_data = super().clean()
        date = cleaned_data.get('date')
        time_slot = cleaned_data.get('time_slot')
        postcode = cleaned_data.get('postcode')
        city = cleaned_data.get('city', '')
        services = cleaned_data.get('services')
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
        return cleaned_data

    def save(self, commit=True):
        booking = super().save(commit=False)
        if commit:
            booking.save()
            service_ids = [s.pk for s in self.cleaned_data['services']]
            booking.services.set(self.cleaned_data['services'])
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
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'time_slot': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'address_line_1': forms.TextInput(attrs={'class': 'form-control'}),
            'address_line_2': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'postcode': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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

        if selected_date:
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
                return None
        if self.instance.pk and not self.data:
            return self.instance.date
        return None

    def _selected_service_ids(self):
        raw = self.data.getlist('services') if self.data else []
        return [int(pk) for pk in raw if str(pk).isdigit()]

    def clean_services(self):
        services = self.cleaned_data.get('services')
        if not services:
            raise forms.ValidationError('Select at least one service.')
        hob_services = [s for s in services if s.exclusive_group == 'hob']
        if len(hob_services) > 1:
            raise forms.ValidationError('Only one hob size allowed per booking.')
        return services

    def clean(self):
        cleaned_data = super().clean()
        date = cleaned_data.get('date')
        time_slot = cleaned_data.get('time_slot')
        status = cleaned_data.get('status')
        postcode = cleaned_data.get('postcode')
        city = cleaned_data.get('city', '')
        services = cleaned_data.get('services')

        if date and time_slot and status != BookingStatus.CANCELLED and postcode and services:
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

        return cleaned_data

    def save(self, commit=True):
        booking = super().save(commit=False)
        if commit:
            booking.save()
            service_ids = [s.pk for s in self.cleaned_data['services']]
            booking.services.set(self.cleaned_data['services'])
            booking.geocode_and_set_duration(service_ids)
        return booking


class AdminBookingStatusForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['status']
        widgets = {'status': forms.Select(attrs={'class': 'form-select'})}

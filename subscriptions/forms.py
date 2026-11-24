from django import forms

from bookings.routing import is_valid_uk_postcode, normalize_postcode
from subscriptions.models import KitchenSafeSubscription, SubscriptionPayment


class KitchenSafeSignupForm(forms.ModelForm):
    photo_email_1 = forms.EmailField(
        label='Photo report email 1',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'family@example.com',
            'autocomplete': 'email',
        }),
        help_text='Required — who should receive the same-day kitchen safety report.',
    )
    photo_email_2 = forms.EmailField(
        label='Photo report email 2',
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Optional',
            'autocomplete': 'email',
        }),
    )
    photo_email_3 = forms.EmailField(
        label='Photo report email 3',
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Optional',
            'autocomplete': 'email',
        }),
    )

    class Meta:
        model = KitchenSafeSubscription
        fields = [
            'contact_name',
            'contact_phone',
            'contact_email',
            'address_line_1',
            'address_line_2',
            'city',
            'postcode',
            'photo_email_1',
            'photo_email_2',
            'photo_email_3',
            'customer_notes',
        ]
        widgets = {
            'contact_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Name of the person we visit',
                'autocomplete': 'name',
            }),
            'contact_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Phone at the property',
                'autocomplete': 'tel',
            }),
            'contact_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional email at the property',
                'autocomplete': 'email',
            }),
            'address_line_1': forms.TextInput(attrs={
                'class': 'form-control',
                'autocomplete': 'address-line1',
            }),
            'address_line_2': forms.TextInput(attrs={
                'class': 'form-control',
                'autocomplete': 'address-line2',
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-control',
                'autocomplete': 'address-level2',
            }),
            'postcode': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. LS1 1AA',
                'autocomplete': 'postal-code',
            }),
            'customer_notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Access notes, preferred days, anything we should know',
            }),
        }
        labels = {
            'contact_name': 'Person we visit',
            'contact_phone': 'Phone number',
            'contact_email': 'Email at the property (optional)',
            'customer_notes': 'Notes for us (optional)',
        }

    def clean_postcode(self):
        postcode = normalize_postcode(self.cleaned_data['postcode'])
        if not is_valid_uk_postcode(postcode):
            raise forms.ValidationError('Please enter a valid UK postcode.')
        return postcode

    def clean_photo_email_1(self):
        return (self.cleaned_data.get('photo_email_1') or '').strip().lower()

    def clean_photo_email_2(self):
        return (self.cleaned_data.get('photo_email_2') or '').strip().lower()

    def clean_photo_email_3(self):
        return (self.cleaned_data.get('photo_email_3') or '').strip().lower()

    def clean(self):
        cleaned = super().clean()
        emails = []
        for key in ('photo_email_1', 'photo_email_2', 'photo_email_3'):
            email = cleaned.get(key) or ''
            if email and email not in emails:
                emails.append(email)
        if not emails:
            self.add_error('photo_email_1', 'Enter at least one email for photo reports.')
        return cleaned

    def save(self, commit=True, user=None):
        subscription = super().save(commit=False)
        if user is not None:
            subscription.user = user
        subscription.monthly_price = KitchenSafeSubscription.DEFAULT_MONTHLY_PRICE
        subscription.status = KitchenSafeSubscription.Status.PENDING
        if commit:
            subscription.save()
        return subscription


class KitchenSafeManageForm(KitchenSafeSignupForm):
    """Customer edits to an existing KITCHENSafe subscription."""

    def save(self, commit=True, user=None):
        # Do not reset status / price / user — only update customer-facing fields.
        subscription = forms.ModelForm.save(self, commit=False)
        if commit:
            subscription.save()
        return subscription


class SubscriptionPaymentForm(forms.ModelForm):

    class Meta:
        model = SubscriptionPayment
        fields = ['amount', 'payment_date', 'method', 'notes']
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
            }),
            'payment_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'method': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional reference',
            }),
        }

    def __init__(self, *args, **kwargs):
        default_amount = kwargs.pop('default_amount', None)
        super().__init__(*args, **kwargs)
        if default_amount is not None and not self.is_bound and not self.initial.get('amount'):
            self.fields['amount'].initial = default_amount


class SubscriptionStatusForm(forms.ModelForm):
    class Meta:
        model = KitchenSafeSubscription
        fields = ['status', 'notes']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

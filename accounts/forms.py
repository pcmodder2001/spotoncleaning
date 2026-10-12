from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, SetPasswordForm, UserCreationForm
from django.contrib.auth import get_user_model

from accounts.account_types import AccountType
from accounts.models import BusinessProfile, Property, SavedAddress
from accounts.roles import UserRole
from website.legal import accept_terms_field

User = get_user_model()


class RegistrationForm(UserCreationForm):
    account_type = forms.ChoiceField(
        choices=AccountType.choices,
        initial=AccountType.PERSONAL,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        label='Account type',
    )
    company_name = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. Oak Lettings Ltd',
        }),
    )
    invoice_email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'accounts@yourcompany.com',
        }),
        label='Invoice email',
    )
    first_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}))
    phone_number = forms.CharField(max_length=20, widget=forms.TextInput(attrs={'class': 'form-control'}))
    password1 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    password2 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    accept_terms = accept_terms_field()

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'phone_number']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'username' in self.fields:
            del self.fields['username']

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('account_type') == AccountType.BUSINESS:
            if not cleaned_data.get('company_name', '').strip():
                self.add_error('company_name', 'Company name is required for property partner accounts.')
            invoice_email = cleaned_data.get('invoice_email', '').strip()
            if not invoice_email:
                cleaned_data['invoice_email'] = cleaned_data.get('email', '').lower()
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.account_type = self.cleaned_data.get('account_type', AccountType.PERSONAL)
        if commit:
            user.save()
            if user.account_type == AccountType.BUSINESS:
                BusinessProfile.objects.create(
                    user=user,
                    company_name=self.cleaned_data['company_name'].strip(),
                    invoice_email=self.cleaned_data['invoice_email'].lower().strip(),
                )
        return user


class EmployeeInviteRegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control', 'readonly': 'readonly'}))
    phone_number = forms.CharField(max_length=20, widget=forms.TextInput(attrs={'class': 'form-control'}))
    password1 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    password2 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    accept_terms = accept_terms_field()

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'phone_number']

    def __init__(self, *args, invite=None, **kwargs):
        self.invite = invite
        super().__init__(*args, **kwargs)
        if 'username' in self.fields:
            del self.fields['username']
        if invite:
            self.fields['email'].initial = invite.email
            if invite.first_name:
                self.fields['first_name'].initial = invite.first_name
            if invite.last_name:
                self.fields['last_name'].initial = invite.last_name

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if self.invite and email != self.invite.email.lower():
            raise forms.ValidationError('This invitation is for a different email address.')
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists. Try logging in instead.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = UserRole.ENGINEER
        user.is_staff = True
        user.phone_number = self.cleaned_data.get('phone_number', '')
        if commit:
            user.save()
            from hr.invites import accept_invite
            from hr.services import create_default_onboarding, ensure_employee_profile

            profile = ensure_employee_profile(user)
            if profile and self.invite:
                profile.job_title = self.invite.job_title
                profile.employment_type = self.invite.employment_type
                profile.start_date = self.invite.start_date
                profile.hourly_rate = self.invite.hourly_rate
                profile.save()
                if not profile.onboarding_tasks.exists():
                    create_default_onboarding(profile)
                accept_invite(self.invite, user)
        return user


class LoginForm(AuthenticationForm):
    username = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'you@example.com',
            'autocomplete': 'email',
        }),
    )
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your password',
            'autocomplete': 'current-password',
        }),
    )
    remember_me = forms.BooleanField(
        required=False,
        initial=True,
        label='Remember me',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone_number']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email


class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})


class CustomSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['new_password1'].label = 'New password'
        self.fields['new_password2'].label = 'Confirm new password'
        self.fields['new_password1'].widget = forms.PasswordInput(attrs={
            'class': 'form-control',
            'autocomplete': 'new-password',
            'placeholder': 'Enter a new password',
        })
        self.fields['new_password2'].widget = forms.PasswordInput(attrs={
            'class': 'form-control',
            'autocomplete': 'new-password',
            'placeholder': 'Re-enter your new password',
        })
        self.fields['new_password1'].help_text = (
            'Use at least 8 characters. Avoid passwords that are too common or entirely numeric.'
        )
        self.fields['new_password2'].help_text = ''


class CompleteAccountFromBookingForm(forms.Form):
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'autocomplete': 'new-password',
        }),
    )
    password2 = forms.CharField(
        label='Confirm password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'autocomplete': 'new-password',
        }),
    )
    accept_terms = accept_terms_field()

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('Passwords do not match.')
        if password1:
            from django.contrib.auth.password_validation import validate_password
            validate_password(password1)
        return cleaned_data


class SavedAddressForm(forms.ModelForm):
    class Meta:
        model = SavedAddress
        fields = [
            'label', 'address_line_1', 'address_line_2', 'city', 'postcode', 'is_default',
        ]
        widgets = {
            'label': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Home, Work',
            }),
            'address_line_1': forms.TextInput(attrs={'class': 'form-control'}),
            'address_line_2': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'postcode': forms.TextInput(attrs={'class': 'form-control'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

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


class BusinessProfileForm(forms.ModelForm):
    class Meta:
        model = BusinessProfile
        fields = ['company_name', 'invoice_email']
        widgets = {
            'company_name': forms.TextInput(attrs={'class': 'form-control'}),
            'invoice_email': forms.EmailInput(attrs={'class': 'form-control'}),
        }


class UpgradeToBusinessForm(forms.Form):
    company_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    invoice_email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
        label='Invoice email',
    )


class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = [
            'reference',
            'address_line_1',
            'address_line_2',
            'city',
            'postcode',
            'access_instructions',
            'contact_name',
            'contact_phone',
            'is_default',
        ]
        widgets = {
            'reference': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Flat 4, Oak House',
            }),
            'address_line_1': forms.TextInput(attrs={'class': 'form-control'}),
            'address_line_2': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'postcode': forms.TextInput(attrs={'class': 'form-control'}),
            'access_instructions': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'contact_name': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

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

"""Shared legal acceptance field for forms."""

from django import forms

ACCEPT_TERMS_ERROR = (
    'You must accept the Terms & Conditions and Privacy Policy to continue.'
)


def accept_terms_field():
    return forms.BooleanField(
        required=True,
        label='',
        error_messages={'required': ACCEPT_TERMS_ERROR},
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

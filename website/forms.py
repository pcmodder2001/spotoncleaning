from django import forms

from website.models import ContactMessage, HomepageOffer


class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'phone', 'message']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Your email'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your phone number'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'How can we help?'}),
        }


class HomepageOfferForm(forms.ModelForm):
    class Meta:
        model = HomepageOffer
        fields = ['enabled', 'headline', 'message', 'message_mobile', 'cta_label']
        labels = {
            'enabled': 'Show offer on homepage',
            'headline': 'Headline (bold)',
            'message': 'Message (desktop / tablet)',
            'message_mobile': 'Message (mobile)',
            'cta_label': 'Button label',
        }
        widgets = {
            'enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'headline': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '10% off',
            }),
            'message': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '2+ appliances, add-ons included — applied automatically',
            }),
            'message_mobile': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '2+ cleans · add-ons included',
            }),
            'cta_label': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Book',
            }),
        }

from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse

from services.models import Service, ServiceType
from website.forms import ContactForm
from website.models import Testimonial


def home_view(request):
    services = Service.objects.filter(active=True)
    oven_services = services.filter(service_type=ServiceType.OVEN)
    addon_services = services.filter(service_type=ServiceType.ADDON)
    testimonials = Testimonial.objects.filter(active=True)
    contact_form = ContactForm()
    return render(request, 'website/home.html', {
        'oven_services': oven_services,
        'addon_services': addon_services,
        'testimonials': testimonials,
        'contact_form': contact_form,
    })


def contact_submit_view(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Thank you for your message. We will get back to you soon!')
        else:
            messages.error(request, 'Please correct the errors in the contact form.')
    return redirect(reverse('website:home') + '#contact')


def privacy_policy_view(request):
    return render(request, 'website/privacy.html')


def terms_view(request):
    return render(request, 'website/terms.html')

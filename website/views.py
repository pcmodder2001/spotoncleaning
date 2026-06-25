from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse

from services.catalog import split_addon_services
from services.models import Service, ServiceType
from website.forms import ContactForm
from website.models import Testimonial


def home_view(request):
    services = Service.objects.filter(active=True)
    oven_services = services.filter(service_type=ServiceType.OVEN)
    addon_services = services.filter(service_type=ServiceType.ADDON)
    standard_addon_services, additional_addon_services = split_addon_services(addon_services)
    testimonials = Testimonial.objects.filter(active=True)
    contact_form = ContactForm()
    return render(request, 'website/home.html', {
        'oven_services': oven_services,
        'standard_addon_services': standard_addon_services,
        'additional_addon_services': additional_addon_services,
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


def zoho_domain_verification_view(request):
    verification_path = settings.BASE_DIR / 'verification' / 'zoho-domain-verification.html'
    content = verification_path.read_text(encoding='utf-8').strip()
    return HttpResponse(content, content_type='text/html')


def robots_txt_view(request):
    content = render_to_string('website/robots.txt', {'SITE_URL': settings.SITE_URL}, request=request)
    return HttpResponse(content, content_type='text/plain')


def sitemap_xml_view(request):
    content = render_to_string('website/sitemap.xml', {'SITE_URL': settings.SITE_URL}, request=request)
    return HttpResponse(content, content_type='application/xml')

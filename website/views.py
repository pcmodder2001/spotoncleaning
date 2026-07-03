from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse

from services.catalog import split_addon_services
from services.models import Service, ServiceType
from website.content import FAQ_ITEMS, HOW_WE_CLEAN_STEPS, PARTNER_BENEFITS
from website.forms import ContactForm
from website.models import Testimonial
from website.areas import (
    area_meta_description,
    area_page_title,
    get_public_coverage_area,
    get_public_coverage_areas,
    group_areas_by_region,
)
from website.tracking import apply_marketing_attribution, queue_meta_pixel_event
from bookings.notifications import send_enquiry_received_email
from audit.actions import ENQUIRY_CREATED
from audit.services import log_action


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
        'how_we_clean_steps': HOW_WE_CLEAN_STEPS,
    })


def faq_view(request):
    return render(request, 'website/faq.html', {
        'faq_items': FAQ_ITEMS,
    })


def property_partners_view(request):
    return render(request, 'website/property_partners.html', {
        'partner_benefits': PARTNER_BENEFITS,
        'how_we_clean_steps': HOW_WE_CLEAN_STEPS[:3],
    })


def areas_view(request):
    areas = get_public_coverage_areas()
    return render(request, 'website/areas.html', {
        'area_groups': sorted(group_areas_by_region(areas).items(), key=lambda item: item[0]),
        'area_count': len(areas),
    })


def area_detail_view(request, slug):
    area = get_public_coverage_area(slug)
    return render(request, 'website/area_detail.html', {
        'area': area,
        'page_title': area_page_title(area),
        'meta_description': area_meta_description(area, settings.SITE_NAME, settings.SITE_LOCAL_AREA),
        'other_areas': [a for a in get_public_coverage_areas() if a.pk != area.pk][:8],
    })


def contact_submit_view(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            enquiry = form.save()
            apply_marketing_attribution(enquiry, request)
            log_action(
                ENQUIRY_CREATED,
                f'Contact enquiry submitted by {enquiry.name}.',
                request=request,
                user=request.user if request.user.is_authenticated else None,
                actor_email=enquiry.email,
                actor_name=enquiry.name,
                target_type='enquiry',
                target_id=enquiry.pk,
                target_label=enquiry.email,
            )
            queue_meta_pixel_event(
                request,
                'Lead',
                content_name='Contact form',
            )
            send_enquiry_received_email(enquiry)
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
    areas = get_public_coverage_areas()
    content = render_to_string('website/sitemap.xml', {
        'SITE_URL': settings.SITE_URL,
        'coverage_areas': areas,
    }, request=request)
    return HttpResponse(content, content_type='application/xml')

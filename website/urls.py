from django.conf import settings
from django.urls import path

from . import errors, views

app_name = 'website'

urlpatterns = [
    path('', views.home_view, name='home'),
    path('contact/', views.contact_submit_view, name='contact'),
    path('faq/', views.faq_view, name='faq'),
    path('property-partners/', views.property_partners_view, name='property_partners'),
    path('areas/', views.areas_view, name='areas'),
    path('areas/<slug:slug>/', views.area_detail_view, name='area_detail'),
    path('privacy/', views.privacy_policy_view, name='privacy'),
    path('terms/', views.terms_view, name='terms'),
    path(
        'zoho-domain-verification.html',
        views.zoho_domain_verification_view,
        name='zoho_domain_verification',
    ),
    path('robots.txt', views.robots_txt_view, name='robots_txt'),
    path('sitemap.xml', views.sitemap_xml_view, name='sitemap_xml'),
]

if settings.DEBUG:
    urlpatterns += [
        path('__preview__/400/', errors.preview_bad_request, name='preview_400'),
        path('__preview__/403/', errors.preview_permission_denied, name='preview_403'),
        path('__preview__/404/', errors.preview_not_found, name='preview_404'),
        path('__preview__/500/', errors.preview_server_error, name='preview_500'),
    ]

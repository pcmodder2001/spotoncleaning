from django.urls import path

from . import views

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

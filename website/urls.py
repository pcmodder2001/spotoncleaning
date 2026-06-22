from django.urls import path

from . import views

app_name = 'website'

urlpatterns = [
    path('', views.home_view, name='home'),
    path('contact/', views.contact_submit_view, name='contact'),
    path('privacy/', views.privacy_policy_view, name='privacy'),
    path('terms/', views.terms_view, name='terms'),
]

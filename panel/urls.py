from django.urls import path

from . import views

app_name = 'panel'

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('users/', views.user_list_view, name='user_list'),
    path('users/<int:pk>/edit/', views.user_edit_view, name='user_edit'),
    path('users/<int:pk>/delete/', views.user_delete_view, name='user_delete'),
    path('bookings/', views.booking_list_view, name='booking_list'),
    path('bookings/<int:pk>/edit/', views.booking_edit_view, name='booking_edit'),
    path('bookings/<int:pk>/cancel/', views.booking_cancel_view, name='booking_cancel'),
    path('availability/', views.availability_view, name='availability'),
    path('enquiries/', views.enquiry_list_view, name='enquiry_list'),
    path('enquiries/<int:pk>/', views.enquiry_detail_view, name='enquiry_detail'),
    path('enquiries/<int:pk>/read/', views.enquiry_mark_read_view, name='enquiry_read'),
    path('enquiries/<int:pk>/delete/', views.enquiry_delete_view, name='enquiry_delete'),
    path('services/', views.service_list_view, name='service_list'),
    path('services/<int:pk>/edit/', views.service_edit_view, name='service_edit'),
    path('services/<int:pk>/delete/', views.service_delete_view, name='service_delete'),
    path('debug/', views.debug_view, name='debug'),
    path('debug/send/<slug:email_type>/', views.debug_send_email_view, name='debug_send_email'),
]

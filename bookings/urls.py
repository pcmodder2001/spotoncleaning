from django.urls import path

from . import views

app_name = 'bookings'

urlpatterns = [
    path('book/', views.create_booking_view, name='create'),
    path('thank-you/', views.thank_you_view, name='thank_you'),
    path('thank-you/calendar.ics', views.booking_calendar_ics_view, name='thank_you_ics'),
    path('<int:pk>/photos/<int:photo_pk>/', views.booking_photo_view, name='job_photo'),
    path('<int:pk>/job-report/', views.completion_report_view, name='completion_report'),
    path('<int:pk>/', views.booking_detail_view, name='detail'),
    path('<int:pk>/cancel/', views.cancel_booking_view, name='cancel'),
    path('<int:pk>/reschedule/', views.reschedule_booking_view, name='reschedule'),
    path('api/coverage-check/', views.coverage_check_api, name='coverage_check'),
    path('api/dates/', views.available_dates_api, name='available_dates'),
    path('api/slots/', views.available_slots_api, name='available_slots'),
    path('api/promo/', views.validate_promo_api, name='validate_promo'),
]

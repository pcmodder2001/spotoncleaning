from django.urls import path

from . import views

app_name = 'bookings'

urlpatterns = [
    path('book/', views.create_booking_view, name='create'),
    path('thank-you/', views.thank_you_view, name='thank_you'),
    path('<int:pk>/', views.booking_detail_view, name='detail'),
    path('<int:pk>/cancel/', views.cancel_booking_view, name='cancel'),
    path('api/addresses/', views.address_lookup_api, name='address_lookup'),
    path('api/dates/', views.available_dates_api, name='available_dates'),
    path('api/slots/', views.available_slots_api, name='available_slots'),
]

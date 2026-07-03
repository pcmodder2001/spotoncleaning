from django.urls import path, re_path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('complete-account/', views.complete_account_from_booking_view, name='complete_account'),
    # Legacy email links placed the raw signed token (with colons) in the path.
    re_path(
        r'^complete-account/(?P<token>[^/]+)/$',
        views.complete_account_from_booking_view,
        name='complete_account_legacy',
    ),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('bookings/', views.my_bookings_view, name='my_bookings'),
    path('profile/', views.profile_view, name='profile'),
    path('addresses/', views.saved_addresses_view, name='addresses'),
    path('properties/', views.properties_view, name='properties'),
    path('password-reset/', views.CustomPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', views.CustomPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', views.CustomPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', views.CustomPasswordResetCompleteView.as_view(), name='password_reset_complete'),
]

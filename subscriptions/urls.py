from django.urls import path

from . import views

app_name = 'subscriptions'

urlpatterns = [
    path(
        'kitchen-safe/signup/',
        views.kitchen_safe_signup_view,
        name='kitchen_safe_signup',
    ),
    path(
        'kitchen-safe/manage/',
        views.kitchen_safe_manage_view,
        name='kitchen_safe_manage',
    ),
    path(
        'kitchen-safe/thanks/',
        views.kitchen_safe_thanks_view,
        name='kitchen_safe_thanks',
    ),
]

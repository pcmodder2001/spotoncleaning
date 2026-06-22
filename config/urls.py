from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('website.urls')),
    path('accounts/', include('accounts.urls')),
    path('bookings/', include('bookings.urls')),
    path('panel/', include('panel.urls')),
]

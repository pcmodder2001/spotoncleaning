from django.contrib import admin

from .models import Service


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'service_type', 'price', 'active', 'sort_order')
    list_filter = ('service_type', 'active')
    search_fields = ('name',)

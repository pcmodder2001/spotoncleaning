from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import PermissionDenied

from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    ordering = ('email',)
    list_display = ('email', 'first_name', 'last_name', 'phone_number', 'role', 'is_staff', 'is_active')
    search_fields = ('email', 'first_name', 'last_name')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'phone_number')}),
        ('Permissions', {'fields': ('is_active', 'role', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'phone_number', 'password1', 'password2'),
        }),
    )

    def has_delete_permission(self, request, obj=None):
        if obj and obj.is_sysadmin:
            return False
        return super().has_delete_permission(request, obj)

    def delete_model(self, request, obj):
        if obj.is_sysadmin:
            self.message_user(
                request,
                'The system administrator account cannot be deleted.',
                level=messages.ERROR,
            )
            return
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        protected = [user for user in queryset if user.is_sysadmin]
        if protected:
            self.message_user(
                request,
                'System administrator account(s) were not deleted.',
                level=messages.WARNING,
            )
        for user in queryset:
            if user.is_sysadmin:
                continue
            try:
                user.delete()
            except PermissionDenied:
                pass

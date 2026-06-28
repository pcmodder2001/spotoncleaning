from django.contrib import admin

from audit.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'action_label', 'actor_display', 'actor_role', 'description', 'ip_address')
    list_filter = ('category', 'action', 'actor_role', 'created_at')
    search_fields = ('description', 'actor_email', 'actor_name', 'target_label', 'target_id')
    readonly_fields = (
        'action', 'category', 'description', 'user', 'actor_email', 'actor_name',
        'actor_role', 'target_type', 'target_id', 'target_label', 'metadata',
        'ip_address', 'created_at',
    )
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

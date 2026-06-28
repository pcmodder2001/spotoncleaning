from django.conf import settings
from django.db import models

from audit.actions import ACTION_CATEGORIES, ACTION_LABELS, CATEGORY_CHOICES


class AuditLog(models.Model):
    action = models.CharField(max_length=64, db_index=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, db_index=True)
    description = models.TextField()
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    actor_email = models.CharField(max_length=254, blank=True, db_index=True)
    actor_name = models.CharField(max_length=200, blank=True)
    actor_role = models.CharField(max_length=20, blank=True, db_index=True)
    target_type = models.CharField(max_length=64, blank=True, db_index=True)
    target_id = models.CharField(max_length=64, blank=True, db_index=True)
    target_label = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at', 'category']),
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f'{self.created_at:%Y-%m-%d %H:%M} — {self.description[:80]}'

    @property
    def action_label(self):
        return ACTION_LABELS.get(self.action, self.action.replace('.', ' ').replace('_', ' ').title())

    @property
    def actor_display(self):
        if self.actor_name:
            return self.actor_name
        if self.actor_email:
            return self.actor_email
        return 'Guest'

from django.db import models


class ServiceType(models.TextChoices):
    OVEN = 'oven', 'Oven'
    ADDON = 'addon', 'Add-on'


class Service(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=8, decimal_places=2)
    active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    service_type = models.CharField(
        max_length=10,
        choices=ServiceType.choices,
        default=ServiceType.OVEN,
    )
    duration_minutes = models.PositiveIntegerField(
        default=60,
        help_text='Estimated time on site in minutes.',
    )
    exclusive_group = models.CharField(
        max_length=50,
        blank=True,
        help_text='Services in the same group are mutually exclusive (e.g. oven).',
    )

    class Meta:
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name

    @property
    def is_oven(self):
        return self.service_type == ServiceType.OVEN

    @property
    def is_addon(self):
        return self.service_type == ServiceType.ADDON

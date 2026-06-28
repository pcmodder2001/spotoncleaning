from django.db import models


class UserRole(models.TextChoices):
    STANDARD = 'standard', 'Standard user'
    ENGINEER = 'engineer', 'Engineer'
    ADMIN = 'admin', 'Admin'

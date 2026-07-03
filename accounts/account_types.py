from django.db import models


class AccountType(models.TextChoices):
    PERSONAL = 'personal', 'Personal'
    BUSINESS = 'business', 'Business account'

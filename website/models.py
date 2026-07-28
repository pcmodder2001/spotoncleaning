from django.db import models


class HomepageOffer(models.Model):
    """Singleton settings for the homepage top-bar promo text."""

    enabled = models.BooleanField(
        default=True,
        help_text='Show the promo offer in the homepage top bar.',
    )
    headline = models.CharField(
        max_length=80,
        default='10% off',
        help_text='Bold lead-in, e.g. “10% off”.',
    )
    message = models.CharField(
        max_length=200,
        blank=True,
        default='2+ appliances, add-ons included — applied automatically',
        help_text='Full message shown on larger screens.',
    )
    message_mobile = models.CharField(
        max_length=120,
        blank=True,
        default='2+ cleans · add-ons included',
        help_text='Shorter message shown on small phones.',
    )
    cta_label = models.CharField(
        max_length=40,
        blank=True,
        default='Book',
        help_text='Button / link label next to the offer.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Homepage offer'
        verbose_name_plural = 'Homepage offer'

    def __str__(self):
        status = 'on' if self.enabled else 'off'
        return f'Homepage offer ({status}): {self.headline}'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Testimonial(models.Model):
    customer_name = models.CharField(max_length=100)
    review = models.TextField()
    rating = models.PositiveSmallIntegerField(default=5)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.customer_name} ({self.rating}/5)'


class ContactMessage(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    marketing_attribution = models.JSONField(
        default=dict,
        blank=True,
        help_text='First-touch UTM tags / fbclid when the enquiry was submitted.',
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} - {self.created_at:%d %b %Y}'

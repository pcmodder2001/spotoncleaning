from django.db import models


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

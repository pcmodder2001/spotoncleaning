from django.contrib import admin

from .models import ContactMessage, Testimonial

admin.site.register(Testimonial)
admin.site.register(ContactMessage)

from django.contrib import admin

from .models import ContactMessage, HomepageOffer, MailingListSubscriber, Testimonial


@admin.register(HomepageOffer)
class HomepageOfferAdmin(admin.ModelAdmin):
    list_display = ('headline', 'enabled', 'updated_at')

    def has_add_permission(self, request):
        return not HomepageOffer.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(Testimonial)
admin.site.register(ContactMessage)
admin.site.register(MailingListSubscriber)

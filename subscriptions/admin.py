from django.contrib import admin

from subscriptions.models import KitchenSafeSubscription, SubscriptionPayment


class SubscriptionPaymentInline(admin.TabularInline):
    model = SubscriptionPayment
    extra = 0
    readonly_fields = ('created_at', 'recorded_by')


@admin.register(KitchenSafeSubscription)
class KitchenSafeSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'contact_name',
        'postcode',
        'status',
        'monthly_price',
        'user',
        'created_at',
    )
    list_filter = ('status',)
    search_fields = (
        'contact_name',
        'contact_phone',
        'contact_email',
        'postcode',
        'photo_email_1',
        'user__email',
    )
    readonly_fields = ('created_at', 'updated_at', 'started_at')
    inlines = [SubscriptionPaymentInline]


@admin.register(SubscriptionPayment)
class SubscriptionPaymentAdmin(admin.ModelAdmin):
    list_display = ('subscription', 'amount', 'payment_date', 'method', 'created_at')
    list_filter = ('method',)
    search_fields = ('subscription__contact_name', 'notes')

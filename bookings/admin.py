from django.contrib import admin

from .models import (
    Availability,
    BlockedDate,
    Booking,
    BookingPhoto,
    CoverageArea,
    CustomerFollowUp,
    PromoCode,
    TimeSlot,
    WeeklySchedule,
)

admin.site.register(Booking)
admin.site.register(BookingPhoto)
admin.site.register(CoverageArea)
admin.site.register(CustomerFollowUp)
admin.site.register(PromoCode)
admin.site.register(Availability)
admin.site.register(TimeSlot)
admin.site.register(WeeklySchedule)
admin.site.register(BlockedDate)

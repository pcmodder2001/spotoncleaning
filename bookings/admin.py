from django.contrib import admin

from .models import Availability, BlockedDate, Booking, TimeSlot, WeeklySchedule

admin.site.register(Booking)
admin.site.register(Availability)
admin.site.register(TimeSlot)
admin.site.register(WeeklySchedule)
admin.site.register(BlockedDate)

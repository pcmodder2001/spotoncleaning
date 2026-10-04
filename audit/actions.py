"""Audit action codes grouped by category."""

# Auth
AUTH_LOGIN = 'auth.login'
AUTH_LOGOUT = 'auth.logout'
AUTH_REGISTER = 'auth.register'
AUTH_PROFILE_UPDATE = 'auth.profile_update'
AUTH_PASSWORD_CHANGE = 'auth.password_change'
AUTH_ACCOUNT_FROM_BOOKING = 'auth.account_from_booking'

# Bookings — customer & staff
BOOKING_CREATED = 'booking.created'
BOOKING_CANCELLED = 'booking.cancelled'
BOOKING_STATUS_CHANGED = 'booking.status_changed'
BOOKING_UPDATED = 'booking.updated'
BOOKING_RESCHEDULED = 'booking.rescheduled'
BOOKING_SERVICES_UPDATED = 'booking.services_updated'
BOOKING_JOB_STARTED = 'booking.job_started'
BOOKING_JOB_COMPLETED = 'booking.job_completed'
BOOKING_REMINDER_SENT = 'booking.reminder_sent'
BOOKING_BULK_CONFIRM = 'booking.bulk_confirm'
BOOKING_BULK_CANCEL = 'booking.bulk_cancel'
BOOKING_BULK_EXPORT = 'booking.bulk_export'
BOOKING_PHOTO_DELETED = 'booking.photo_deleted'
BOOKING_DELETED = 'booking.deleted'

# Users
USER_UPDATED = 'user.updated'
USER_DELETED = 'user.deleted'

# Site admin
AVAILABILITY_UPDATED = 'admin.availability_updated'
SERVICE_CREATED = 'admin.service_created'
SERVICE_UPDATED = 'admin.service_updated'
SERVICE_DELETED = 'admin.service_deleted'
PROMO_CREATED = 'admin.promo_created'
PROMO_UPDATED = 'admin.promo_updated'
PROMO_DELETED = 'admin.promo_deleted'
FOLLOWUP_CREATED = 'admin.followup_created'
FOLLOWUP_UPDATED = 'admin.followup_updated'
FOLLOWUP_DELETED = 'admin.followup_deleted'
ENQUIRY_READ = 'admin.enquiry_read'
ENQUIRY_DELETED = 'admin.enquiry_deleted'
ENQUIRY_CREATED = 'admin.enquiry_created'
COVERAGE_AREA_UPDATED = 'admin.coverage_area_updated'
COVERAGE_BOUNDARY_UPDATED = 'admin.coverage_boundary_updated'
HOMEPAGE_OFFER_UPDATED = 'admin.homepage_offer_updated'

ACTION_LABELS = {
    AUTH_LOGIN: 'Logged in',
    AUTH_LOGOUT: 'Logged out',
    AUTH_REGISTER: 'Registered account',
    AUTH_PROFILE_UPDATE: 'Updated profile',
    AUTH_PASSWORD_CHANGE: 'Changed password',
    AUTH_ACCOUNT_FROM_BOOKING: 'Created account from booking',
    BOOKING_CREATED: 'Created booking',
    BOOKING_CANCELLED: 'Cancelled booking',
    BOOKING_STATUS_CHANGED: 'Changed booking status',
    BOOKING_UPDATED: 'Updated booking',
    BOOKING_RESCHEDULED: 'Rescheduled booking',
    BOOKING_SERVICES_UPDATED: 'Updated booking services',
    BOOKING_JOB_STARTED: 'Started job',
    BOOKING_JOB_COMPLETED: 'Completed job',
    BOOKING_REMINDER_SENT: 'Sent booking reminder',
    BOOKING_BULK_CONFIRM: 'Bulk confirmed bookings',
    BOOKING_BULK_CANCEL: 'Bulk cancelled bookings',
    BOOKING_BULK_EXPORT: 'Exported bookings',
    BOOKING_PHOTO_DELETED: 'Deleted job photo',
    BOOKING_DELETED: 'Deleted booking',
    USER_UPDATED: 'Updated user',
    USER_DELETED: 'Deleted user',
    AVAILABILITY_UPDATED: 'Updated availability',
    SERVICE_CREATED: 'Created service',
    SERVICE_UPDATED: 'Updated service',
    SERVICE_DELETED: 'Deleted service',
    PROMO_CREATED: 'Created promo code',
    PROMO_UPDATED: 'Updated promo code',
    PROMO_DELETED: 'Deleted promo code',
    FOLLOWUP_CREATED: 'Created follow-up',
    FOLLOWUP_UPDATED: 'Updated follow-up',
    FOLLOWUP_DELETED: 'Deleted follow-up',
    ENQUIRY_READ: 'Marked enquiry read',
    ENQUIRY_DELETED: 'Deleted enquiry',
    ENQUIRY_CREATED: 'Submitted contact enquiry',
    COVERAGE_AREA_UPDATED: 'Updated service coverage area',
    COVERAGE_BOUNDARY_UPDATED: 'Updated editable service boundary',
    HOMEPAGE_OFFER_UPDATED: 'Updated homepage offer banner',
}

CATEGORY_CHOICES = [
    ('auth', 'Authentication'),
    ('booking', 'Bookings'),
    ('user', 'Users'),
    ('admin', 'Site admin'),
]

ACTION_CATEGORIES = {
    AUTH_LOGIN: 'auth',
    AUTH_LOGOUT: 'auth',
    AUTH_REGISTER: 'auth',
    AUTH_PROFILE_UPDATE: 'auth',
    AUTH_PASSWORD_CHANGE: 'auth',
    AUTH_ACCOUNT_FROM_BOOKING: 'auth',
    BOOKING_CREATED: 'booking',
    BOOKING_CANCELLED: 'booking',
    BOOKING_STATUS_CHANGED: 'booking',
    BOOKING_UPDATED: 'booking',
    BOOKING_RESCHEDULED: 'booking',
    BOOKING_SERVICES_UPDATED: 'booking',
    BOOKING_JOB_STARTED: 'booking',
    BOOKING_JOB_COMPLETED: 'booking',
    BOOKING_REMINDER_SENT: 'booking',
    BOOKING_BULK_CONFIRM: 'booking',
    BOOKING_BULK_CANCEL: 'booking',
    BOOKING_BULK_EXPORT: 'booking',
    BOOKING_PHOTO_DELETED: 'booking',
    BOOKING_DELETED: 'booking',
    USER_UPDATED: 'user',
    USER_DELETED: 'user',
    AVAILABILITY_UPDATED: 'admin',
    SERVICE_CREATED: 'admin',
    SERVICE_UPDATED: 'admin',
    SERVICE_DELETED: 'admin',
    PROMO_CREATED: 'admin',
    PROMO_UPDATED: 'admin',
    PROMO_DELETED: 'admin',
    FOLLOWUP_CREATED: 'admin',
    FOLLOWUP_UPDATED: 'admin',
    FOLLOWUP_DELETED: 'admin',
    ENQUIRY_READ: 'admin',
    ENQUIRY_DELETED: 'admin',
    ENQUIRY_CREATED: 'admin',
    COVERAGE_AREA_UPDATED: 'admin',
    COVERAGE_BOUNDARY_UPDATED: 'admin',
    HOMEPAGE_OFFER_UPDATED: 'admin',
}

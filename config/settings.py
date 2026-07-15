"""
Django settings for Spot On Appliance Cleaning.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

_env_file = BASE_DIR / '.env'
if _env_file.exists():
    from dotenv import load_dotenv

    load_dotenv(_env_file, override=True)

SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-s6-+f0#1+s++zze3s!t3&37pbc$oh9)0*0hpp5v7)id!%r%9%3',
)

DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() in ('true', '1', 'yes')

# TEMP: show travel-time scheduling debug on booking page (set False to hide)
SCHEDULE_DEBUG = os.environ.get('SCHEDULE_DEBUG', 'True').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get(
        'DJANGO_ALLOWED_HOSTS',
        'localhost,127.0.0.1,spoton.vehiclecare.online,192.168.0.50,spotonappliancecleaning.co.uk,www.spotonappliancecleaning.co.uk,192.168.0.93',
    ).split(',')
    if host.strip()
]

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        'DJANGO_CSRF_TRUSTED_ORIGINS',
        'https://spoton.vehiclecare.online,https://spotonappliancecleaning.co.uk,https://www.spotonappliancecleaning.co.uk,http://localhost,http://127.0.0.1,http://localhost:8999,http://127.0.0.1:8999,http://192.168.0.50:8999',
    ).split(',')
    if origin.strip()
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',
    'services',
    'bookings',
    'website',
    'panel',
    'audit',
    'hr',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'config.middleware.CanonicalHostMiddleware',
    'config.middleware.SiteMatrixStatusMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'website.middleware.MarketingAttributionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'website.context_processors.site_settings',
                'hr.context_processors.hr_view_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

if os.environ.get('DB_ENGINE', '').lower() in ('postgresql', 'postgres'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('DB_NAME', 'spotoncleaning'),
            'USER': os.environ.get('DB_USER', 'spoton'),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '5432'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.environ.get('SQLITE_PATH', str(BASE_DIR / 'db.sqlite3')),
        }
    }

AUTH_USER_MODEL = 'accounts.CustomUser'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-gb'
TIME_ZONE = 'Europe/London'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage',
    },
}

from config.static_utils import build_static_cache_versions  # noqa: E402

STATIC_CACHE_VERSIONS = build_static_cache_versions(
    'img/logo.png',
    'img/logo-alt.png',
    'img/favicon.png',
    'img/apple-touch-icon.png',
    'img/sitematrix-logo.png',
    'img/oven-before.jpg',
    'img/oven-after.jpg',
    'css/style.css',
    'css/sitematrix-offline.css',
    'js/main.js',
    'js/toast.js',
    'js/booking.js',
    'js/panel-bookings.js',
    'js/panel-schedule.js',
    'js/panel-coverage.js',
    'js/schedule-debug.js',
)

MEDIA_URL = 'media/'
MEDIA_ROOT = os.environ.get('MEDIA_ROOT', str(BASE_DIR / 'media'))

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'accounts:dashboard'
LOGOUT_REDIRECT_URL = 'website:home'

EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend',
)
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() in ('true', '1', 'yes')
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', 'False').lower() in ('true', '1', 'yes')
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get(
    'DEFAULT_FROM_EMAIL',
    'Spot On Appliance Cleaning <noreply@spotonappliancecleaning.co.uk>',
)

SITE_NAME = 'Spot On Appliance Cleaning'
SITE_TAGLINE = 'Appliance Shine. Every Time.'
SITE_PHONE = '07884 818633'
SITE_EMAIL = 'info@spotonappliancecleaning.co.uk'
SITE_ADDRESS = 'Serving customers across the local area'
SITE_URL = os.environ.get('SITE_URL', 'https://www.spotonappliancecleaning.co.uk').rstrip('/')
EMPLOYER_LEGAL_NAME = os.environ.get('EMPLOYER_LEGAL_NAME', SITE_NAME)
EMPLOYER_ADDRESS = os.environ.get('EMPLOYER_ADDRESS', 'West Yorkshire, United Kingdom')
EMPLOYER_REP_NAME = os.environ.get('EMPLOYER_REP_NAME', 'Director')
HR_INVITE_VALID_DAYS = int(os.environ.get('HR_INVITE_VALID_DAYS', '14'))
# Bare domain (spotonappliancecleaning.co.uk) may not reach the app via Cloudflare — use www in SITE_URL.
CANONICAL_HOST = os.environ.get('CANONICAL_HOST', 'www.spotonappliancecleaning.co.uk').strip()

# SiteMatrix — remote site on/off + subscription status (fail open if unreachable)
SITEMATRIX_API_KEY = os.environ.get('SITEMATRIX_API_KEY', '')
SITEMATRIX_STATUS_URL = os.environ.get('SITEMATRIX_STATUS_URL', '').strip()
if SITEMATRIX_STATUS_URL and not SITEMATRIX_STATUS_URL.endswith('/'):
    SITEMATRIX_STATUS_URL = f'{SITEMATRIX_STATUS_URL}/'
SITEMATRIX_CACHE_SECONDS = int(os.environ.get('SITEMATRIX_CACHE_SECONDS', '300'))
SITEMATRIX_TIMEOUT_SECONDS = int(os.environ.get('SITEMATRIX_TIMEOUT_SECONDS', '3'))
_sitematrix_enabled = os.environ.get(
    'SITEMATRIX_ENABLED',
    'true' if SITEMATRIX_API_KEY and SITEMATRIX_STATUS_URL else 'false',
).lower() in ('true', '1', 'yes')
SITEMATRIX_ENABLED = _sitematrix_enabled and bool(SITEMATRIX_API_KEY and SITEMATRIX_STATUS_URL)
SITEMATRIX_DEBUG = os.environ.get(
    'SITEMATRIX_DEBUG',
    'true' if DEBUG else 'false',
).lower() in ('true', '1', 'yes')
SITEMATRIX_PORTAL_URL = os.environ.get('SITEMATRIX_PORTAL_URL', '').strip()
SITEMATRIX_SUPPORT_URL = os.environ.get('SITEMATRIX_SUPPORT_URL', '').strip()

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    USE_X_FORWARDED_HOST = True
SITE_DESCRIPTION = os.environ.get(
    'SITE_DESCRIPTION',
    'Professional oven and appliance cleaning across West Yorkshire. Book online for oven, hob '
    'and extractor cleaning. Eco-friendly products, fully insured, transparent pricing.',
)
SITE_KEYWORDS = os.environ.get(
    'SITE_KEYWORDS',
    'oven cleaning, appliance cleaning, oven cleaner, hob cleaning, extractor cleaning, '
    'professional oven cleaning, West Yorkshire, book oven clean online',
)
SITE_LOCAL_AREA = os.environ.get('SITE_LOCAL_AREA', 'West Yorkshire')
LEGAL_LAST_UPDATED = os.environ.get('LEGAL_LAST_UPDATED', '22 June 2025')
# Meta (Facebook) Pixel — Events Manager → Data sources → your pixel ID (digits only)
META_PIXEL_ID = os.environ.get('META_PIXEL_ID', '').strip()
# Google Business Profile — link for reviews (find in Google Maps → Share → Write a review)
GOOGLE_REVIEWS_URL = os.environ.get('GOOGLE_REVIEWS_URL', '').strip()
GOOGLE_REVIEW_RATING = os.environ.get('GOOGLE_REVIEW_RATING', '5.0').strip()
GOOGLE_REVIEW_COUNT = os.environ.get('GOOGLE_REVIEW_COUNT', '').strip()
SERVICE_AREA_NAME = os.environ.get('SERVICE_AREA_NAME', SITE_LOCAL_AREA)
# Service area enforcement uses editable map boundaries in Panel → Service coverage.
# Set SERVICE_AREA_ENFORCED=False in .env to allow UK-wide booking again.
SERVICE_AREA_ENFORCED = os.environ.get('SERVICE_AREA_ENFORCED', 'True').lower() in (
    'true', '1', 'yes',
)
SITE_DEFAULT_SEO_TITLE = os.environ.get(
    'SITE_DEFAULT_SEO_TITLE',
    'Oven & Appliance Cleaning West Yorkshire | Spot On Appliance Cleaning',
)

# System administrator accounts — cannot be deleted (comma-separated emails)
SYSADMIN_EMAILS = [
    email.strip().lower()
    for email in os.environ.get(
        'SYSADMIN_EMAILS',
        'brad.crampton2001@gmail.com',
    ).split(',')
    if email.strip()
]

# Smart scheduling — travel time between jobs
USE_OSRM_ROUTING = os.environ.get('USE_OSRM_ROUTING', 'True').lower() in ('true', '1', 'yes')
OSRM_BASE_URL = os.environ.get('OSRM_BASE_URL', 'https://router.project-osrm.org/route/v1/driving')
DEFAULT_JOB_DURATION_MINUTES = int(os.environ.get('DEFAULT_JOB_DURATION_MINUTES', '60'))
DEFAULT_TRAVEL_MINUTES = int(os.environ.get('DEFAULT_TRAVEL_MINUTES', '30'))
MIN_TRAVEL_MINUTES = int(os.environ.get('MIN_TRAVEL_MINUTES', '5'))
TRAVEL_BUFFER_MINUTES = int(os.environ.get('TRAVEL_BUFFER_MINUTES', '5'))
ROAD_DISTANCE_FACTOR = float(os.environ.get('ROAD_DISTANCE_FACTOR', '1.35'))
AVERAGE_DRIVING_SPEED_KMH = float(os.environ.get('AVERAGE_DRIVING_SPEED_KMH', '45'))
BUSINESS_BASE_POSTCODE = os.environ.get('BUSINESS_BASE_POSTCODE', '')

# Day-before booking reminders (run via send_booking_reminders management command)
BOOKING_REMINDERS_ENABLED = os.environ.get('BOOKING_REMINDERS_ENABLED', 'True').lower() in ('true', '1', 'yes')

# SMS via Twilio (optional — reminders still send email if SMS is not configured)
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '').strip()
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '').strip()
TWILIO_FROM_NUMBER = os.environ.get('TWILIO_FROM_NUMBER', '').strip()
SMS_ENABLED = bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'django.security.DisallowedHost': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'config.sitematrix': {
            'handlers': ['console'],
            'level': 'INFO' if SITEMATRIX_DEBUG else 'WARNING',
            'propagate': False,
        },
    },
}

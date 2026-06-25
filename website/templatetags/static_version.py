from django import template
from django.templatetags.static import static

from config.static_utils import static_cache_version

register = template.Library()


@register.simple_tag
def static_v(path):
    url = static(path)
    version = static_cache_version(path)
    separator = '&' if '?' in url else '?'
    return f'{url}{separator}v={version}'

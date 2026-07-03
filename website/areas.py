from django.shortcuts import get_object_or_404

from bookings.models import CoverageArea


def get_public_coverage_areas():
    return list(CoverageArea.objects.filter(enabled=True).order_by('sort_order', 'name'))


def get_public_coverage_area(slug):
    return get_object_or_404(CoverageArea, slug=slug, enabled=True)


def group_areas_by_region(areas):
    grouped = {}
    for area in areas:
        grouped.setdefault(area.region_group, []).append(area)
    return grouped


def area_page_title(area):
    return f'Oven Cleaning {area.name} | Professional Appliance Cleaning'


def area_meta_description(area, site_name, local_area):
    return (
        f'Book professional oven, hob and extractor cleaning in {area.name}, {local_area}. '
        f'{site_name} — family-friendly products, online booking, fully insured technicians.'
    )

import json

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from audit.actions import COVERAGE_AREA_UPDATED
from audit.services import log_action
from bookings.coverage import (
    coverage_areas_for_map,
    lookup_coverage_search,
    set_coverage_area_enabled,
    set_region_enabled,
)
from bookings.coverage_data import EXCLUDED_POSTCODE_DISTRICTS, REGION_GROUP_SLUGS, REGION_GROUPS, REGION_SLUGS
from bookings.models import CoverageArea
from bookings.service_area import service_area_enforced, service_area_name
from panel.decorators import admin_required


def _region_sections(areas):
    grouped = {group: [] for group in REGION_GROUPS}
    for area in areas:
        grouped.setdefault(area.region_group, []).append(area)
    return [
        {
            'name': group,
            'slug': REGION_GROUP_SLUGS[group],
            'areas': grouped.get(group, []),
        }
        for group in REGION_GROUPS
    ]


@admin_required
@require_GET
def coverage_map_view(request):
    areas = CoverageArea.objects.order_by('sort_order', 'name')
    enabled_count = areas.filter(enabled=True).count()
    return render(request, 'panel/coverage/map.html', {
        'areas': areas,
        'region_sections': _region_sections(areas),
        'enabled_count': enabled_count,
        'total_count': areas.count(),
        'service_area_name': service_area_name(),
        'service_area_enforced': service_area_enforced(),
        'excluded_districts': EXCLUDED_POSTCODE_DISTRICTS,
        'map_geojson': json.dumps(coverage_areas_for_map()),
    })


@admin_required
@require_GET
def coverage_map_api(request):
    return JsonResponse(coverage_areas_for_map())


@admin_required
@require_GET
def coverage_search_api(request):
    query = request.GET.get('q', '').strip() or request.GET.get('postcode', '').strip()
    if not query:
        return JsonResponse({'error': 'Enter a postcode or area name.'}, status=400)
    result = lookup_coverage_search(query)
    if result.get('error'):
        return JsonResponse(result, status=404)
    return JsonResponse(result)


@admin_required
@require_POST
def coverage_toggle_api(request, slug):
    area = CoverageArea.objects.filter(slug=slug).first()
    if not area:
        return JsonResponse({'error': 'Area not found.'}, status=404)

    enabled = request.POST.get('enabled', '').lower() in ('1', 'true', 'yes', 'on')
    if area.enabled == enabled:
        return JsonResponse({
            'success': True,
            'slug': area.slug,
            'enabled': area.enabled,
            'unchanged': True,
        })

    set_coverage_area_enabled(slug, enabled)
    area.refresh_from_db()

    log_action(
        COVERAGE_AREA_UPDATED,
        f'{"Enabled" if area.enabled else "Disabled"} coverage for {area.name}.',
        request=request,
        target_type='coverage_area',
        target_id=area.pk,
        target_label=area.name,
        metadata={'slug': area.slug, 'enabled': area.enabled},
    )

    messages.success(
        request,
        f'{area.name} is now {"accepting" if area.enabled else "not accepting"} online bookings.',
    )

    return JsonResponse({
        'success': True,
        'slug': area.slug,
        'name': area.name,
        'enabled': area.enabled,
        'enabled_count': CoverageArea.objects.filter(enabled=True).count(),
    })


@admin_required
@require_POST
def coverage_region_toggle_api(request, region_slug):
    region_group = REGION_SLUGS.get(region_slug)
    if not region_group:
        return JsonResponse({'error': 'Region not found.'}, status=404)

    enabled = request.POST.get('enabled', '').lower() in ('1', 'true', 'yes', 'on')
    set_region_enabled(region_group, enabled)

    log_action(
        COVERAGE_AREA_UPDATED,
        f'{"Enabled" if enabled else "Disabled"} all coverage in {region_group}.',
        request=request,
        target_type='coverage_region',
        target_label=region_group,
        metadata={'region_group': region_group, 'enabled': enabled},
    )

    areas = CoverageArea.objects.filter(region_group=region_group).order_by('sort_order', 'name')
    return JsonResponse({
        'success': True,
        'region_group': region_group,
        'enabled': enabled,
        'areas': [
            {'slug': area.slug, 'enabled': area.enabled}
            for area in areas
        ],
        'enabled_count': CoverageArea.objects.filter(enabled=True).count(),
    })

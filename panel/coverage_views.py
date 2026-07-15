import json

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from audit.actions import COVERAGE_AREA_UPDATED, COVERAGE_BOUNDARY_UPDATED
from audit.services import log_action
from bookings.coverage import (
    coverage_areas_for_map,
    create_editable_coverage_boundary,
    delete_editable_coverage_boundary,
    editable_boundaries_geojson,
    get_editable_coverage_boundaries,
    lookup_coverage_search,
    save_editable_coverage_boundaries,
    set_coverage_area_enabled,
    set_region_enabled,
)
from bookings.postcode_estimates import coverage_boundary_stats_summary
from bookings.coverage_data import REGION_SLUGS
from bookings.models import CoverageArea
from bookings.service_area import service_area_enforced
from panel.decorators import admin_required


@admin_required
@require_GET
def coverage_map_view(request):
    boundaries = get_editable_coverage_boundaries()
    stats = coverage_boundary_stats_summary(boundaries)
    return render(request, 'panel/coverage/map.html', {
        'boundaries': boundaries,
        'boundary_count': len(boundaries),
        'coverage_stats': stats,
        'editable_boundaries_geojson': json.dumps(editable_boundaries_geojson()),
        'service_area_enforced': service_area_enforced(),
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


@admin_required
@require_POST
def coverage_boundary_save_api(request):
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON payload.'}, status=400)

    items = payload.get('boundaries')
    if items is None and payload.get('ring'):
        items = [{
            'slug': payload.get('slug', ''),
            'ring': payload.get('ring', []),
            'name': payload.get('name', ''),
        }]

    try:
        boundaries = save_editable_coverage_boundaries(items or [])
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)

    log_action(
        COVERAGE_BOUNDARY_UPDATED,
        f'Saved {len(boundaries)} service boundar{"y" if len(boundaries) == 1 else "ies"} on the coverage map.',
        request=request,
        target_type='coverage_boundary',
        target_label='Service boundaries',
        metadata={'boundary_count': len(boundaries)},
    )

    messages.success(request, 'Service boundaries saved.')
    stats = coverage_boundary_stats_summary(boundaries)
    return JsonResponse({
        'success': True,
        'boundaries': boundaries,
        'geojson': editable_boundaries_geojson(),
        'stats': stats,
    })


@admin_required
@require_POST
def coverage_boundary_create_api(request):
    try:
        center_lat = float(request.POST.get('lat', '53.85'))
        center_lng = float(request.POST.get('lng', '-1.45'))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Invalid map centre.'}, status=400)

    boundary = create_editable_coverage_boundary(center_lat, center_lng)

    log_action(
        COVERAGE_BOUNDARY_UPDATED,
        f'Added service boundary {boundary["name"]}.',
        request=request,
        target_type='coverage_boundary',
        target_label=boundary['name'],
        metadata={'slug': boundary['slug'], 'created': True},
    )

    messages.success(request, f'{boundary["name"]} added — drag it into place, then save all.')
    boundaries = get_editable_coverage_boundaries()
    return JsonResponse({
        'success': True,
        'boundary': boundary,
        'boundaries': boundaries,
        'geojson': editable_boundaries_geojson(),
        'stats': coverage_boundary_stats_summary(boundaries),
    })


@admin_required
@require_POST
def coverage_boundary_delete_api(request, slug):
    boundary = next(
        (item for item in get_editable_coverage_boundaries() if item['slug'] == slug),
        None,
    )
    if not boundary:
        return JsonResponse({'error': 'Boundary not found.'}, status=404)

    delete_editable_coverage_boundary(slug)

    log_action(
        COVERAGE_BOUNDARY_UPDATED,
        f'Removed service boundary {boundary["name"]}.',
        request=request,
        target_type='coverage_boundary',
        target_label=boundary['name'],
        metadata={'slug': slug, 'deleted': True},
    )

    messages.success(request, f'{boundary["name"]} removed.')
    boundaries = get_editable_coverage_boundaries()
    return JsonResponse({
        'success': True,
        'slug': slug,
        'boundaries': boundaries,
        'geojson': editable_boundaries_geojson(),
        'stats': coverage_boundary_stats_summary(boundaries),
    })


@admin_required
@require_POST
def coverage_boundary_reset_api(request):
    """Backward-compatible alias for creating a new square."""
    return coverage_boundary_create_api(request)

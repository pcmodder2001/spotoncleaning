(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        const cfg = window.panelCoverageConfig;
        const mapEl = document.getElementById('coverageMap');
        if (!cfg || !mapEl || typeof L === 'undefined') return;

        const layersBySlug = {};
        const featuresBySlug = {};
        let searchMarker = null;
        let combinedOutlineLayer = null;

        const map = L.map(mapEl, {
            scrollWheelZoom: true,
            tap: true,
        }).setView([53.85, -1.45], 9);

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 18,
            attribution: '&copy; OpenStreetMap contributors',
        }).addTo(map);

        function toggleUrl(slug) {
            return cfg.toggleUrlTemplate.replace('__slug__', encodeURIComponent(slug));
        }

        function regionToggleUrl(regionSlug) {
            return cfg.regionToggleUrlTemplate.replace('__region__', encodeURIComponent(regionSlug));
        }

        function styleForPolygon(enabled, color) {
            return {
                color: enabled ? color : '#64748b',
                weight: enabled ? 2.5 : 1.5,
                fillColor: enabled ? color : '#94a3b8',
                fillOpacity: enabled ? 0.28 : 0.06,
                dashArray: enabled ? null : '6 4',
            };
        }

        function outlineStyle() {
            return {
                color: '#0e7490',
                weight: 4,
                fillColor: '#0e7490',
                fillOpacity: 0.04,
                dashArray: null,
            };
        }

        function bindLayerEvents(layer, props, feature) {
            const slugs = props.slugs || [props.slug];
            featuresBySlug[props.slug] = feature;

            slugs.forEach(function (slug) {
                layersBySlug[slug] = { layer: layer, props: props, feature: feature };
            });

            function refreshPopup() {
                const enabled = props.enabled;
                let html = '<div class="coverage-popup"><strong>' + escapeHtml(props.name) + '</strong><br>';
                if (props.names && props.names.length > 1) {
                    html += '<span class="text-muted small">' + escapeHtml(props.names.join(', ')) + '</span><br>';
                } else {
                    html += '<span class="text-muted small">' + escapeHtml(props.postcode_label || '') + '</span><br>';
                }
                html += '<span class="badge ' + (enabled ? 'bg-success' : 'bg-secondary') + ' mt-2">' +
                    (enabled ? 'Coverage on' : 'Coverage off') + '</span>';
                html += '<div class="mt-2 d-flex flex-wrap gap-1">';
                slugs.forEach(function (slug) {
                    const item = document.querySelector('.coverage-area-list-item[data-slug="' + slug + '"]');
                    const labelEl = item && item.querySelector('strong');
                    const label = labelEl ? labelEl.textContent : slug.replace(/-/g, ' ');
                    const isOn = item && item.dataset.enabled === 'true';
                    html += '<button type="button" class="btn btn-sm ' + (isOn ? 'btn-outline-danger' : 'btn-primary') +
                        ' coverage-popup-toggle" data-slug="' + escapeHtml(slug) + '" data-enabled="' +
                        (isOn ? 'false' : 'true') + '">' + (isOn ? 'Turn off' : 'Turn on') + ' ' + escapeHtml(label) + '</button>';
                });
                html += '</div></div>';
                layer.setPopupContent(html);
            }

            layer.on('click', function () {
                layer.openPopup();
            });

            layer.on('popupopen', function () {
                document.querySelectorAll('.coverage-popup-toggle').forEach(function (btn) {
                    btn.addEventListener('click', function (event) {
                        event.preventDefault();
                        toggleArea(btn.dataset.slug, btn.dataset.enabled === 'true');
                    });
                });
            });

            layer.bindPopup('');
            refreshPopup();
            layer.on('popupopen', refreshPopup);
        }

        function rebuildCombinedOutline() {
            if (combinedOutlineLayer) {
                map.removeLayer(combinedOutlineLayer);
                combinedOutlineLayer = null;
            }
            if (typeof turf === 'undefined') return;

            const seen = new Set();
            const enabledFeatures = [];
            Object.values(layersBySlug).forEach(function (entry) {
                if (!entry.props.enabled || !entry.feature || seen.has(entry.feature)) return;
                seen.add(entry.feature);
                enabledFeatures.push(entry.feature);
            });

            if (!enabledFeatures.length) return;

            let merged = enabledFeatures[0];
            try {
                for (let i = 1; i < enabledFeatures.length; i++) {
                    merged = turf.union(merged, enabledFeatures[i]);
                }
                combinedOutlineLayer = L.geoJSON(merged, {
                    interactive: false,
                    style: outlineStyle,
                }).addTo(map);
            } catch (error) {
                // Individual district polygons still render if union fails.
            }
        }

        function refreshPolygonStyles() {
            const seenLayers = new Set();
            Object.values(layersBySlug).forEach(function (entry) {
                if (seenLayers.has(entry.layer)) return;
                seenLayers.add(entry.layer);
                const slugs = entry.props.slugs || [entry.props.slug];
                const anyOn = slugs.some(function (s) {
                    const item = document.querySelector('.coverage-area-list-item[data-slug="' + s + '"]');
                    return item && item.dataset.enabled === 'true';
                });
                entry.props.enabled = anyOn;
                entry.layer.setStyle(styleForPolygon(anyOn, entry.props.color));
            });
            rebuildCombinedOutline();
        }

        (cfg.geojson.features || []).forEach(function (feature) {
            const props = feature.properties || {};
            if (!feature.geometry || feature.geometry.type !== 'Polygon') return;

            const layer = L.geoJSON(feature, {
                style: function () {
                    return styleForPolygon(props.enabled, props.color);
                },
            }).getLayers()[0];
            if (!layer) return;

            bindLayerEvents(layer, props, feature);
            layer.addTo(map);
        });

        const allLayers = Object.values(layersBySlug)
            .map(function (entry) { return entry.layer; })
            .filter(function (layer, index, arr) { return arr.indexOf(layer) === index; });

        if (allLayers.length) {
            map.fitBounds(L.featureGroup(allLayers).getBounds().pad(0.06));
        }

        rebuildCombinedOutline();

        function updateUi(slug, enabled, enabledCount) {
            document.querySelectorAll('[data-slug="' + slug + '"]').forEach(function (el) {
                if (el.classList.contains('coverage-area-list-item')) {
                    el.dataset.enabled = enabled ? 'true' : 'false';
                }
                if (el.classList.contains('coverage-toggle-btn')) {
                    el.dataset.enabled = enabled ? 'true' : 'false';
                    el.textContent = enabled ? 'On' : 'Off';
                    el.classList.toggle('btn-success', enabled);
                    el.classList.toggle('btn-outline-secondary', !enabled);
                }
            });

            refreshPolygonStyles();

            const badge = document.querySelector('.coverage-active-badge');
            if (badge && typeof enabledCount === 'number') {
                const total = document.querySelectorAll('.coverage-area-list-item').length;
                badge.textContent = enabledCount + ' / ' + total + ' areas active';
                badge.classList.toggle('bg-success', enabledCount > 0);
                badge.classList.toggle('bg-danger', enabledCount === 0);
            }
        }

        function toggleArea(slug, enabled) {
            const body = new FormData();
            body.append('enabled', enabled ? 'true' : 'false');
            body.append('csrfmiddlewaretoken', cfg.csrfToken);

            fetch(toggleUrl(slug), {
                method: 'POST',
                headers: { 'X-CSRFToken': cfg.csrfToken },
                body: body,
            })
                .then(function (response) { return response.json().then(function (data) { return { ok: response.ok, data: data }; }); })
                .then(function ({ ok, data }) {
                    if (!ok || !data.success) {
                        throw new Error((data && data.error) || 'Could not update coverage');
                    }
                    updateUi(data.slug, data.enabled, data.enabled_count);
                })
                .catch(function (error) {
                    if (window.showAppToast) {
                        window.showAppToast(error.message, 'error');
                    }
                });
        }

        function toggleRegion(regionSlug, enabled) {
            const body = new FormData();
            body.append('enabled', enabled ? 'true' : 'false');
            body.append('csrfmiddlewaretoken', cfg.csrfToken);

            fetch(regionToggleUrl(regionSlug), {
                method: 'POST',
                headers: { 'X-CSRFToken': cfg.csrfToken },
                body: body,
            })
                .then(function (response) { return response.json().then(function (data) { return { ok: response.ok, data: data }; }); })
                .then(function ({ ok, data }) {
                    if (!ok || !data.success) {
                        throw new Error((data && data.error) || 'Could not update region');
                    }
                    (data.areas || []).forEach(function (area) {
                        updateUi(area.slug, area.enabled, data.enabled_count);
                    });
                })
                .catch(function (error) {
                    if (window.showAppToast) {
                        window.showAppToast(error.message, 'error');
                    }
                });
        }

        document.querySelectorAll('.coverage-toggle-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                toggleArea(btn.dataset.slug, btn.dataset.enabled !== 'true');
            });
        });

        document.querySelectorAll('.coverage-region-toggle').forEach(function (btn) {
            btn.addEventListener('click', function () {
                toggleRegion(btn.dataset.regionSlug, btn.dataset.enabled === 'true');
            });
        });

        const searchForm = document.getElementById('coverageSearchForm');
        const searchInput = document.getElementById('coverageSearchInput');
        const searchResult = document.getElementById('coverageSearchResult');

        function showSearchResult(data) {
            if (!searchResult) return;

            let html;
            if (data.search_type === 'area') {
                const label = data.area_name || data.query;
                if (data.covered) {
                    html = '<span class="text-success"><strong>' + escapeHtml(label) + '</strong> coverage is on.</span>';
                } else {
                    html = '<span class="text-warning"><strong>' + escapeHtml(label) + '</strong> coverage is off.</span>';
                }
                if (data.matching_areas && data.matching_areas.length > 1) {
                    const others = data.matching_areas
                        .filter(function (area) { return area.slug !== data.area_slug; })
                        .map(function (area) { return area.name; });
                    if (others.length) {
                        html += ' <span class="text-muted">Also matched: ' + escapeHtml(others.join(', ')) + '.</span>';
                    }
                }
            } else if (data.search_type === 'place') {
                html = '<span class="text-muted"><strong>' + escapeHtml(data.query) + '</strong> is on the map but is not one of your coverage areas yet. Turn on a nearby area below if you want to accept bookings there.</span>';
            } else if (data.excluded) {
                html = '<span class="text-danger"><strong>' + escapeHtml(data.postcode) + '</strong> is always excluded (outside service area).</span>';
            } else if (data.covered) {
                html = '<span class="text-success"><strong>' + escapeHtml(data.postcode) + '</strong> is covered';
                if (data.enabled_matches && data.enabled_matches.length) {
                    html += ' (' + escapeHtml(data.enabled_matches.join(', ')) + ')';
                }
                html += '.</span>';
            } else if (data.matching_areas && data.matching_areas.length) {
                const names = data.matching_areas.map(function (area) {
                    return area.name + (area.enabled ? '' : ' — off');
                });
                html = '<span class="text-warning"><strong>' + escapeHtml(data.postcode) + '</strong> matches ' +
                    escapeHtml(names.join(', ')) + ' but coverage is off.</span>';
            } else {
                html = '<span class="text-danger"><strong>' + escapeHtml(data.postcode || data.query || 'Search') + '</strong> is not in any defined area.</span>';
            }

            if (data.admin_district) {
                html += ' <span class="text-muted">(' + escapeHtml(data.admin_district) + ')</span>';
            }

            searchResult.innerHTML = html;
            searchResult.hidden = false;
        }

        function focusSearchResult(data) {
            if (searchMarker) {
                map.removeLayer(searchMarker);
                searchMarker = null;
            }

            const slug = data.area_slug || (
                data.matching_areas && data.matching_areas.length ? data.matching_areas[0].slug : ''
            );
            const entry = slug && layersBySlug[slug];
            if (entry && entry.layer) {
                map.fitBounds(entry.layer.getBounds().pad(0.15));
                entry.layer.openPopup();
                return;
            }

            if (data.lat == null || data.lng == null) return;

            const iconColor = data.covered ? '#16a34a' : (data.matching_areas && data.matching_areas.length ? '#ca8a04' : '#dc2626');
            searchMarker = L.circleMarker([data.lat, data.lng], {
                radius: 10,
                color: '#fff',
                weight: 2,
                fillColor: iconColor,
                fillOpacity: 1,
            }).addTo(map);
            const popupLabel = data.postcode || data.area_name || data.query;
            searchMarker.bindPopup('<strong>' + escapeHtml(popupLabel) + '</strong>').openPopup();
            map.flyTo([data.lat, data.lng], 12, { duration: 0.8 });
        }

        if (searchForm && searchInput) {
            searchForm.addEventListener('submit', function (event) {
                event.preventDefault();
                const query = searchInput.value.trim();
                if (!query) return;

                fetch(cfg.searchUrl + '?q=' + encodeURIComponent(query), {
                    headers: { 'Accept': 'application/json' },
                })
                    .then(function (response) { return response.json().then(function (data) { return { ok: response.ok, data: data }; }); })
                    .then(function ({ ok, data }) {
                        if (!ok) {
                            throw new Error((data && data.error) || 'Search failed');
                        }
                        showSearchResult(data);
                        focusSearchResult(data);
                    })
                    .catch(function (error) {
                        if (searchResult) {
                            searchResult.innerHTML = '<span class="text-danger">' + escapeHtml(error.message) + '</span>';
                            searchResult.hidden = false;
                        }
                    });
            });
        }

        setTimeout(function () { map.invalidateSize(); }, 150);
    });

    function escapeHtml(value) {
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }
})();

(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        const cfg = window.panelCoverageConfig;
        const mapEl = document.getElementById('coverageMap');
        if (!cfg || !mapEl || typeof L === 'undefined') return;

        const map = L.map(mapEl, {
            scrollWheelZoom: true,
            tap: true,
        }).setView([53.85, -1.45], 6);

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 18,
            attribution: '&copy; OpenStreetMap contributors',
        }).addTo(map);

        if (map.pm) {
            map.pm.setGlobalOptions({
                snappable: true,
                snapDistance: 20,
                allowSelfIntersection: false,
            });
        }

        initLocationSearch(map, cfg);
        initEditableBoundaries(map, cfg);

        setTimeout(function () { map.invalidateSize(); }, 150);
    });

    function initLocationSearch(map, cfg) {
        const searchForm = document.getElementById('coverageSearchForm');
        const searchInput = document.getElementById('coverageSearchInput');
        const searchResult = document.getElementById('coverageSearchResult');
        if (!searchForm || !searchInput) return;

        let searchMarker = null;

        function focusSearchResult(data) {
            if (searchMarker) {
                map.removeLayer(searchMarker);
                searchMarker = null;
            }

            if (data.lat == null || data.lng == null) return;

            searchMarker = L.circleMarker([data.lat, data.lng], {
                radius: 10,
                color: '#fff',
                weight: 2,
                fillColor: '#2563eb',
                fillOpacity: 1,
            }).addTo(map);

            const popupLabel = data.postcode || data.area_name || data.query;
            searchMarker.bindPopup('<strong>' + escapeHtml(popupLabel) + '</strong>').openPopup();
            map.flyTo([data.lat, data.lng], 10, { duration: 0.8 });
        }

        searchForm.addEventListener('submit', function (event) {
            event.preventDefault();
            const query = searchInput.value.trim();
            if (!query) return;

            fetch(cfg.searchUrl + '?q=' + encodeURIComponent(query), {
                headers: { 'Accept': 'application/json' },
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        return { ok: response.ok, data: data };
                    });
                })
                .then(function ({ ok, data }) {
                    if (!ok) {
                        throw new Error((data && data.error) || 'Search failed');
                    }
                    focusSearchResult(data);
                    if (searchResult) {
                        const label = data.postcode || data.area_name || data.query || query;
                        searchResult.innerHTML = '<span class="text-muted">Showing <strong>' + escapeHtml(label) + '</strong> on the map.</span>';
                        searchResult.hidden = false;
                    }
                })
                .catch(function (error) {
                    if (searchResult) {
                        searchResult.innerHTML = '<span class="text-danger">' + escapeHtml(error.message) + '</span>';
                        searchResult.hidden = false;
                    }
                });
        });
    }

    function initEditableBoundaries(map, cfg) {
        const addBtn = document.getElementById('coverageBoundaryAddBtn');
        const editBtn = document.getElementById('coverageBoundaryEditBtn');
        const saveBtn = document.getElementById('coverageBoundarySaveBtn');
        const statusEl = document.getElementById('coverageBoundaryStatus');
        const listEl = document.getElementById('coverageBoundaryList');
        const countBadge = document.getElementById('coverageBoundaryCountBadge');
        if (!addBtn || !editBtn || !saveBtn || typeof map.pm === 'undefined') return;

        const boundaryLayers = {};
        const SEGMENTS_PER_SIDE = 5;
        const MIN_VERTICES_FOR_DENSE_RING = SEGMENTS_PER_SIDE * 4;

        function deleteUrl(slug) {
            return cfg.boundaryDeleteUrlTemplate.replace('__slug__', encodeURIComponent(slug));
        }

        function setBoundaryStatus(message) {
            if (statusEl) statusEl.textContent = message;
        }

        function markDirty() {
            saveBtn.disabled = false;
            setBoundaryStatus('Unsaved changes');
        }

        function ringFromLayer(layer) {
            let latlngs = layer.getLatLngs();
            if (Array.isArray(latlngs[0]) && latlngs[0].length && latlngs[0][0] && latlngs[0][0].lat !== undefined) {
                latlngs = latlngs[0];
            } else if (Array.isArray(latlngs[0]) && !latlngs[0].lat) {
                latlngs = latlngs[0];
            }
            return latlngs.map(function (ll) {
                return [
                    Math.round(ll.lat * 1000000) / 1000000,
                    Math.round(ll.lng * 1000000) / 1000000,
                ];
            });
        }

        function densifyRing(ring, segmentsPerSide) {
            if (!ring || ring.length < 3) return ring;

            const closed = (
                ring.length > 1
                && ring[0][0] === ring[ring.length - 1][0]
                && ring[0][1] === ring[ring.length - 1][1]
            );
            const vertices = closed ? ring.slice(0, -1) : ring.slice();
            if (vertices.length >= segmentsPerSide * 4) {
                return closed ? ring.slice(0, -1) : vertices;
            }

            const dense = [];
            for (let index = 0; index < vertices.length; index++) {
                const start = vertices[index];
                const end = vertices[(index + 1) % vertices.length];
                for (let step = 0; step < segmentsPerSide; step++) {
                    const t = step / segmentsPerSide;
                    dense.push([
                        Math.round((start[0] + (end[0] - start[0]) * t) * 1000000) / 1000000,
                        Math.round((start[1] + (end[1] - start[1]) * t) * 1000000) / 1000000,
                    ]);
                }
            }
            return dense;
        }

        function applyDenseRingToLayer(layer, markChanged) {
            const ring = ringFromLayer(layer);
            const dense = densifyRing(ring, SEGMENTS_PER_SIDE);
            if (dense.length <= ring.length) return false;
            layer.setLatLngs(dense.map(function (point) {
                return L.latLng(point[0], point[1]);
            }));
            if (markChanged) markDirty();
            return true;
        }

        function styleForBoundary(color) {
            return {
                color: color,
                weight: 4,
                fillColor: color,
                fillOpacity: 0.14,
            };
        }

        function enableLayerEdit(layer) {
            applyDenseRingToLayer(layer, true);
            layer.pm.enable({
                allowSelfIntersection: false,
                draggable: true,
                snappable: true,
            });
        }

        function disableLayerEdit(layer) {
            if (layer.pm) {
                layer.pm.disable();
            }
        }

        function bindLayerEvents(layer) {
            ['pm:edit', 'pm:drag', 'pm:dragstart', 'pm:dragend', 'pm:markerdrag', 'pm:vertexadded', 'pm:vertexremoved', 'pm:rotateend']
                .forEach(function (eventName) {
                    layer.on(eventName, markDirty);
                });

            layer.on('click', function () {
                enableLayerEdit(layer);
                setBoundaryStatus('Drag the dots to reshape, drag inside the shape to move it, or click an edge to add more points');
            });
        }

        function removeBoundaryLayer(slug) {
            const entry = boundaryLayers[slug];
            if (!entry) return;
            disableLayerEdit(entry.layer);
            map.removeLayer(entry.layer);
            delete boundaryLayers[slug];
        }

        function clearBoundaryLayers() {
            Object.keys(boundaryLayers).forEach(removeBoundaryLayer);
        }

        function addBoundaryLayer(feature, autoEdit) {
            if (!feature || !feature.geometry || feature.geometry.type !== 'Polygon') return null;

            const props = feature.properties || {};
            const slug = props.slug;
            const color = props.color || '#dc2626';
            let ring = (feature.geometry.coordinates[0] || []).map(function (coord) {
                return [coord[1], coord[0]];
            });
            if (ring.length > 1
                && ring[0][0] === ring[ring.length - 1][0]
                && ring[0][1] === ring[ring.length - 1][1]) {
                ring = ring.slice(0, -1);
            }
            if (ring.length < MIN_VERTICES_FOR_DENSE_RING) {
                ring = densifyRing(ring, SEGMENTS_PER_SIDE);
            }

            removeBoundaryLayer(slug);

            const layer = L.polygon(ring, styleForBoundary(color));
            layer.addTo(map);
            layer._boundaryMeta = {
                slug: slug,
                name: props.name || slug,
                color: color,
            };
            bindLayerEvents(layer);
            boundaryLayers[slug] = { layer: layer };

            if (autoEdit) {
                enableLayerEdit(layer);
                map.fitBounds(layer.getBounds().pad(0.2));
            }

            return layer;
        }

        function loadBoundaries(geojson, focusSlug, boundaries, stats) {
            clearBoundaryLayers();
            const features = (geojson && geojson.features) || [];
            const items = boundaries || features.map(function (feature) { return feature.properties || {}; });
            features.forEach(function (feature) {
                const slug = feature.properties && feature.properties.slug;
                addBoundaryLayer(feature, focusSlug && slug === focusSlug);
            });
            renderBoundaryList(items);
            updateCountBadge(items.length);
            updateStatsSummary(stats, items);

            if (features.length && !focusSlug) {
                const group = L.featureGroup(Object.values(boundaryLayers).map(function (entry) { return entry.layer; }));
                if (group.getLayers().length) {
                    map.fitBounds(group.getBounds().pad(0.08));
                }
            }
        }

        function formatBoundaryMeta(item) {
            const postcodes = parseInt(item.estimated_postcode_count, 10) || 0;
            const districts = parseInt(item.district_count, 10) || 0;
            if (postcodes) {
                return '~' + postcodes.toLocaleString() + ' postcodes · ' + districts.toLocaleString() + ' districts';
            }
            return 'Save to calculate postcode estimate';
        }

        function renderBoundaryList(items) {
            if (!listEl) return;

            if (!items.length) {
                listEl.innerHTML = '';
                listEl.classList.add('d-none');
                return;
            }

            listEl.classList.remove('d-none');
            listEl.innerHTML = items.map(function (item) {
                return (
                    '<div class="coverage-boundary-list-item" data-slug="' + escapeHtml(item.slug) + '">' +
                    '<span class="coverage-boundary-swatch" style="background:' + escapeHtml(item.color || '#dc2626') + ';"></span>' +
                    '<div class="coverage-boundary-copy">' +
                    '<span class="coverage-boundary-name">' + escapeHtml(item.name || item.slug) + '</span>' +
                    '<span class="coverage-boundary-meta text-muted small">' + escapeHtml(formatBoundaryMeta(item)) + '</span>' +
                    '</div>' +
                    '<button type="button" class="btn btn-sm btn-outline-danger coverage-boundary-delete-btn" ' +
                    'data-slug="' + escapeHtml(item.slug) + '" data-name="' + escapeHtml(item.name || item.slug) + '">Remove</button>' +
                    '</div>'
                );
            }).join('');

            listEl.querySelectorAll('.coverage-boundary-delete-btn').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    deleteBoundary(btn.dataset.slug, btn.dataset.name);
                });
            });
        }

        function updateStatsSummary(stats, boundaries) {
            const statsEl = document.getElementById('coverageBoundaryStats');
            const totalPostcodesEl = document.getElementById('coverageTotalPostcodes');
            const totalDistrictsEl = document.getElementById('coverageTotalDistricts');
            const totalAreasEl = document.getElementById('coverageTotalAreas');

            const summary = stats || {
                area_count: (boundaries || []).length,
                total_estimated_postcodes: (boundaries || []).reduce(function (sum, item) {
                    return sum + (parseInt(item.estimated_postcode_count, 10) || 0);
                }, 0),
                total_districts: (boundaries || []).reduce(function (sum, item) {
                    return sum + (parseInt(item.district_count, 10) || 0);
                }, 0),
            };

            if (totalPostcodesEl) totalPostcodesEl.textContent = summary.total_estimated_postcodes.toLocaleString();
            if (totalDistrictsEl) totalDistrictsEl.textContent = summary.total_districts.toLocaleString();
            if (totalAreasEl) totalAreasEl.textContent = String(summary.area_count);

            if (statsEl) {
                statsEl.classList.toggle('d-none', !summary.total_estimated_postcodes);
            }
        }

        function updateCountBadge(count) {
            if (!countBadge) return;
            countBadge.textContent = count + ' area' + (count === 1 ? '' : 's');
        }

        function enableAllEdit() {
            const layers = Object.values(boundaryLayers);
            if (!layers.length) {
                setBoundaryStatus('Add a square first');
                return;
            }
            layers.forEach(function (entry) {
                enableLayerEdit(entry.layer);
            });
            setBoundaryStatus('Drag the dots to reshape, drag inside the shape to move it, or click an edge to add more points');
        }

        function disableAllEdit() {
            Object.values(boundaryLayers).forEach(function (entry) {
                disableLayerEdit(entry.layer);
            });
        }

        function collectBoundariesPayload() {
            return Object.values(boundaryLayers).map(function (entry) {
                const meta = entry.layer._boundaryMeta || {};
                return {
                    slug: meta.slug,
                    name: meta.name,
                    ring: ringFromLayer(entry.layer),
                };
            });
        }

        function saveAllBoundaries() {
            const boundaries = collectBoundariesPayload();
            if (!boundaries.length) {
                setBoundaryStatus('Add at least one square first');
                return;
            }

            saveBtn.disabled = true;
            setBoundaryStatus('Saving and calculating postcodes…');

            fetch(cfg.boundarySaveUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': cfg.csrfToken,
                    'Accept': 'application/json',
                },
                body: JSON.stringify({ boundaries: boundaries }),
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        return { ok: response.ok, data: data };
                    });
                })
                .then(function ({ ok, data }) {
                    if (!ok || !data.success) {
                        throw new Error((data && data.error) || 'Could not save boundaries');
                    }
                    disableAllEdit();
                    loadBoundaries(data.geojson, null, data.boundaries, data.stats);
                    saveBtn.disabled = true;
                    const total = data.stats && data.stats.total_estimated_postcodes;
                    setBoundaryStatus(
                        total
                            ? 'Saved — ~' + total.toLocaleString() + ' postcodes across ' + data.boundaries.length + ' areas'
                            : (data.boundaries || []).length + ' areas saved'
                    );
                    if (window.showAppToast) {
                        const message = total
                            ? 'Saved ~' + total.toLocaleString() + ' postcodes across ' + data.boundaries.length + ' areas.'
                            : 'Service boundaries saved.';
                        window.showAppToast(message, 'success');
                    }
                })
                .catch(function (error) {
                    saveBtn.disabled = false;
                    setBoundaryStatus(error.message);
                    if (window.showAppToast) {
                        window.showAppToast(error.message, 'error');
                    }
                });
        }

        function addSquare() {
            const center = map.getCenter();
            const body = new FormData();
            body.append('lat', String(center.lat));
            body.append('lng', String(center.lng));
            body.append('csrfmiddlewaretoken', cfg.csrfToken);

            addBtn.disabled = true;
            setBoundaryStatus('Adding square…');

            fetch(cfg.boundaryCreateUrl, {
                method: 'POST',
                headers: { 'X-CSRFToken': cfg.csrfToken },
                body: body,
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        return { ok: response.ok, data: data };
                    });
                })
                .then(function ({ ok, data }) {
                    if (!ok || !data.success) {
                        throw new Error((data && data.error) || 'Could not add square');
                    }
                    const newSlug = data.boundary && data.boundary.slug;
                    loadBoundaries(data.geojson, newSlug, data.boundaries, data.stats);
                    if (newSlug && boundaryLayers[newSlug]) {
                        enableLayerEdit(boundaryLayers[newSlug].layer);
                    }
                    markDirty();
                    setBoundaryStatus((data.boundary && data.boundary.name) + ' added — drag it into place, then save all');
                })
                .catch(function (error) {
                    setBoundaryStatus(error.message);
                    if (window.showAppToast) {
                        window.showAppToast(error.message, 'error');
                    }
                })
                .finally(function () {
                    addBtn.disabled = false;
                });
        }

        function deleteBoundary(slug, name) {
            if (!window.confirm('Remove ' + name + '?')) return;

            fetch(deleteUrl(slug), {
                method: 'POST',
                headers: { 'X-CSRFToken': cfg.csrfToken },
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        return { ok: response.ok, data: data };
                    });
                })
                .then(function ({ ok, data }) {
                    if (!ok || !data.success) {
                        throw new Error((data && data.error) || 'Could not remove area');
                    }
                    loadBoundaries(data.geojson, null, data.boundaries, data.stats);
                    saveBtn.disabled = false;
                    setBoundaryStatus(name + ' removed');
                    if (window.showAppToast) {
                        window.showAppToast(name + ' removed.', 'success');
                    }
                })
                .catch(function (error) {
                    setBoundaryStatus(error.message);
                    if (window.showAppToast) {
                        window.showAppToast(error.message, 'error');
                    }
                });
        }

        addBtn.addEventListener('click', addSquare);
        editBtn.addEventListener('click', enableAllEdit);
        saveBtn.addEventListener('click', saveAllBoundaries);

        listEl && listEl.querySelectorAll('.coverage-boundary-delete-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                deleteBoundary(btn.dataset.slug, btn.dataset.name);
            });
        });

        loadBoundaries(cfg.editableBoundaries, null, null, null);
    }

    function escapeHtml(value) {
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }
})();

/**
 * TEMP: Schedule debug panel — independent of booking.js (avoids stale cache).
 */
(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        var cfg = window.bookingConfig;
        var panel = document.getElementById('scheduleDebugPanel');
        var content = document.getElementById('scheduleDebugContent');
        var status = document.getElementById('scheduleDebugStatus');
        if (!cfg || !panel || !content) return;

        var lastFetchKey = '';

        function setStatus(msg) {
            if (status) status.textContent = msg;
        }

        function escapeHtml(text) {
            if (text === null || text === undefined) return '';
            return String(text)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');
        }

        function formatDuration(minutes) {
            minutes = minutes || 60;
            if (minutes < 60) return minutes + ' mins';
            var hours = Math.floor(minutes / 60);
            var mins = minutes % 60;
            return mins ? hours + ' hr ' + mins + ' mins' : hours + ' hr';
        }

        function getPostcode() {
            var el = document.getElementById('id_postcode');
            return el ? el.value.trim() : '';
        }

        function getCity() {
            var el = document.getElementById('id_city');
            return el ? el.value.trim() : '';
        }

        function getSelectedDate() {
            var el = document.getElementById('id_date');
            return el ? el.value.trim() : '';
        }

        function getServiceIds() {
            var ids = [];
            document.querySelectorAll('#servicesInputs input[name="services"]').forEach(function (input) {
                if (input.value) ids.push(input.value);
            });
            if (!ids.length) {
                document.querySelectorAll('.service-pick.selected').forEach(function (btn) {
                    if (btn.dataset.serviceId) ids.push(btn.dataset.serviceId);
                });
            }
            return ids;
        }

        function showWaiting(html) {
            content.innerHTML = html;
            panel.hidden = false;
        }

        function renderDebug(debug, selectedTime) {
            var html = '';
            if (selectedTime) {
                html += '<p class="schedule-debug-selected"><strong>Selected time:</strong> ' + escapeHtml(selectedTime) + '</p>';
            }
            html += '<div class="schedule-debug-summary">';
            html += '<p><strong>Date:</strong> ' + escapeHtml(debug.date) + '</p>';
            html += '<p><strong>Postcode:</strong> ' + escapeHtml(debug.postcode || '—');
            if (debug.candidate_coords) {
                html += ' <span class="text-muted">(' + Number(debug.candidate_coords[0]).toFixed(4) + ', ' + Number(debug.candidate_coords[1]).toFixed(4) + ')</span>';
            }
            html += '</p>';
            html += '<p><strong>Job duration:</strong> ' + formatDuration(debug.job_duration_minutes) + '</p>';
            html += '<p><strong>Available slots:</strong> ' + debug.available_count + ' / ' + debug.total_slots + '</p>';
            html += '</div>';

            if (debug.existing_jobs && debug.existing_jobs.length) {
                html += '<h6 class="schedule-debug-subtitle">Existing jobs this day</h6><ul class="schedule-debug-jobs">';
                debug.existing_jobs.forEach(function (job) {
                    html += '<li><strong>#' + job.booking_id + '</strong> ' + escapeHtml(job.start) + '–' + escapeHtml(job.end);
                    html += ' (' + job.duration_minutes + ' min) — ' + escapeHtml(job.postcode);
                    html += '<br><small class="text-muted">' + escapeHtml(job.services) + '</small></li>';
                });
                html += '</ul>';
            } else {
                html += '<p class="text-muted small">No other jobs booked this day.</p>';
            }

            html += '<h6 class="schedule-debug-subtitle">Slot breakdown (expand each)</h6><div class="schedule-debug-slots">';
            debug.slots.forEach(function (slot) {
                var statusClass = slot.available ? 'available' : 'blocked';
                var isSelected = selectedTime && slot.time === selectedTime;
                html += '<details class="schedule-debug-slot ' + statusClass + (isSelected ? ' selected-slot' : '') + '"' + (isSelected ? ' open' : '') + '>';
                html += '<summary><span class="slot-time">' + escapeHtml(slot.time) + '</span> ';
                html += slot.available ? '<span class="badge bg-success">Available</span>' : '<span class="badge bg-danger">Blocked</span>';
                if (slot.blocked_by) html += ' <span class="text-muted small">(' + escapeHtml(slot.blocked_by) + ')</span>';
                html += '</summary><div class="slot-details">';
                if (typeof slot.explanation === 'string') {
                    html += '<p>' + escapeHtml(slot.explanation) + '</p>';
                } else if (slot.explanation && slot.explanation.checks) {
                    if (slot.explanation.job_end) {
                        html += '<p><strong>Would end:</strong> ' + escapeHtml(slot.explanation.job_end) + '</p>';
                    }
                    slot.explanation.checks.forEach(function (check) {
                        html += '<p class="check-' + check.status + '"><strong>' + (check.status === 'pass' ? '✓' : '✗') + ' ' + escapeHtml(check.rule) + ':</strong> ';
                        html += escapeHtml(check.message);
                        if (check.travel_minutes !== undefined) html += ' <em>(' + check.travel_minutes + ' min travel)</em>';
                        html += '</p>';
                    });
                }
                html += '</div></details>';
            });
            html += '</div>';

            content.innerHTML = html;
            panel.hidden = false;
            setStatus('Debug loaded ' + new Date().toLocaleTimeString());
        }

        function getSelectedTimeLabel() {
            var btn = document.querySelector('.time-slot-btn.selected');
            return btn ? btn.dataset.slotTime : '';
        }

        async function fetchDebug() {
            var postcode = getPostcode();
            var date = getSelectedDate();
            var serviceIds = getServiceIds();

            if (!postcode || postcode.length < 5) {
                setStatus('Waiting for postcode…');
                showWaiting('<p class="text-muted mb-0">Enter your postcode on step 2, then click a date.</p>');
                return;
            }

            if (!date) {
                setStatus('Postcode: ' + postcode + ' — waiting for date…');
                showWaiting('<p class="text-muted mb-0">Postcode <strong>' + escapeHtml(postcode) + '</strong> set. Click a date on the calendar.</p>');
                return;
            }

            var fetchKey = date + '|' + postcode + '|' + serviceIds.join(',');
            if (fetchKey === lastFetchKey && content.querySelector('.schedule-debug-slots')) {
                return;
            }
            lastFetchKey = fetchKey;

            setStatus('Fetching debug for ' + date + '…');
            showWaiting('<p class="text-muted mb-0">Loading travel calculations for <strong>' + escapeHtml(date) + '</strong>…</p>');

            var params = new URLSearchParams();
            params.set('date', date);
            params.set('postcode', postcode);
            params.set('debug', '1');
            if (getCity()) params.set('city', getCity());
            serviceIds.forEach(function (id) { params.append('services', id); });

            try {
                var res = await fetch(cfg.slotsUrl + '?' + params.toString(), { credentials: 'same-origin' });
                if (!res.ok) throw new Error('HTTP ' + res.status);
                var data = await res.json();
                if (data.debug) {
                    renderDebug(data.debug, getSelectedTimeLabel());
                } else if (data.debug_error) {
                    showWaiting('<p class="text-danger mb-0">Server debug error: <strong>' + escapeHtml(data.debug_error) + '</strong></p>');
                    setStatus('Server error');
                } else {
                    showWaiting('<p class="text-danger mb-0">API returned no debug data. Is SCHEDULE_DEBUG enabled on the server?</p>');
                    setStatus('No debug in response');
                }
            } catch (err) {
                showWaiting('<p class="text-danger mb-0">Failed to load debug: <strong>' + escapeHtml(err.message) + '</strong></p>');
                setStatus('Error: ' + err.message);
            }
        }

        setStatus('Debug active — v5');
        showWaiting('<p class="text-muted mb-0">Go to step 2, enter postcode, click a date. This panel updates automatically.</p>');

        var postcodeEl = document.getElementById('id_postcode');
        if (postcodeEl) {
            postcodeEl.addEventListener('input', function () {
                lastFetchKey = '';
                fetchDebug();
            });
        }

        var calGrid = document.getElementById('calGrid');
        if (calGrid) {
            calGrid.addEventListener('click', function () {
                setTimeout(fetchDebug, 300);
            });
        }

        var timeSlotsGrid = document.getElementById('timeSlotsGrid');
        if (timeSlotsGrid) {
            timeSlotsGrid.addEventListener('click', function () {
                setTimeout(fetchDebug, 100);
            });
        }

        setInterval(function () {
            var date = getSelectedDate();
            var postcode = getPostcode();
            if (date && postcode.length >= 5) {
                fetchDebug();
            }
        }, 2000);

        document.addEventListener('click', function (e) {
            if (e.target.closest('.btn-next[data-next="2"]')) {
                setTimeout(fetchDebug, 200);
            }
        });
    });
})();

(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', initBookingWizard);

    function initBookingWizard() {
        const form = document.getElementById('bookingForm');
        if (!form || !window.bookingConfig) return;

        const cfg = window.bookingConfig;
        const servicesInputs = document.getElementById('servicesInputs');
        const dateInput = document.getElementById('id_date');
        const timeInput = document.getElementById('id_time_slot');
        const postcodeInput = document.getElementById('id_postcode');
        const cityInput = document.getElementById('id_city');
        const postcodeDisplay = document.getElementById('postcodeDisplay');
        const calendarSection = document.getElementById('calendarSection');
        const panels = document.querySelectorAll('.booking-panel');
        const steps = document.querySelectorAll('.booking-step');
        const calGrid = document.getElementById('calGrid');
        const calMonthLabel = document.getElementById('calMonthLabel');
        const calPrev = document.getElementById('calPrev');
        const calNext = document.getElementById('calNext');
        const timeSlotsSection = document.getElementById('timeSlotsSection');
        const timeSlotsGrid = document.getElementById('timeSlotsGrid');
        const timeSlotsEmpty = document.getElementById('timeSlotsEmpty');
        const timeSlotsNote = document.getElementById('timeSlotsNote');
        const selectedDateLabel = document.getElementById('selectedDateLabel');
        const scheduleDebugPanel = document.getElementById('scheduleDebugPanel');
        const scheduleDebugContent = document.getElementById('scheduleDebugContent');
        const showScheduleDebug = cfg.showScheduleDebug === true;
        const addressLookupSelect = document.getElementById('addressLookupSelect');
        const addressLookupStatus = document.getElementById('addressLookupStatus');
        const addressManualToggle = document.getElementById('addressManualToggle');

        let currentStep = 1;
        let viewYear, viewMonth;
        let availableDates = new Set();
        let selectedDate = dateInput.value || '';
        let selectedTime = timeInput.value || '';
        let selectedTimeLabel = '';
        let selectedServices = {};
        let postcodeDebounce = null;
        let loadedAddresses = [];
        let addressLookupLoadedFor = '';

        const today = new Date();
        today.setHours(0, 0, 0, 0);

        initViewMonth();
        bindServicePicker();
        bindNavigation();
        bindCalendarNav();
        bindPostcodeInput();
        bindAddressLookup();
        initFromConfig();

        async function initFromConfig() {
            const ids = cfg.initialServices && cfg.initialServices.length
                ? cfg.initialServices
                : (cfg.initialService ? [cfg.initialService] : []);
            ids.forEach(function (id) {
                const btn = document.querySelector('.service-pick[data-service-id="' + id + '"]');
                if (btn) applyServiceSelection(btn, false);
            });
            syncServiceInputs();
            syncPostcodeDisplay();
            if (cfg.hasErrors) {
                goToStep(parseInt(cfg.errorStep, 10) || 1);
            }
            if (getPostcode()) {
                calendarSection.hidden = false;
                if (showScheduleDebug) {
                    showDebugWaiting('Postcode <strong>' + escapeHtml(getPostcode()) + '</strong> set. <strong>Click a date</strong> on the calendar to load travel time debug.');
                }
                await renderCalendar();
                if (selectedDate) {
                    await selectDate(selectedDate, false);
                    if (selectedTime) highlightTimeSlot(selectedTime);
                }
            }
            updateSummary();
        }

        function getPostcode() {
            return (postcodeInput && postcodeInput.value || '').trim();
        }

        function getCity() {
            return (cityInput && cityInput.value || '').trim();
        }

        function syncPostcodeDisplay() {
            if (postcodeDisplay) {
                postcodeDisplay.value = getPostcode();
            }
        }

        function bindPostcodeInput() {
            if (!postcodeInput) return;
            postcodeInput.addEventListener('input', function () {
                syncPostcodeDisplay();
                clearTimeout(postcodeDebounce);
                postcodeDebounce = setTimeout(onPostcodeChanged, 500);
            });
            postcodeInput.addEventListener('blur', onPostcodeChanged);
        }

        async function onPostcodeChanged() {
            syncPostcodeDisplay();
            resetAddressLookup();
            const postcode = getPostcode();
            if (postcode.length < 5) {
                calendarSection.hidden = true;
                timeSlotsSection.hidden = true;
                if (showScheduleDebug) showDebugWaiting('Enter a valid UK postcode (e.g. WF6 1TN) to begin.');
                return;
            }
            calendarSection.hidden = false;
            selectedDate = '';
            selectedTime = '';
            selectedTimeLabel = '';
            dateInput.value = '';
            timeInput.value = '';
            timeSlotsSection.hidden = true;
            if (showScheduleDebug) {
                showDebugWaiting('Postcode <strong>' + escapeHtml(postcode) + '</strong> set. Now <strong>click a date</strong> on the calendar to load travel time debug for each slot.');
            }
            await renderCalendar();
        }

        function resetAddressLookup() {
            loadedAddresses = [];
            addressLookupLoadedFor = '';
            if (!addressLookupSelect) return;
            addressLookupSelect.innerHTML = '<option value="">Enter your postcode on step 2 first…</option>';
            addressLookupSelect.disabled = true;
            addressLookupSelect.value = '';
            if (addressLookupStatus) addressLookupStatus.textContent = '';
            if (addressManualToggle) addressManualToggle.hidden = true;
        }

        function bindAddressLookup() {
            if (!cfg.addressLookupEnabled || !addressLookupSelect) return;
            addressLookupSelect.addEventListener('change', function () {
                if (!this.value) return;
                applySelectedAddress(this.value);
            });
            if (addressManualToggle) {
                addressManualToggle.addEventListener('click', function () {
                    addressLookupSelect.value = '';
                    const line1 = document.getElementById('id_address_line_1');
                    if (line1) line1.focus();
                });
            }
        }

        function applySelectedAddress(index) {
            const addr = loadedAddresses[parseInt(index, 10)];
            if (!addr) return;
            const line1 = document.getElementById('id_address_line_1');
            const line2 = document.getElementById('id_address_line_2');
            if (line1) line1.value = addr.line_1 || '';
            if (line2) line2.value = addr.line_2 || '';
            if (cityInput) cityInput.value = addr.city || '';
            if (postcodeInput && addr.postcode) {
                postcodeInput.value = addr.postcode;
                syncPostcodeDisplay();
            }
        }

        async function loadAddressLookup() {
            if (!cfg.addressLookupEnabled || !cfg.addressesUrl || !addressLookupSelect) return;

            const postcode = getPostcode();
            if (!postcode || postcode.length < 5) {
                resetAddressLookup();
                return;
            }
            if (addressLookupLoadedFor === postcode) return;

            addressLookupSelect.disabled = true;
            addressLookupSelect.innerHTML = '<option value="">Loading addresses…</option>';
            if (addressLookupStatus) addressLookupStatus.textContent = 'Looking up addresses for ' + postcode + '…';
            if (addressManualToggle) addressManualToggle.hidden = true;

            try {
                const params = new URLSearchParams({ postcode: postcode });
                const res = await fetch(cfg.addressesUrl + '?' + params.toString());
                if (!res.ok) throw new Error('Server returned ' + res.status);
                const data = await res.json();

                loadedAddresses = data.addresses || [];
                addressLookupLoadedFor = postcode;
                addressLookupSelect.innerHTML = '<option value="">— Select your address —</option>';
                loadedAddresses.forEach(function (addr, index) {
                    const option = document.createElement('option');
                    option.value = String(index);
                    option.textContent = addr.label;
                    addressLookupSelect.appendChild(option);
                });
                addressLookupSelect.disabled = false;

                if (addressLookupStatus) {
                    if (data.error === 'postcode_not_found') {
                        addressLookupStatus.textContent = 'No addresses found for this postcode. Enter your address manually below.';
                    } else if (loadedAddresses.length) {
                        addressLookupStatus.textContent = loadedAddresses.length + ' address(es) found — select yours from the list.';
                    } else {
                        addressLookupStatus.textContent = 'Enter your address manually below.';
                    }
                }
                if (addressManualToggle) {
                    addressManualToggle.hidden = loadedAddresses.length === 0;
                }
            } catch (err) {
                addressLookupSelect.innerHTML = '<option value="">Could not load addresses</option>';
                addressLookupSelect.disabled = true;
                if (addressLookupStatus) {
                    addressLookupStatus.textContent = 'Address lookup unavailable — enter your details manually below.';
                }
            }
        }

        function showDebugWaiting(message) {
            if (!scheduleDebugPanel || !scheduleDebugContent) return;
            scheduleDebugPanel.hidden = false;
            scheduleDebugContent.innerHTML = '<p class="text-muted mb-0">' + message + '</p>';
        }

        function buildScheduleParams() {
            const params = new URLSearchParams();
            Object.keys(selectedServices).forEach(function (id) {
                params.append('services', id);
            });
            const postcode = getPostcode();
            const city = getCity();
            if (postcode) params.set('postcode', postcode);
            if (city) params.set('city', city);
            return params;
        }

        function initViewMonth() {
            const base = selectedDate ? parseDate(selectedDate) : today;
            viewYear = base.getFullYear();
            viewMonth = base.getMonth();
        }

        function bindServicePicker() {
            document.querySelectorAll('.service-pick-exclusive').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    const group = btn.dataset.exclusiveGroup;
                    document.querySelectorAll('.service-pick[data-exclusive-group="' + group + '"]').forEach(function (b) {
                        b.classList.remove('selected');
                        delete selectedServices[b.dataset.serviceId];
                    });
                    applyServiceSelection(btn, true);
                    onServicesChanged();
                });
            });
            document.querySelectorAll('.service-pick-addon').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    const id = btn.dataset.serviceId;
                    if (btn.classList.contains('selected')) {
                        btn.classList.remove('selected');
                        delete selectedServices[id];
                    } else {
                        applyServiceSelection(btn, true);
                    }
                    onServicesChanged();
                });
            });
        }

        async function onServicesChanged() {
            if (currentStep === 2 && getPostcode()) {
                if (selectedDate) {
                    await loadTimeSlots(selectedDate);
                } else {
                    await renderCalendar();
                }
            }
        }

        function applyServiceSelection(btn, update) {
            const id = btn.dataset.serviceId;
            btn.classList.add('selected');
            selectedServices[id] = {
                name: btn.dataset.serviceName,
                price: parseFloat(btn.dataset.servicePrice),
                duration: parseInt(btn.dataset.serviceDuration, 10) || 60,
            };
            if (update) {
                syncServiceInputs();
                updateSummary();
            }
        }

        function getEstimatedDuration() {
            return Object.values(selectedServices).reduce(function (sum, s) {
                return sum + (s.duration || 60);
            }, 0);
        }

        function syncServiceInputs() {
            servicesInputs.innerHTML = '';
            Object.keys(selectedServices).forEach(function (id) {
                const input = document.createElement('input');
                input.type = 'hidden';
                input.name = 'services';
                input.value = id;
                servicesInputs.appendChild(input);
            });
        }

        function bindNavigation() {
            document.querySelectorAll('.btn-next').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    const next = parseInt(btn.dataset.next, 10);
                    if (validateStep(currentStep)) goToStep(next);
                });
            });
            document.querySelectorAll('.btn-prev').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    goToStep(parseInt(btn.dataset.prev, 10));
                });
            });
        }

        function validateStep(step) {
            if (step === 1) {
                if (Object.keys(selectedServices).length === 0) {
                    showToast('Please select at least one service.');
                    return false;
                }
            }
            if (step === 2) {
                if (!getPostcode() || getPostcode().length < 5) {
                    showToast('Please enter your postcode so we can check travel times.');
                    return false;
                }
                if (!dateInput.value) {
                    showToast('Please select a date from the calendar.');
                    return false;
                }
                if (!timeInput.value) {
                    showToast('Please select a time slot.');
                    return false;
                }
            }
            return true;
        }

        function goToStep(step) {
            currentStep = step;
            panels.forEach(function (p) {
                p.classList.toggle('active', parseInt(p.dataset.panel, 10) === step);
            });
            steps.forEach(function (s) {
                const n = parseInt(s.dataset.step, 10);
                s.classList.toggle('active', n === step);
                s.classList.toggle('completed', n < step);
            });
            if (step === 3) {
                syncPostcodeDisplay();
                loadAddressLookup();
            }
            window.scrollTo({ top: form.offsetTop - 100, behavior: 'smooth' });
        }

        function bindCalendarNav() {
            calPrev.addEventListener('click', async function () {
                viewMonth -= 1;
                if (viewMonth < 0) { viewMonth = 11; viewYear -= 1; }
                await renderCalendar();
            });
            calNext.addEventListener('click', async function () {
                viewMonth += 1;
                if (viewMonth > 11) { viewMonth = 0; viewYear += 1; }
                await renderCalendar();
            });
        }

        async function fetchAvailableDates(year, month) {
            const params = buildScheduleParams();
            params.set('year', year);
            params.set('month', month + 1);
            const res = await fetch(cfg.datesUrl + '?' + params.toString());
            const data = await res.json();
            return new Set(data.available || []);
        }

        async function renderCalendar() {
            if (!getPostcode()) return;
            calMonthLabel.textContent = new Date(viewYear, viewMonth, 1).toLocaleDateString('en-GB', {
                month: 'long', year: 'numeric'
            });
            availableDates = await fetchAvailableDates(viewYear, viewMonth);
            calGrid.innerHTML = '';

            const firstDay = new Date(viewYear, viewMonth, 1);
            const lastDay = new Date(viewYear, viewMonth + 1, 0);
            let startPad = firstDay.getDay() - 1;
            if (startPad < 0) startPad = 6;

            for (let i = 0; i < startPad; i++) calGrid.appendChild(createDayCell(null));
            for (let d = 1; d <= lastDay.getDate(); d++) {
                const date = new Date(viewYear, viewMonth, d);
                const iso = formatISO(date);
                calGrid.appendChild(createDayCell({
                    day: d,
                    iso: iso,
                    isPast: date < today,
                    isAvailable: availableDates.has(iso),
                    isSelected: iso === selectedDate,
                }));
            }
        }

        function createDayCell(opts) {
            const cell = document.createElement('button');
            cell.type = 'button';
            cell.className = 'calendar-day';
            if (!opts) {
                cell.classList.add('empty');
                cell.disabled = true;
                return cell;
            }
            cell.textContent = opts.day;
            if (opts.isPast) {
                cell.classList.add('past');
                cell.disabled = true;
            } else if (!opts.isAvailable) {
                cell.classList.add('unavailable');
                cell.disabled = true;
            } else {
                cell.classList.add('available');
                cell.addEventListener('click', function () { selectDate(opts.iso); });
            }
            if (opts.isSelected) cell.classList.add('selected');
            return cell;
        }

        async function selectDate(iso, reloadCalendar) {
            if (reloadCalendar === undefined) reloadCalendar = true;
            selectedDate = iso;
            dateInput.value = iso;
            selectedTime = '';
            selectedTimeLabel = '';
            timeInput.value = '';
            if (reloadCalendar) await renderCalendar();
            selectedDateLabel.textContent = parseDate(iso).toLocaleDateString('en-GB', {
                weekday: 'short', day: 'numeric', month: 'short'
            });
            timeSlotsSection.hidden = false;
            await loadTimeSlots(iso);
            updateSummary();
        }

        async function loadTimeSlots(iso) {
            timeSlotsGrid.innerHTML = '<span class="time-loading">Checking travel times…</span>';
            timeSlotsEmpty.hidden = true;
            timeSlotsNote.hidden = true;
            if (showScheduleDebug) {
                showDebugWaiting('Loading schedule debug for <strong>' + escapeHtml(iso) + '</strong>…');
            }
            try {
                const params = buildScheduleParams();
                params.set('date', iso);
                if (showScheduleDebug) params.set('debug', '1');
                const res = await fetch(cfg.slotsUrl + '?' + params.toString());
                if (!res.ok) {
                    throw new Error('Server returned ' + res.status);
                }
                const data = await res.json();

                if (showScheduleDebug && data.debug) {
                    renderScheduleDebug(data.debug, selectedTime);
                } else if (showScheduleDebug) {
                    showDebugWaiting('No debug data returned from server. Restart the server and ensure SCHEDULE_DEBUG is enabled.');
                }

                timeSlotsGrid.innerHTML = '';

                if (data.error === 'postcode_required') {
                    timeSlotsGrid.innerHTML = '<span class="text-muted small">Enter your postcode above to see available times.</span>';
                    return;
                }

                const duration = data.estimated_duration_minutes || getEstimatedDuration();
                if (duration) {
                    timeSlotsNote.textContent = 'Estimated job time: ' + formatDuration(duration) + '. Travel time between jobs is included automatically.';
                    timeSlotsNote.hidden = false;
                }

                if (!data.slots || !data.slots.length) {
                    timeSlotsEmpty.hidden = false;
                    return;
                }

                data.slots.forEach(function (slot) {
                    const btn = document.createElement('button');
                    btn.type = 'button';
                    btn.className = 'time-slot-btn';
                    btn.textContent = slot.time;
                    btn.dataset.slotId = slot.id;
                    btn.dataset.slotTime = slot.time;
                    btn.addEventListener('click', function () {
                        selectedTime = slot.id.toString();
                        selectedTimeLabel = slot.time;
                        timeInput.value = selectedTime;
                        timeSlotsGrid.querySelectorAll('.time-slot-btn').forEach(function (b) {
                            b.classList.toggle('selected', b === btn);
                        });
                        if (showScheduleDebug && data.debug) {
                            renderScheduleDebug(data.debug, selectedTime, slot.time);
                        }
                        updateSummary();
                    });
                    timeSlotsGrid.appendChild(btn);
                });
            } catch (e) {
                timeSlotsGrid.innerHTML = '<span class="text-danger small">Could not load times.</span>';
                if (showScheduleDebug) {
                    showDebugWaiting('Error loading schedule debug: <strong>' + escapeHtml(e.message) + '</strong>. Check you are logged in and the server is running.');
                }
            }
        }

        function formatDuration(minutes) {
            if (minutes < 60) return minutes + ' mins';
            const hours = Math.floor(minutes / 60);
            const mins = minutes % 60;
            return mins ? hours + ' hr ' + mins + ' mins' : hours + ' hr';
        }

        function renderScheduleDebug(debug, selectedSlotId, selectedSlotTime) {
            if (!scheduleDebugPanel || !scheduleDebugContent) return;

            try {
            let html = '';
            if (selectedSlotTime) {
                html += '<p class="schedule-debug-selected"><strong>Selected time:</strong> ' + escapeHtml(selectedSlotTime) + '</p>';
            }
            html += '<div class="schedule-debug-summary">';
            html += '<p><strong>Date:</strong> ' + escapeHtml(debug.date) + '</p>';
            html += '<p><strong>Postcode:</strong> ' + escapeHtml(debug.postcode || '—');
            if (debug.candidate_coords) {
                html += ' <span class="text-muted">(' + Number(debug.candidate_coords[0]).toFixed(4) + ', ' + Number(debug.candidate_coords[1]).toFixed(4) + ')</span>';
            }
            html += '</p>';
            html += '<p><strong>Job duration:</strong> ' + formatDuration(debug.job_duration_minutes || 60) + '</p>';
            html += '<p><strong>Available slots:</strong> ' + debug.available_count + ' / ' + debug.total_slots + '</p>';
            html += '</div>';

            if (debug.existing_jobs && debug.existing_jobs.length) {
                html += '<h6 class="schedule-debug-subtitle">Existing jobs this day</h6><ul class="schedule-debug-jobs">';
                debug.existing_jobs.forEach(function (job) {
                    html += '<li>';
                    html += '<strong>#' + job.booking_id + '</strong> ' + escapeHtml(job.start) + '–' + escapeHtml(job.end);
                    html += ' (' + job.duration_minutes + ' min) — ' + escapeHtml(job.postcode);
                    html += '<br><small class="text-muted">' + escapeHtml(job.services) + '</small>';
                    if (job.coords) {
                        html += '<br><small class="text-muted">Coords: ' + Number(job.coords[0]).toFixed(4) + ', ' + Number(job.coords[1]).toFixed(4) + '</small>';
                    }
                    html += '</li>';
                });
                html += '</ul>';
            } else {
                html += '<p class="text-muted small">No other jobs booked this day.</p>';
            }

            html += '<h6 class="schedule-debug-subtitle">Slot breakdown</h6>';
            html += '<div class="schedule-debug-slots">';
            debug.slots.forEach(function (slot) {
                const statusClass = slot.available ? 'available' : 'blocked';
                const isSelected = selectedSlotTime && slot.time === selectedSlotTime;
                html += '<details class="schedule-debug-slot ' + statusClass + (isSelected ? ' selected-slot' : '') + '"' + (isSelected ? ' open' : '') + '>';
                html += '<summary>';
                html += '<span class="slot-time">' + escapeHtml(slot.time) + '</span> ';
                html += slot.available
                    ? '<span class="badge bg-success">Available</span>'
                    : '<span class="badge bg-danger">Blocked</span>';
                if (slot.blocked_by) {
                    html += ' <span class="text-muted small">(' + escapeHtml(slot.blocked_by) + ')</span>';
                }
                html += '</summary><div class="slot-details">';

                if (typeof slot.explanation === 'string') {
                    html += '<p>' + escapeHtml(slot.explanation) + '</p>';
                } else if (slot.explanation && slot.explanation.checks) {
                    if (slot.explanation.job_end) {
                        html += '<p><strong>Would end:</strong> ' + escapeHtml(slot.explanation.job_end) + '</p>';
                    }
                    slot.explanation.checks.forEach(function (check) {
                        const icon = check.status === 'pass' ? '✓' : '✗';
                        html += '<p class="check-' + check.status + '">';
                        html += '<strong>' + icon + ' ' + escapeHtml(check.rule) + ':</strong> ';
                        html += escapeHtml(check.message);
                        if (check.travel_minutes !== undefined) {
                            html += ' <em>(' + check.travel_minutes + ' min travel)</em>';
                        }
                        html += '</p>';
                    });
                }
                html += '</div></details>';
            });
            html += '</div>';

            scheduleDebugContent.innerHTML = html;
            scheduleDebugPanel.hidden = false;
            } catch (err) {
                scheduleDebugContent.innerHTML = '<p class="text-danger">Debug render error: ' + escapeHtml(err.message) + '</p>';
                scheduleDebugPanel.hidden = false;
            }
        }

        function escapeHtml(text) {
            if (text === null || text === undefined) return '';
            return String(text)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;');
        }

        function highlightTimeSlot(id) {
            timeSlotsGrid.querySelectorAll('.time-slot-btn').forEach(function (btn) {
                if (btn.dataset.slotId === id) {
                    btn.classList.add('selected');
                    selectedTimeLabel = btn.dataset.slotTime;
                }
            });
        }

        function updateSummary() {
            const elService = document.getElementById('summaryService');
            const elDate = document.getElementById('summaryDate');
            const elTime = document.getElementById('summaryTime');
            const elPrice = document.getElementById('summaryPrice');

            const names = Object.values(selectedServices).map(function (s) { return s.name; });
            const total = Object.values(selectedServices).reduce(function (sum, s) {
                return sum + s.price;
            }, 0);

            if (elService) elService.textContent = names.length ? names.join(', ') : '—';
            if (elPrice) elPrice.textContent = total > 0 ? '£' + total.toFixed(2) : '—';
            if (selectedDate && elDate) {
                elDate.textContent = parseDate(selectedDate).toLocaleDateString('en-GB', {
                    weekday: 'short', day: 'numeric', month: 'short', year: 'numeric'
                });
            }
            if (elTime) elTime.textContent = selectedTimeLabel || '—';
        }

        function parseDate(iso) {
            const parts = iso.split('-').map(Number);
            return new Date(parts[0], parts[1] - 1, parts[2]);
        }

        function formatISO(date) {
            return date.getFullYear() + '-' +
                String(date.getMonth() + 1).padStart(2, '0') + '-' +
                String(date.getDate()).padStart(2, '0');
        }

        function showToast(msg) {
            if (typeof showAppToast === 'function') {
                showAppToast(msg, 'warning');
            }
        }
    }
})();

(function () {
    'use strict';

    function parseDate(iso) {
        const parts = iso.split('-');
        return new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10));
    }

    function formatISO(date) {
        const y = date.getFullYear();
        const m = String(date.getMonth() + 1).padStart(2, '0');
        const d = String(date.getDate()).padStart(2, '0');
        return y + '-' + m + '-' + d;
    }

    function formatDuration(minutes) {
        if (minutes < 60) return minutes + ' mins';
        const hours = Math.floor(minutes / 60);
        const mins = minutes % 60;
        return mins ? hours + ' hr ' + mins + ' mins' : hours + ' hr';
    }

    function escapeHtml(value) {
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    window.initBookingSchedulePicker = function (cfg) {
        const dateInput = document.getElementById(cfg.dateInputId || 'id_date');
        const timeInput = document.getElementById(cfg.timeInputId || 'id_time_slot');
        const calGrid = document.getElementById('calGrid');
        const calMonthLabel = document.getElementById('calMonthLabel');
        const calPrev = document.getElementById('calPrev');
        const calNext = document.getElementById('calNext');
        const timeSlotsSection = document.getElementById('timeSlotsSection');
        const timeSlotsGrid = document.getElementById('timeSlotsGrid');
        const timeSlotsEmpty = document.getElementById('timeSlotsEmpty');
        const timeSlotsNote = document.getElementById('timeSlotsNote');
        const selectedDateLabel = document.getElementById('selectedDateLabel');
        const nextAvailableHint = document.getElementById('nextAvailableHint');
        const nextAvailableLabel = document.getElementById('nextAvailableLabel');
        const nextAvailableJump = document.getElementById('nextAvailableJump');
        const submitButton = cfg.submitButtonId
            ? document.getElementById(cfg.submitButtonId)
            : null;

        if (!dateInput || !timeInput || !calGrid) return;

        const today = new Date();
        today.setHours(0, 0, 0, 0);

        let viewYear;
        let viewMonth;
        let availableDates = new Set();
        let closedDates = new Set();
        let fullDates = new Set();
        let selectedDate = cfg.initialDate || dateInput.value || '';
        let selectedTime = cfg.initialTimeSlotId || timeInput.value || '';
        let selectedTimeLabel = '';

        initViewMonth();
        bindCalendarNav();
        updateSubmitState();

        (async function initPicker() {
            await renderCalendar();
            if (selectedDate) {
                await selectDate(selectedDate, false);
                if (selectedTime) highlightTimeSlot(selectedTime);
            }
        })();

        function initViewMonth() {
            const base = selectedDate ? parseDate(selectedDate) : today;
            viewYear = base.getFullYear();
            viewMonth = base.getMonth();
        }

        function buildScheduleParams() {
            const params = new URLSearchParams();
            (cfg.serviceIds || []).forEach(function (id) {
                params.append('services', id);
            });
            if (cfg.postcode) params.set('postcode', cfg.postcode);
            if (cfg.city) params.set('city', cfg.city);
            if (cfg.excludeBookingId) params.set('exclude_booking', cfg.excludeBookingId);
            return params;
        }

        function updateSubmitState() {
            if (!submitButton) return;
            submitButton.disabled = !(dateInput.value && timeInput.value);
        }

        function updateNextAvailableHint(isoDate) {
            if (!nextAvailableHint || !nextAvailableLabel) return;
            if (!isoDate) {
                nextAvailableHint.hidden = true;
                return;
            }
            nextAvailableLabel.textContent = parseDate(isoDate).toLocaleDateString('en-GB', {
                weekday: 'long', day: 'numeric', month: 'long',
            });
            nextAvailableHint.hidden = false;
            if (nextAvailableJump) {
                nextAvailableJump.hidden = false;
                nextAvailableJump.onclick = function () {
                    const d = parseDate(isoDate);
                    viewYear = d.getFullYear();
                    viewMonth = d.getMonth();
                    selectDate(isoDate);
                };
            }
        }

        function bindCalendarNav() {
            if (!calPrev || !calNext) return;
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

        async function fetchCalendarDates(year, month) {
            const params = buildScheduleParams();
            params.set('year', year);
            params.set('month', month + 1);
            const res = await fetch(cfg.datesUrl + '?' + params.toString());
            const data = await res.json().catch(function () { return {}; });
            return {
                available: new Set(data.available || []),
                closed: new Set(data.closed || []),
                full: new Set(data.full || []),
                nextAvailable: data.next_available || null,
            };
        }

        async function renderCalendar() {
            calMonthLabel.textContent = new Date(viewYear, viewMonth, 1).toLocaleDateString('en-GB', {
                month: 'long', year: 'numeric',
            });
            const calendarDates = await fetchCalendarDates(viewYear, viewMonth);
            availableDates = calendarDates.available;
            closedDates = calendarDates.closed;
            fullDates = calendarDates.full;
            updateNextAvailableHint(calendarDates.nextAvailable);
            calGrid.innerHTML = '';

            const firstDay = new Date(viewYear, viewMonth, 1);
            const lastDay = new Date(viewYear, viewMonth + 1, 0);
            let startPad = firstDay.getDay() - 1;
            if (startPad < 0) startPad = 6;

            for (let i = 0; i < startPad; i++) calGrid.appendChild(createDayCell(null));
            for (let d = 1; d <= lastDay.getDate(); d++) {
                const date = new Date(viewYear, viewMonth, d);
                const iso = formatISO(date);
                let dayStatus = 'available';
                if (closedDates.has(iso)) {
                    dayStatus = 'closed';
                } else if (fullDates.has(iso)) {
                    dayStatus = 'full';
                } else if (!availableDates.has(iso)) {
                    dayStatus = 'full';
                }
                calGrid.appendChild(createDayCell({
                    day: d,
                    iso: iso,
                    isPast: date < today,
                    dayStatus: dayStatus,
                    isAvailable: availableDates.has(iso),
                    isSelected: iso === selectedDate,
                }));
            }
        }

        function createUnavailableDayCell(cell, opts, statusClass, statusLabel, title) {
            cell.classList.add(statusClass);
            cell.disabled = true;
            cell.setAttribute('aria-label', 'Day ' + opts.day + ', ' + title);
            cell.title = title;
            const dayNum = document.createElement('span');
            dayNum.className = 'calendar-day-num';
            dayNum.textContent = opts.day;
            const status = document.createElement('span');
            status.className = 'calendar-day-status';
            status.textContent = statusLabel;
            cell.appendChild(dayNum);
            cell.appendChild(status);
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
            if (opts.isPast) {
                cell.textContent = opts.day;
                cell.classList.add('past');
                cell.disabled = true;
            } else if (opts.dayStatus === 'closed') {
                createUnavailableDayCell(cell, opts, 'closed', 'Closed', 'Closed');
            } else if (opts.dayStatus === 'full') {
                createUnavailableDayCell(cell, opts, 'fully-booked', 'Full', 'Fully booked');
            } else if (!opts.isAvailable) {
                createUnavailableDayCell(cell, opts, 'fully-booked', 'Full', 'Fully booked');
            } else {
                cell.textContent = opts.day;
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
                weekday: 'short', day: 'numeric', month: 'short',
            });
            timeSlotsSection.hidden = false;
            await loadTimeSlots(iso);
            updateSubmitState();
            if (typeof cfg.onSelectionChange === 'function') {
                cfg.onSelectionChange({ date: iso, timeSlotId: '', timeLabel: '' });
            }
        }

        async function loadTimeSlots(iso) {
            timeSlotsGrid.innerHTML = '<span class="time-loading">Checking travel times…</span>';
            timeSlotsEmpty.hidden = true;
            timeSlotsNote.hidden = true;
            try {
                const params = buildScheduleParams();
                params.set('date', iso);
                const res = await fetch(cfg.slotsUrl + '?' + params.toString());
                const data = await res.json().catch(function () { return {}; });
                if (!res.ok) throw new Error('Server returned ' + res.status);

                timeSlotsGrid.innerHTML = '';

                const duration = data.estimated_duration_minutes || cfg.estimatedDurationMinutes;
                if (duration) {
                    timeSlotsNote.textContent = 'Estimated job time: ' + formatDuration(duration) + '. Travel time between jobs is included automatically.';
                    timeSlotsNote.hidden = false;
                }

                if (!data.slots || !data.slots.length) {
                    timeSlotsEmpty.hidden = false;
                    updateSubmitState();
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
                        updateSubmitState();
                        if (typeof cfg.onSelectionChange === 'function') {
                            cfg.onSelectionChange({
                                date: selectedDate,
                                timeSlotId: selectedTime,
                                timeLabel: selectedTimeLabel,
                            });
                        }
                    });
                    timeSlotsGrid.appendChild(btn);
                });
            } catch (e) {
                timeSlotsGrid.innerHTML = '<span class="text-danger small">Could not load times.</span>';
            }
            updateSubmitState();
        }

        function highlightTimeSlot(id) {
            selectedTime = id.toString();
            timeInput.value = selectedTime;
            timeSlotsGrid.querySelectorAll('.time-slot-btn').forEach(function (btn) {
                if (btn.dataset.slotId === id) {
                    btn.classList.add('selected');
                    selectedTimeLabel = btn.dataset.slotTime;
                }
            });
            updateSubmitState();
        }

        return {
            selectDate: selectDate,
            renderCalendar: renderCalendar,
        };
    };
})();

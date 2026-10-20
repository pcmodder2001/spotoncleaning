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
        const postcodeAreaError = document.getElementById('postcodeAreaError');
        const postcodeAreaSuccess = document.getElementById('postcodeAreaSuccess');
        const cityInput = document.getElementById('id_city');
        const addressLine1Input = document.getElementById('id_address_line_1');
        const calendarSection = document.getElementById('calendarSection');
        const calendarPlaceholder = document.getElementById('calendarPlaceholder');
        const calendarActive = document.getElementById('calendarActive');
        const postcodeChip = document.getElementById('postcodeChip');
        const postcodeChipValue = document.getElementById('postcodeChipValue');
        const nextAvailableHint = document.getElementById('nextAvailableHint');
        const nextAvailableLabel = document.getElementById('nextAvailableLabel');
        const nextAvailableJump = document.getElementById('nextAvailableJump');
        const btnStep1Next = document.getElementById('btnStep1Next');
        const btnConfirmMainServices = document.getElementById('btnConfirmMainServices');
        const btnStep2Next = document.getElementById('btnStep2Next');
        const btnStep3Next = document.getElementById('btnStep3Next');
        const btnChangeMainServices = document.getElementById('btnChangeMainServices');
        const serviceMainSection = document.getElementById('serviceMainSection');
        const serviceMainSummary = document.getElementById('serviceMainSummary');
        const serviceMainSummaryText = document.getElementById('serviceMainSummaryText');
        const serviceAddonsSection = document.getElementById('serviceAddonsSection');
        const promoInput = document.getElementById('id_promo_code');
        const promoFeedback = document.getElementById('promoFeedback');
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
        const mobileBarToggle = document.getElementById('mobileBarToggle');
        const mobileBarDetails = document.getElementById('mobileBarDetails');
        const bookingMobileStepLabel = document.getElementById('bookingMobileStepLabel');
        const bookingMobileStepCount = document.getElementById('bookingMobileStepCount');
        const bookingMobileProgressFill = document.getElementById('bookingMobileProgressFill');
        const STEP_LABELS = ['Location', 'Services', 'Date & Time', 'Confirm'];
        const savedAddressSelect = document.getElementById('savedAddressSelect');
        const savedAddressSection = document.getElementById('savedAddressSection');
        const acceptTermsInput = document.getElementById('id_accept_terms');
        const isGuestBooking = cfg.isGuestBooking === true;

        let currentStep = 1;
        let viewYear, viewMonth;
        let availableDates = new Set();
        let closedDates = new Set();
        let fullDates = new Set();
        let selectedDate = dateInput.value || '';
        let selectedTime = timeInput.value || '';
        let selectedTimeLabel = '';
        let selectedServices = {};
        let postcodeDebounce = null;
        let postcodeValid = false;
        let nextAvailableDate = null;
        let promoState = { valid: false, discount: 0, code: '', total: 0, auto: false, stacked: false };
        let savedAddresses = Array.isArray(cfg.savedAddresses) ? cfg.savedAddresses : [];
        let servicesPhase = 'main';

        const today = new Date();
        today.setHours(0, 0, 0, 0);

        initViewMonth();
        bindServicePicker();
        bindServiceExpand();
        bindServiceStep();
        bindNavigation();
        bindStepIndicators();
        bindGoStepLinks();
        bindCalendarNav();
        bindPostcodeInput();
        bindPromoField();
        bindMobileBar();
        bindAddressReviewFields();
        bindSavedAddresses();
        bindFormSubmit();
        applyPrefillAddress();
        initFromConfig();

        async function initFromConfig() {
            const ids = cfg.initialServices && cfg.initialServices.length
                ? cfg.initialServices
                : (cfg.initialService ? [cfg.initialService] : []);
            ids.forEach(function (id) {
                const el = document.querySelector('.service-pick[data-service-id="' + id + '"]');
                if (el) applyServiceSelection(el, false);
            });
            syncServiceInputs();
            updatePostcodeChip();
            if (hasMainServiceSelected()) {
                if (hasAddonServices()) {
                    servicesPhase = 'addons';
                }
                updateServiceStepUI();
            }
            if (cfg.hasErrors) {
                goToStep(parseInt(cfg.errorStep, 10) || 1);
            }
            if (getPostcode()) {
                await onPostcodeChanged();
                if (selectedDate) {
                    setCalendarMode(true);
                    await selectDate(selectedDate, false);
                    if (selectedTime) highlightTimeSlot(selectedTime);
                }
            } else {
                setCalendarMode(false);
            }
            await refreshAutoPromo();
            updateSummary();
            updateServiceStepUI();
            updateContinueButtons();
        }

        function applyPrefillAddress() {
            if (!cfg.prefillAddress) return;
            const prefill = cfg.prefillAddress;
            applyAddressFields(prefill, false);
            if (prefill.id && savedAddressSelect) {
                savedAddressSelect.value = String(prefill.id);
            }
        }

        function bindSavedAddresses() {
            if (!savedAddressSelect) return;
            if (!savedAddresses.length) {
                if (savedAddressSection) savedAddressSection.hidden = true;
                return;
            }
            savedAddresses.forEach(function (addr) {
                const option = document.createElement('option');
                option.value = String(addr.id);
                option.textContent = addr.label + ' — ' + addr.summary;
                if (addr.is_default) option.selected = true;
                savedAddressSelect.appendChild(option);
            });
            savedAddressSelect.addEventListener('change', function () {
                if (!this.value) return;
                const addr = savedAddresses.find(function (item) {
                    return String(item.id) === this.value;
                }, this);
                if (addr) applySavedAddress(addr);
            });

            ['id_address_line_1', 'id_address_line_2', 'id_city'].forEach(function (id) {
                const el = document.getElementById(id);
                if (el) {
                    el.addEventListener('input', function () {
                        if (savedAddressSelect.value) savedAddressSelect.value = '';
                    });
                }
            });
        }

        async function applySavedAddress(addr) {
            await applyAddressFields(addr, true);
        }

        async function applyAddressFields(addr, refreshSchedule) {
            const line1 = document.getElementById('id_address_line_1');
            const line2 = document.getElementById('id_address_line_2');
            if (line1) line1.value = addr.address_line_1 || '';
            if (line2) line2.value = addr.address_line_2 || '';
            if (cityInput) cityInput.value = addr.city || '';
            const previousPostcode = getPostcode();
            if (postcodeInput && addr.postcode) {
                postcodeInput.value = addr.postcode;
                updatePostcodeChip();
            }
            let propertyInput = document.getElementById('bookingPropertyId');
            if (addr.is_property) {
                if (!propertyInput) {
                    propertyInput = document.createElement('input');
                    propertyInput.type = 'hidden';
                    propertyInput.name = 'property_id';
                    propertyInput.id = 'bookingPropertyId';
                    form.appendChild(propertyInput);
                }
                propertyInput.value = addr.id;
            } else if (propertyInput) {
                propertyInput.value = '';
            }
            updateReviewBlock();
            updateContinueButtons();
            if (refreshSchedule && addr.postcode && (addr.postcode !== previousPostcode || addr.is_property)) {
                await onPostcodeChanged();
            } else if (refreshSchedule && addr.is_property && postcodeValid) {
                await renderCalendar();
            }
        }

        function getPostcode() {
            return (postcodeInput && postcodeInput.value || '').trim();
        }

        function getAddressLine1() {
            return (addressLine1Input && addressLine1Input.value || '').trim();
        }

        function isAddressComplete() {
            return !!getAddressLine1() && !!getCity();
        }

        function getCity() {
            return (cityInput && cityInput.value || '').trim();
        }

        function updatePostcodeChip() {
            const postcode = getPostcode();
            if (postcodeChip && postcodeChipValue) {
                if (postcode && postcodeValid) {
                    postcodeChipValue.textContent = postcode;
                    postcodeChip.hidden = false;
                } else {
                    postcodeChip.hidden = true;
                }
            }
        }

        function setCalendarMode(active) {
            if (!calendarSection) return;
            calendarSection.classList.toggle('is-placeholder', !active);
            if (calendarPlaceholder) calendarPlaceholder.hidden = active;
            if (calendarActive) calendarActive.hidden = !active;
        }

        function bindPostcodeInput() {
            if (!postcodeInput) return;
            postcodeInput.addEventListener('input', function () {
                clearPostcodeFeedback();
                updatePostcodeChip();
                postcodeValid = false;
                updateContinueButtons();
                clearTimeout(postcodeDebounce);
                postcodeDebounce = setTimeout(onPostcodeChanged, 500);
            });
            postcodeInput.addEventListener('blur', onPostcodeChanged);
        }

        function clearPostcodeFeedback() {
            if (postcodeAreaError) {
                postcodeAreaError.classList.add('d-none');
                postcodeAreaError.textContent = '';
            }
            if (postcodeAreaSuccess) {
                postcodeAreaSuccess.classList.add('d-none');
            }
        }

        function showPostcodeAreaSuccess() {
            if (postcodeAreaError) {
                postcodeAreaError.classList.add('d-none');
                postcodeAreaError.textContent = '';
            }
            if (postcodeAreaSuccess) {
                postcodeAreaSuccess.classList.remove('d-none');
            }
        }

        function showPostcodeAreaError(message) {
            if (postcodeAreaSuccess) {
                postcodeAreaSuccess.classList.add('d-none');
            }
            if (postcodeAreaError) {
                postcodeAreaError.textContent = message;
                postcodeAreaError.classList.remove('d-none');
            }
            postcodeValid = false;
            setCalendarMode(false);
            if (timeSlotsSection) timeSlotsSection.hidden = true;
            updateContinueButtons();
            updatePostcodeChip();
        }

        async function validatePostcodeServiceArea(postcode) {
            clearPostcodeFeedback();
            const params = new URLSearchParams({ postcode: postcode });
            params.set('year', String(new Date().getFullYear()));
            params.set('month', String(new Date().getMonth() + 1));
            try {
                const res = await fetch(cfg.datesUrl + '?' + params.toString());
                const data = await res.json().catch(function () { return {}; });
                if (res.status === 400 && data.error === 'outside_service_area') {
                    showPostcodeAreaError(data.message || 'Sorry — we do not currently cover your postcode.');
                    return false;
                }
                if (!res.ok) {
                    clearPostcodeFeedback();
                    return false;
                }
                showPostcodeAreaSuccess();
                return true;
            } catch (err) {
                clearPostcodeFeedback();
                return false;
            }
        }

        async function onPostcodeChanged() {
            updatePostcodeChip();
            const postcode = getPostcode();
            if (postcode.length < 5) {
                clearPostcodeFeedback();
                postcodeValid = false;
                setCalendarMode(false);
                if (timeSlotsSection) timeSlotsSection.hidden = true;
                updateNextAvailableHint(null);
                if (showScheduleDebug) showDebugWaiting('Enter a valid UK postcode (e.g. WF6 1TN) to begin.');
                updateContinueButtons();
                return;
            }
            const inArea = await validatePostcodeServiceArea(postcode);
            if (!inArea) return;

            postcodeValid = true;
            setCalendarMode(true);
            selectedDate = '';
            selectedTime = '';
            selectedTimeLabel = '';
            dateInput.value = '';
            timeInput.value = '';
            if (timeSlotsSection) timeSlotsSection.hidden = true;
            if (showScheduleDebug) {
                showDebugWaiting('Postcode <strong>' + escapeHtml(postcode) + '</strong> set. Now <strong>click a date</strong> on the calendar.');
            }
            await renderCalendar();
            updateContinueButtons();
            updatePostcodeChip();
        }

        function updateNextAvailableHint(isoDate) {
            nextAvailableDate = isoDate || null;
            if (!nextAvailableHint || !nextAvailableLabel) return;
            if (!isoDate) {
                nextAvailableHint.hidden = true;
                return;
            }
            nextAvailableLabel.textContent = parseDate(isoDate).toLocaleDateString('en-GB', {
                weekday: 'long', day: 'numeric', month: 'long'
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

        function bindAddressReviewFields() {
            ['id_address_line_1', 'id_address_line_2', 'id_city'].forEach(function (id) {
                const el = document.getElementById(id);
                if (el) {
                    el.addEventListener('input', function () {
                        updateReviewBlock();
                        updateContinueButtons();
                    });
                }
            });
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
            const guestEmail = document.getElementById('id_guest_email');
            if (guestEmail && guestEmail.value.trim()) {
                params.set('email', guestEmail.value.trim());
            }
            const joinList = document.getElementById('id_join_mailing_list');
            if (joinList && joinList.checked) {
                params.set('join_mailing_list', '1');
            }
            return params;
        }

        function initViewMonth() {
            const base = selectedDate ? parseDate(selectedDate) : today;
            viewYear = base.getFullYear();
            viewMonth = base.getMonth();
        }

        function bindServicePicker() {
            document.querySelectorAll('.service-pick').forEach(function (el) {
                el.addEventListener('click', function (ev) {
                    if (ev.target.closest('.service-pick-more')) return;
                    if (el.classList.contains('service-pick-exclusive')) {
                        const group = el.dataset.exclusiveGroup;
                        document.querySelectorAll('.service-pick[data-exclusive-group="' + group + '"]').forEach(function (item) {
                            item.classList.remove('selected');
                            delete selectedServices[item.dataset.serviceId];
                        });
                        applyServiceSelection(el, false);
                    } else {
                        const id = el.dataset.serviceId;
                        if (el.classList.contains('selected')) {
                            el.classList.remove('selected');
                            delete selectedServices[id];
                        } else {
                            applyServiceSelection(el, false);
                        }
                    }
                    void onServicesChanged();
                });
                el.addEventListener('keydown', function (ev) {
                    if (ev.key === 'Enter' || ev.key === ' ') {
                        ev.preventDefault();
                        el.click();
                    }
                });
            });
        }

        function bindServiceExpand() {
            document.querySelectorAll('.service-pick-more').forEach(function (btn) {
                btn.addEventListener('click', function (ev) {
                    ev.stopPropagation();
                    const expanded = btn.getAttribute('aria-expanded') === 'true';
                    const full = btn.nextElementSibling;
                    btn.setAttribute('aria-expanded', expanded ? 'false' : 'true');
                    if (full) full.hidden = expanded;
                    btn.textContent = expanded ? "What's included" : 'Hide details';
                });
            });
        }

        async function onServicesChanged() {
            syncServiceInputs();
            if (promoInput && promoInput.value.trim()) {
                await validatePromoField();
            } else {
                await refreshAutoPromo();
            }
            updateMainServiceSummary();
            if (postcodeValid && Object.keys(selectedServices).length) {
                if (currentStep === 3 && selectedDate) {
                    await loadTimeSlots(selectedDate);
                } else {
                    await renderCalendar();
                }
            }
            updateContinueButtons();
            updateSummary();
        }

        function hasMainServiceSelected() {
            return document.querySelectorAll('.service-picker-oven .service-pick.selected').length > 0;
        }

        function hasAddonServices() {
            return serviceAddonsSection && serviceAddonsSection.querySelectorAll('.service-pick').length > 0;
        }

        function formatMoney(value) {
            const amount = Number(value);
            if (Number.isNaN(amount)) return '£0.00';
            return '£' + amount.toFixed(2);
        }

        function formatServiceLabel(name, price) {
            return name + ' (' + formatMoney(price) + ')';
        }

        function getMainServiceNames() {
            const names = [];
            document.querySelectorAll('.service-picker-oven .service-pick.selected').forEach(function (el) {
                names.push(formatServiceLabel(el.dataset.serviceName, el.dataset.servicePrice));
            });
            return names;
        }

        function updateMainServiceSummary() {
            if (!serviceMainSummaryText) return;
            const names = getMainServiceNames();
            serviceMainSummaryText.textContent = names.length ? names.join(', ') : '—';
        }

        function bindServiceStep() {
            if (btnConfirmMainServices) {
                btnConfirmMainServices.addEventListener('click', function () {
                    if (!hasMainServiceSelected()) {
                        showToast('Please select at least one service.');
                        return;
                    }
                    confirmMainServices();
                });
            }
            if (btnChangeMainServices) {
                btnChangeMainServices.addEventListener('click', showMainServicesPhase);
            }
        }

        function confirmMainServices() {
            if (!hasMainServiceSelected()) return;
            updateMainServiceSummary();
            if (!hasAddonServices()) {
                goToStep(3);
                return;
            }
            servicesPhase = 'addons';
            updateServiceStepUI();
            scrollToElement(serviceAddonsSection);
        }

        function showMainServicesPhase() {
            servicesPhase = 'main';
            updateServiceStepUI();
            scrollToElement(serviceMainSection);
        }

        function updateServiceStepUI() {
            const inAddonsPhase = servicesPhase === 'addons';
            if (serviceMainSection) serviceMainSection.hidden = inAddonsPhase;
            if (serviceMainSummary) serviceMainSummary.hidden = !inAddonsPhase;
            if (serviceAddonsSection) serviceAddonsSection.hidden = !inAddonsPhase;
            if (btnConfirmMainServices) {
                btnConfirmMainServices.hidden = inAddonsPhase;
                btnConfirmMainServices.textContent = hasAddonServices()
                    ? 'Continue to add-ons'
                    : 'Continue';
            }
            if (btnStep2Next) btnStep2Next.hidden = !inAddonsPhase;
            if (inAddonsPhase) updateMainServiceSummary();
            updateContinueButtons();
        }

        function isServicesStepComplete() {
            if (!hasMainServiceSelected()) return false;
            if (hasAddonServices() && servicesPhase === 'main') return false;
            return true;
        }

        function applyServiceSelection(el, update) {
            const id = el.dataset.serviceId;
            el.classList.add('selected');
            selectedServices[id] = {
                name: el.dataset.serviceName,
                price: parseFloat(el.dataset.servicePrice),
                duration: parseInt(el.dataset.serviceDuration, 10) || 60,
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

        function bindStepIndicators() {
            steps.forEach(function (stepBtn) {
                stepBtn.addEventListener('click', function () {
                    const target = parseInt(stepBtn.dataset.step, 10);
                    if (target === currentStep) return;
                    if (target < currentStep) {
                        goToStep(target);
                        return;
                    }
                    for (let s = currentStep; s < target; s++) {
                        if (!validateStep(s)) return;
                    }
                    goToStep(target);
                });
            });
        }

        function bindGoStepLinks() {
            document.querySelectorAll('[data-go-step]').forEach(function (link) {
                link.addEventListener('click', function () {
                    goToStep(parseInt(link.dataset.goStep, 10));
                });
            });
        }

        function bindPromoField() {
            if (!promoInput || !cfg.promoUrl) return;
            promoInput.addEventListener('blur', validatePromoField);
            promoInput.addEventListener('input', function () {
                if (!promoInput.value.trim()) {
                    validatePromoField();
                }
            });
            const joinList = document.getElementById('id_join_mailing_list');
            if (joinList) {
                joinList.addEventListener('change', validatePromoField);
            }
            const guestEmail = document.getElementById('id_guest_email');
            if (guestEmail) {
                guestEmail.addEventListener('blur', validatePromoField);
            }
        }

        async function validatePromoField() {
            if (!promoInput || !cfg.promoUrl) return;
            const code = promoInput.value.trim();
            if (!code) {
                await refreshAutoPromo();
                updateReviewBlock();
                updateSummary();
                return;
            }
            if (!Object.keys(selectedServices).length) {
                setPromoFeedback('Select at least one service first.', 'error');
                return;
            }
            try {
                const params = buildScheduleParams();
                params.set('code', code);
                const res = await fetch(cfg.promoUrl + '?' + params.toString());
                const data = await res.json().catch(function () { return {}; });
                if (data.valid) {
                    const codes = (data.promos || []).map(function (p) { return p.code; }).filter(Boolean);
                    const hasAuto = (data.promos || []).some(function (p) { return p.auto; });
                    promoState = {
                        valid: true,
                        discount: parseFloat(data.discount),
                        code: codes.length ? codes.join(' + ') : data.code,
                        total: parseFloat(data.total),
                        auto: hasAuto,
                        stacked: !!data.stacked || codes.length > 1,
                    };
                    const msg = data.message
                        || (promoState.stacked
                            ? ('Offers combined — you save £' + parseFloat(data.discount).toFixed(2))
                            : ('Code applied — you save £' + parseFloat(data.discount).toFixed(2)));
                    setPromoFeedback(msg, 'success');
                } else {
                    const errorMsg = data.error || 'Invalid promo code.';
                    await refreshAutoPromo();
                    if (promoState.valid) {
                        setPromoFeedback(errorMsg + ' Automatic discount still applied.', 'error');
                    } else {
                        setPromoFeedback(errorMsg, 'error');
                    }
                }
            } catch (err) {
                await refreshAutoPromo();
                if (promoState.valid) {
                    setPromoFeedback('Could not validate promo code. Automatic discount still applied.', 'error');
                } else {
                    setPromoFeedback('Could not validate promo code.', 'error');
                }
            }
            updateReviewBlock();
            updateSummary();
        }

        async function refreshAutoPromo() {
            if (!cfg.autoPromoUrl || !Object.keys(selectedServices).length) {
                promoState = { valid: false, discount: 0, code: '', total: 0, auto: false, stacked: false };
                setPromoFeedback('');
                return;
            }
            try {
                const params = buildScheduleParams();
                const res = await fetch(cfg.autoPromoUrl + '?' + params.toString());
                const data = await res.json().catch(function () { return {}; });
                if (data.applies) {
                    const codes = (data.promos || []).map(function (p) { return p.code; }).filter(Boolean);
                    promoState = {
                        valid: true,
                        discount: parseFloat(data.discount),
                        code: codes.length ? codes.join(' + ') : data.code,
                        total: parseFloat(data.total),
                        auto: true,
                        stacked: !!data.stacked,
                    };
                    setPromoFeedback(data.message || ('Discount applied — save £' + parseFloat(data.discount).toFixed(2)), 'success');
                } else {
                    promoState = { valid: false, discount: 0, code: '', total: 0, auto: false, stacked: false };
                    setPromoFeedback('');
                }
            } catch (err) {
                promoState = { valid: false, discount: 0, code: '', total: 0, auto: false, stacked: false };
                setPromoFeedback('');
            }
        }

        async function syncPromosForConfirmStep() {
            if (promoInput && promoInput.value.trim()) {
                await validatePromoField();
            } else {
                await refreshAutoPromo();
            }
            updateReviewBlock();
            updateSummary();
        }

        function setPromoFeedback(message, type) {
            if (!promoFeedback) return;
            promoFeedback.textContent = message || '';
            promoFeedback.className = 'small mt-1' + (type === 'success' ? ' text-success' : type === 'error' ? ' text-danger' : '');
        }

        function bindMobileBar() {
            if (!mobileBarToggle || !mobileBarDetails) return;
            mobileBarToggle.addEventListener('click', function () {
                const open = mobileBarDetails.hidden;
                mobileBarDetails.hidden = !open;
                mobileBarToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
            });
        }

        function bindFormSubmit() {
            form.addEventListener('submit', function (ev) {
                for (let step = 1; step <= 4; step++) {
                    if (!validateStep(step)) {
                        ev.preventDefault();
                        goToStep(step);
                        return;
                    }
                }
            });
        }

        function validateStep(step) {
            if (step === 1) {
                if (!getPostcode() || getPostcode().length < 5 || !postcodeValid) {
                    showToast('Please enter a postcode within our service area.');
                    return false;
                }
                if (!getAddressLine1()) {
                    showToast('Please enter your address line 1.');
                    return false;
                }
                if (!getCity()) {
                    showToast('Please enter your city.');
                    return false;
                }
            }
            if (step === 2) {
                if (!hasMainServiceSelected()) {
                    showToast('Please select at least one service.');
                    return false;
                }
                if (hasAddonServices() && servicesPhase === 'main') {
                    confirmMainServices();
                    return false;
                }
            }
            if (step === 3) {
                if (!isServicesStepComplete()) {
                    showToast('Please choose your services first.');
                    goToStep(2);
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
            if (step === 4 && isGuestBooking) {
                if (!acceptTermsInput || !acceptTermsInput.checked) {
                    showToast('Please accept the Terms & Conditions and Privacy Policy.');
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
                if (n === step) s.setAttribute('aria-current', 'step');
                else s.removeAttribute('aria-current');
            });
            updateMobileProgress(step);
            collapseMobileBarDetails();
            if (step === 2) {
                updateServiceStepUI();
            }
            if (step === 3 && postcodeValid && isServicesStepComplete()) {
                setCalendarMode(true);
                renderCalendar();
            }
            if (step === 4) {
                syncPromosForConfirmStep();
            }
            updateContinueButtons();
            scrollToWizardTop();
        }

        function updateMobileProgress(step) {
            if (bookingMobileStepLabel) {
                bookingMobileStepLabel.textContent = STEP_LABELS[step - 1] || '';
            }
            if (bookingMobileStepCount) {
                bookingMobileStepCount.textContent = step + ' / 4';
            }
            if (bookingMobileProgressFill) {
                bookingMobileProgressFill.style.width = ((step / 4) * 100) + '%';
            }
        }

        function collapseMobileBarDetails() {
            if (!mobileBarDetails || !mobileBarToggle) return;
            mobileBarDetails.hidden = true;
            mobileBarToggle.setAttribute('aria-expanded', 'false');
        }

        function getBookingScrollOffset() {
            if (window.innerWidth >= 992) return 80;
            const mobileBar = document.getElementById('bookingMobileBar');
            const footer = document.querySelector('.booking-panel.active .booking-panel-footer');
            let offset = 72;
            if (mobileBar) offset += mobileBar.offsetHeight;
            if (footer && window.getComputedStyle(footer).position === 'fixed') {
                offset += footer.offsetHeight;
            }
            return offset;
        }

        function scrollToWizardTop() {
            const wizard = document.querySelector('.booking-wizard');
            const target = wizard || form;
            const top = target.getBoundingClientRect().top + window.pageYOffset - (window.innerWidth < 992 ? 12 : 100);
            window.scrollTo({ top: Math.max(0, top), behavior: 'smooth' });
        }

        function updateContinueButtons() {
            const step1Ready = postcodeValid && isAddressComplete();
            if (btnStep1Next) btnStep1Next.disabled = !step1Ready;

            const mainSelected = hasMainServiceSelected();
            if (btnConfirmMainServices) {
                btnConfirmMainServices.disabled = !mainSelected;
            }
            if (btnStep2Next) {
                btnStep2Next.disabled = !mainSelected;
            }

            const step3Ready = isServicesStepComplete() && !!dateInput.value && !!timeInput.value;
            if (btnStep3Next) btnStep3Next.disabled = !step3Ready;
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
            if (res.status === 400 && data.error === 'outside_service_area') {
                showPostcodeAreaError(data.message || 'Sorry — we do not currently cover your postcode.');
                return { available: new Set(), closed: new Set(), full: new Set(), nextAvailable: null };
            }
            return {
                available: new Set(data.available || []),
                closed: new Set(data.closed || []),
                full: new Set(data.full || []),
                nextAvailable: data.next_available || null,
            };
        }

        async function renderCalendar() {
            if (!getPostcode() || !postcodeValid || !calGrid) return;
            calMonthLabel.textContent = new Date(viewYear, viewMonth, 1).toLocaleDateString('en-GB', {
                month: 'long', year: 'numeric'
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
                weekday: 'short', day: 'numeric', month: 'short'
            });
            timeSlotsSection.hidden = false;
            await loadTimeSlots(iso);
            updateSummary();
            updateContinueButtons();
            scrollToElement(timeSlotsSection);
        }

        function scrollToElement(el) {
            if (!el) return;
            const top = el.getBoundingClientRect().top + window.pageYOffset - getBookingScrollOffset();
            window.scrollTo({ top: Math.max(0, top), behavior: 'smooth' });
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
                const data = await res.json().catch(function () { return {}; });
                if (res.status === 400 && data.error === 'outside_service_area') {
                    showPostcodeAreaError(data.message || 'Sorry — we do not currently cover your postcode.');
                    timeSlotsGrid.innerHTML = '';
                    return;
                }
                if (!res.ok) throw new Error('Server returned ' + res.status);

                if (showScheduleDebug && data.debug) {
                    renderScheduleDebug(data.debug, selectedTime);
                } else if (showScheduleDebug) {
                    showDebugWaiting('No debug data returned from server.');
                }

                timeSlotsGrid.innerHTML = '';

                if (data.error === 'postcode_required') {
                    timeSlotsGrid.innerHTML = '<span class="text-muted small">Choose your services on step 2 to see available times.</span>';
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
                        updateContinueButtons();
                    });
                    timeSlotsGrid.appendChild(btn);
                });
            } catch (e) {
                timeSlotsGrid.innerHTML = '<span class="text-danger small">Could not load times.</span>';
                if (showScheduleDebug) {
                    showDebugWaiting('Error loading schedule debug: <strong>' + escapeHtml(e.message) + '</strong>.');
                }
            }
        }

        function formatDuration(minutes) {
            if (minutes < 60) return minutes + ' mins';
            const hours = Math.floor(minutes / 60);
            const mins = minutes % 60;
            return mins ? hours + ' hr ' + mins + ' mins' : hours + ' hr';
        }

        function formatDurationShort(minutes) {
            if (!minutes) return '—';
            if (minutes < 60) return '~' + minutes + ' mins';
            const hours = Math.floor(minutes / 60);
            const mins = minutes % 60;
            return mins ? '~' + hours + ' hr ' + mins + ' mins' : '~' + hours + ' hr';
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

        function getSubtotal() {
            return Object.values(selectedServices).reduce(function (sum, s) {
                return sum + s.price;
            }, 0);
        }

        function getDisplayTotal() {
            const subtotal = getSubtotal();
            if (promoState.valid && promoState.total > 0) return promoState.total;
            return subtotal;
        }

        function formatAddressSummary() {
            const line1 = document.getElementById('id_address_line_1');
            const line2 = document.getElementById('id_address_line_2');
            const parts = [];
            if (line1 && line1.value.trim()) parts.push(line1.value.trim());
            if (line2 && line2.value.trim()) parts.push(line2.value.trim());
            const city = getCity();
            const postcode = getPostcode();
            if (city) parts.push(city);
            if (postcode) parts.push(postcode);
            return parts.length ? parts.join(', ') : '—';
        }

        function updateReviewBlock() {
            const reviewServices = document.getElementById('reviewServices');
            const reviewDateTime = document.getElementById('reviewDateTime');
            const reviewAddress = document.getElementById('reviewAddress');
            const reviewTotal = document.getElementById('reviewTotal');
            const reviewPromoRow = document.getElementById('reviewPromoRow');
            const reviewPromo = document.getElementById('reviewPromo');

            const names = Object.values(selectedServices).map(function (s) {
                return formatServiceLabel(s.name, s.price);
            });
            if (reviewServices) reviewServices.textContent = names.length ? names.join(', ') : '—';

            let dateTime = '—';
            if (selectedDate) {
                dateTime = parseDate(selectedDate).toLocaleDateString('en-GB', {
                    weekday: 'short', day: 'numeric', month: 'short', year: 'numeric'
                });
                if (selectedTimeLabel) dateTime += ' at ' + selectedTimeLabel;
            }
            if (reviewDateTime) reviewDateTime.textContent = dateTime;
            if (reviewAddress) reviewAddress.textContent = formatAddressSummary();

            const total = getDisplayTotal();
            if (reviewTotal) reviewTotal.textContent = total > 0 ? '£' + total.toFixed(2) : '—';

            if (reviewPromoRow && reviewPromo) {
                if (promoState.valid) {
                    let label = promoState.code || 'Discount';
                    if (promoState.auto && !promoState.stacked) {
                        label += ' (automatic)';
                    } else if (promoState.stacked) {
                        label += promoState.auto ? ' (automatic)' : ' (combined)';
                    }
                    reviewPromo.textContent = label + ' (−£' + promoState.discount.toFixed(2) + ')';
                    reviewPromoRow.hidden = false;
                } else {
                    reviewPromoRow.hidden = true;
                }
            }
        }

        function updateSummary() {
            const elService = document.getElementById('summaryService');
            const elDuration = document.getElementById('summaryDuration');
            const elDate = document.getElementById('summaryDate');
            const elTime = document.getElementById('summaryTime');
            const elPrice = document.getElementById('summaryPrice');
            const summaryPromoRow = document.getElementById('summaryPromoRow');
            const summaryPromo = document.getElementById('summaryPromo');

            const names = Object.values(selectedServices).map(function (s) {
                return formatServiceLabel(s.name, s.price);
            });
            const subtotal = getSubtotal();
            const total = getDisplayTotal();
            const duration = getEstimatedDuration();

            if (elService) elService.textContent = names.length ? names.join(', ') : '—';
            if (elDuration) elDuration.textContent = formatDurationShort(duration);
            if (elPrice) elPrice.textContent = total > 0 ? '£' + total.toFixed(2) : '—';
            if (selectedDate && elDate) {
                elDate.textContent = parseDate(selectedDate).toLocaleDateString('en-GB', {
                    weekday: 'short', day: 'numeric', month: 'short', year: 'numeric'
                });
            }
            if (elTime) elTime.textContent = selectedTimeLabel || '—';

            if (summaryPromoRow && summaryPromo) {
                if (promoState.valid) {
                    summaryPromo.textContent = '−£' + promoState.discount.toFixed(2);
                    summaryPromoRow.hidden = false;
                } else {
                    summaryPromoRow.hidden = true;
                }
            }

            updateMobileBar(names, duration, total, subtotal);
            updateReviewBlock();
        }

        function updateMobileBar(names, duration, total, subtotal) {
            const mobileBarSummary = document.getElementById('mobileBarSummary');
            const mobileBarPrice = document.getElementById('mobileBarPrice');
            const mobileBarServices = document.getElementById('mobileBarServices');
            const mobileBarDuration = document.getElementById('mobileBarDuration');
            const mobileBarDate = document.getElementById('mobileBarDate');
            const mobileBarTime = document.getElementById('mobileBarTime');
            const mobileBarPromoRow = document.getElementById('mobileBarPromoRow');
            const mobileBarPromo = document.getElementById('mobileBarPromo');

            let compact = 'Enter your postcode to begin';
            if (postcodeValid && isAddressComplete()) {
                if (selectedDate && selectedTimeLabel) {
                    compact = parseDate(selectedDate).toLocaleDateString('en-GB', {
                        day: 'numeric', month: 'short'
                    }) + ' · ' + selectedTimeLabel;
                } else if (selectedDate) {
                    compact = parseDate(selectedDate).toLocaleDateString('en-GB', {
                        day: 'numeric', month: 'short'
                    });
                } else if (names.length) {
                    compact = names.length === 1 ? names[0] : names.length + ' services';
                } else {
                    compact = getPostcode() || 'Address entered';
                }
            }

            if (mobileBarSummary) mobileBarSummary.textContent = compact;
            if (mobileBarPrice) mobileBarPrice.textContent = total > 0 ? '£' + total.toFixed(2) : (subtotal > 0 ? '£' + subtotal.toFixed(2) : '—');
            if (mobileBarServices) mobileBarServices.textContent = names.length ? names.join(', ') : '—';
            if (mobileBarDuration) mobileBarDuration.textContent = formatDurationShort(duration);
            if (mobileBarDate) {
                mobileBarDate.textContent = selectedDate
                    ? parseDate(selectedDate).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })
                    : '—';
            }
            if (mobileBarTime) mobileBarTime.textContent = selectedTimeLabel || '—';
            if (mobileBarPromoRow && mobileBarPromo) {
                if (promoState.valid) {
                    mobileBarPromo.textContent = '−£' + promoState.discount.toFixed(2);
                    mobileBarPromoRow.hidden = false;
                } else {
                    mobileBarPromoRow.hidden = true;
                }
            }
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

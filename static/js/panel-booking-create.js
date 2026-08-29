(function () {
    var root = document.getElementById('adminBookingCreate');
    if (!root) return;

    var scheduleCheckUrl = root.dataset.scheduleCheckUrl;
    var form = root.querySelector('form');
    var steps = Array.prototype.slice.call(root.querySelectorAll('[data-create-step]'));
    var stepIndicators = Array.prototype.slice.call(root.querySelectorAll('[data-step-indicator]'));
    var backBtn = document.getElementById('createBookingBack');
    var nextBtn = document.getElementById('createBookingNext');
    var submitBtn = document.getElementById('createBookingSubmit');
    var scheduleStatus = document.getElementById('scheduleStatus');
    var warningsBox = document.getElementById('scheduleWarnings');
    var warningsList = document.getElementById('scheduleWarningsList');
    var scheduleClear = document.getElementById('scheduleClear');
    var schedulePending = document.getElementById('schedulePending');
    var pricingBox = document.getElementById('createBookingPricing');
    var pricingValue = document.getElementById('createBookingPricingValue');
    var servicesStepError = document.getElementById('servicesStepError');
    var scheduleStepError = document.getElementById('scheduleStepError');
    var addressStepError = document.getElementById('addressStepError');
    var checkTimer = null;
    var currentStep = parseInt(root.dataset.initialStep || '0', 10);
    var totalSteps = steps.length;

    if (isNaN(currentStep) || currentStep < 0 || currentStep >= totalSteps) {
        currentStep = 0;
    }

    function fieldValue(name) {
        var field = form.querySelector('[name="' + name + '"]');
        return field ? field.value.trim() : '';
    }

    function showStepError(errorEl, message) {
        if (!errorEl) {
            if (typeof showAppToast === 'function') {
                showAppToast(message, 'error');
            }
            return;
        }
        errorEl.textContent = message;
        errorEl.classList.remove('d-none');
    }

    function clearStepErrors() {
        [servicesStepError, scheduleStepError, addressStepError].forEach(function (el) {
            if (el) {
                el.textContent = '';
                el.classList.add('d-none');
            }
        });
    }

    function appointmentTimeValue() {
        var hour = fieldValue('appointment_hour');
        var minute = fieldValue('appointment_minute');
        if (!hour || !minute) {
            return '';
        }
        return hour + ':' + minute;
    }

    function validateStep(stepIndex) {
        clearStepErrors();

        if (stepIndex === 0) {
            var userId = fieldValue('user');
            if (!userId) {
                var missing = [];
                if (!fieldValue('guest_first_name')) missing.push('first name');
                if (!fieldValue('guest_last_name')) missing.push('last name');
                if (!fieldValue('guest_email')) missing.push('email');
                if (missing.length) {
                    showStepError(null, 'Please enter guest ' + missing.join(', ') + ' or select a customer account.');
                    return false;
                }
            }
            return true;
        }

        if (stepIndex === 1) {
            if (!form.querySelector('.admin-create-service-input:checked')) {
                showStepError(servicesStepError, 'Please select at least one service.');
                return false;
            }
            return true;
        }

        if (stepIndex === 2) {
            if (!fieldValue('date') || !appointmentTimeValue()) {
                showStepError(scheduleStepError, 'Please choose a date, hour, and minutes.');
                return false;
            }
            return true;
        }

        if (stepIndex === 3) {
            var missingAddress = [];
            if (!fieldValue('address_line_1')) missingAddress.push('address line 1');
            if (!fieldValue('city')) missingAddress.push('city');
            if (!fieldValue('postcode')) missingAddress.push('postcode');
            if (missingAddress.length) {
                showStepError(addressStepError, 'Please complete ' + missingAddress.join(', ') + '.');
                return false;
            }
            return true;
        }

        return true;
    }

    function updateStepUi() {
        steps.forEach(function (step, index) {
            var isActive = index === currentStep;
            step.hidden = !isActive;
            step.classList.toggle('is-active', isActive);
        });

        stepIndicators.forEach(function (indicator, index) {
            indicator.classList.toggle('is-active', index === currentStep);
            indicator.classList.toggle('is-complete', index < currentStep);
        });

        if (backBtn) backBtn.hidden = currentStep === 0;
        if (nextBtn) nextBtn.hidden = currentStep === totalSteps - 1;
        if (submitBtn) submitBtn.hidden = currentStep !== totalSteps - 1;

        if (currentStep === 2) {
            refreshScheduleWarnings();
        }
    }

    function goToStep(stepIndex) {
        if (stepIndex < 0 || stepIndex >= totalSteps) return;
        currentStep = stepIndex;
        updateStepUi();
        var activeStep = steps[currentStep];
        if (activeStep) {
            var focusTarget = activeStep.querySelector('input, select, textarea, button');
            if (focusTarget) focusTarget.focus();
        }
    }

    function selectedServiceIds() {
        return Array.prototype.slice.call(
            form.querySelectorAll('.admin-create-service-input:checked')
        ).map(function (input) {
            return input.value;
        });
    }

    function formatMoney(amount) {
        return '£' + amount.toFixed(2);
    }

    function updatePricingPreview() {
        if (!pricingBox || !pricingValue) return;

        var total = 0;
        var count = 0;
        form.querySelectorAll('.admin-create-service-input:checked').forEach(function (input) {
            var price = parseFloat(input.dataset.price || '0');
            if (!isNaN(price)) {
                total += price;
                count += 1;
            }
        });

        if (count === 0) {
            pricingBox.hidden = true;
            return;
        }

        pricingValue.textContent = formatMoney(total);
        pricingBox.hidden = false;
    }

    function syncServicePickVisual(pick) {
        var input = pick.querySelector('.admin-create-service-input');
        if (!input) return;
        pick.classList.toggle('selected', input.checked);
    }

    function initServicePicks() {
        form.querySelectorAll('.admin-create-service-input').forEach(function (input) {
            input.addEventListener('change', function () {
                if (input.classList.contains('admin-service-oven') && input.checked) {
                    form.querySelectorAll('.admin-service-oven').forEach(function (other) {
                        if (other !== input) {
                            other.checked = false;
                            syncServicePickVisual(other.closest('.admin-create-service-pick'));
                        }
                    });
                }

                syncServicePickVisual(input.closest('.admin-create-service-pick'));
                updatePricingPreview();
                if (servicesStepError) {
                    servicesStepError.classList.add('d-none');
                }
                scheduleRefresh();
            });
        });

        form.querySelectorAll('.admin-create-service-pick').forEach(syncServicePickVisual);
        updatePricingPreview();
    }

    function initGuestSection() {
        var userSelect = form.querySelector('[name="user"]');
        var guestSection = document.getElementById('guestDetailsSection');
        if (!userSelect || !guestSection) return;

        function toggleGuestSection() {
            guestSection.classList.toggle('is-collapsed', Boolean(userSelect.value));
        }

        userSelect.addEventListener('change', toggleGuestSection);
        toggleGuestSection();
    }

    function initWizardNav() {
        if (nextBtn) {
            nextBtn.addEventListener('click', function () {
                if (!validateStep(currentStep)) return;
                goToStep(currentStep + 1);
            });
        }

        if (backBtn) {
            backBtn.addEventListener('click', function () {
                clearStepErrors();
                goToStep(currentStep - 1);
            });
        }

        form.addEventListener('submit', function (event) {
            if (!validateStep(currentStep)) {
                event.preventDefault();
            }
        });
    }

    function setScheduleState(state) {
        if (!scheduleStatus) return;

        scheduleStatus.classList.remove('d-none');
        warningsBox.classList.add('d-none');
        scheduleClear.classList.add('d-none');
        schedulePending.classList.add('d-none');

        if (state === 'pending') {
            schedulePending.classList.remove('d-none');
            return;
        }

        if (state === 'warnings') {
            warningsBox.classList.remove('d-none');
            return;
        }

        if (state === 'clear') {
            scheduleClear.classList.remove('d-none');
            return;
        }

        scheduleStatus.classList.add('d-none');
    }

    function buildScheduleCheckUrl() {
        var dateInput = form.querySelector('[name="date"]');
        var timeValue = appointmentTimeValue();
        var postcodeInput = form.querySelector('[name="postcode"]');
        var cityInput = form.querySelector('[name="city"]');

        if (!dateInput || !dateInput.value || !timeValue) {
            return null;
        }

        var params = new URLSearchParams();
        params.set('date', dateInput.value);
        params.set('time', timeValue);
        if (postcodeInput && postcodeInput.value) {
            params.set('postcode', postcodeInput.value.trim());
        }
        if (cityInput && cityInput.value) {
            params.set('city', cityInput.value.trim());
        }
        selectedServiceIds().forEach(function (serviceId) {
            params.append('services', serviceId);
        });
        return scheduleCheckUrl + '?' + params.toString();
    }

    function renderWarnings(warnings) {
        if (!warningsList) return;

        warningsList.innerHTML = '';
        if (!warnings || !warnings.length) {
            setScheduleState('clear');
            return;
        }

        warnings.forEach(function (warning) {
            var item = document.createElement('li');
            item.textContent = warning;
            warningsList.appendChild(item);
        });
        setScheduleState('warnings');
    }

    function refreshScheduleWarnings() {
        var url = buildScheduleCheckUrl();
        if (!url) {
            setScheduleState('idle');
            return;
        }

        setScheduleState('pending');

        fetch(url, {
            headers: { 'Accept': 'application/json' },
            credentials: 'same-origin',
        })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error('Could not check schedule conflicts.');
                }
                return response.json();
            })
            .then(function (data) {
                renderWarnings(data.warnings || []);
            })
            .catch(function () {
                warningsList.innerHTML = '';
                var item = document.createElement('li');
                item.textContent = 'Could not check schedule conflicts right now.';
                warningsList.appendChild(item);
                setScheduleState('warnings');
            });
    }

    function scheduleRefresh() {
        window.clearTimeout(checkTimer);
        checkTimer = window.setTimeout(refreshScheduleWarnings, 300);
    }

    ['change', 'input'].forEach(function (eventName) {
        form.addEventListener(eventName, function (event) {
            var target = event.target;
            if (!target || !target.name) return;
            if (
                target.name === 'date'
                || target.name === 'appointment_hour'
                || target.name === 'appointment_minute'
                || target.name === 'postcode'
                || target.name === 'city'
            ) {
                if (scheduleStepError) scheduleStepError.classList.add('d-none');
                if (currentStep === 2) {
                    scheduleRefresh();
                }
            }
        });
    });

    initServicePicks();
    initGuestSection();
    initWizardNav();
    updateStepUi();

    var initialWarningsScript = document.getElementById('initial-schedule-warnings');
    if (initialWarningsScript && currentStep === 2) {
        try {
            renderWarnings(JSON.parse(initialWarningsScript.textContent));
        } catch (error) {
            setScheduleState('idle');
        }
    }
})();

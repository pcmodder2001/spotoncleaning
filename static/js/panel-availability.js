/**
 * Availability panel — SweetAlert helpers for block date / add slot.
 */
(function () {
    function csrfToken() {
        const panel = document.getElementById('availPanel');
        if (panel && panel.dataset.csrf) return panel.dataset.csrf;
        const input = document.querySelector('[name=csrfmiddlewaretoken]');
        return input ? input.value : '';
    }

    function postAction(fields) {
        const form = document.createElement('form');
        form.method = 'post';
        form.action = window.location.pathname;
        form.style.display = 'none';

        function addField(name, value) {
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = name;
            input.value = value;
            form.appendChild(input);
        }

        addField('csrfmiddlewaretoken', csrfToken());
        Object.keys(fields).forEach(function (key) {
            addField(key, fields[key]);
        });
        document.body.appendChild(form);
        form.submit();
    }

    function openBlockDate() {
        if (typeof Swal === 'undefined') return;

        const today = new Date();
        const iso = today.toISOString().slice(0, 10);

        Swal.fire({
            title: 'Block a date',
            html: `
                <form class="avail-swal-form text-start">
                    <div class="mb-3">
                        <label class="form-label" for="swalAvailDate">Date</label>
                        <input type="date" id="swalAvailDate" class="form-control" value="${iso}" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label" for="swalAvailType">Type</label>
                        <select id="swalAvailType" class="form-select">
                            <option value="closed">Closed (not available)</option>
                            <option value="full">Fully booked</option>
                        </select>
                    </div>
                    <div class="mb-0">
                        <label class="form-label" for="swalAvailReason">Reason (optional)</label>
                        <input type="text" id="swalAvailReason" class="form-control" placeholder="e.g. Bank holiday">
                    </div>
                </form>
            `,
            width: window.matchMedia('(max-width: 576px)').matches ? '100%' : 480,
            showCancelButton: true,
            confirmButtonText: 'Block date',
            cancelButtonText: 'Cancel',
            confirmButtonColor: '#111111',
            cancelButtonColor: '#6b6b6b',
            focusConfirm: false,
            customClass: { popup: 'avail-swal-popup' },
            preConfirm: function () {
                const date = document.getElementById('swalAvailDate').value;
                if (!date) {
                    Swal.showValidationMessage('Choose a date.');
                    return false;
                }
                return {
                    date: date,
                    closure_type: document.getElementById('swalAvailType').value,
                    reason: document.getElementById('swalAvailReason').value || '',
                };
            },
        }).then(function (result) {
            if (!result.isConfirmed || !result.value) return;
            postAction({
                action: 'block_date',
                date: result.value.date,
                closure_type: result.value.closure_type,
                reason: result.value.reason,
            });
        });
    }

    function openAddSlot() {
        if (typeof Swal === 'undefined') return;

        Swal.fire({
            title: 'Add time slot',
            html: `
                <form class="avail-swal-form text-start">
                    <label class="form-label" for="swalAvailTime">Time</label>
                    <input type="time" id="swalAvailTime" class="form-control" required>
                </form>
            `,
            width: 400,
            showCancelButton: true,
            confirmButtonText: 'Add slot',
            cancelButtonText: 'Cancel',
            confirmButtonColor: '#111111',
            cancelButtonColor: '#6b6b6b',
            focusConfirm: false,
            customClass: { popup: 'avail-swal-popup' },
            preConfirm: function () {
                const time = document.getElementById('swalAvailTime').value;
                if (!time) {
                    Swal.showValidationMessage('Choose a time.');
                    return false;
                }
                return { time: time };
            },
        }).then(function (result) {
            if (!result.isConfirmed || !result.value) return;
            postAction({
                action: 'add_slot',
                time: result.value.time,
            });
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        ['availBlockDateBtn', 'availBlockDateBtnSecondary'].forEach(function (id) {
            const btn = document.getElementById(id);
            if (btn) btn.addEventListener('click', openBlockDate);
        });
        ['availAddSlotBtn', 'availAddSlotEmptyBtn'].forEach(function (id) {
            const btn = document.getElementById(id);
            if (btn) btn.addEventListener('click', openAddSlot);
        });
    });
})();

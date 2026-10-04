/**
 * Follow-ups panel — create dialog + mark-done renew flow.
 */
(function () {
    function csrfToken() {
        const panel = document.getElementById('followupPanel');
        if (panel && panel.dataset.csrf) return panel.dataset.csrf;
        const input = document.querySelector('[name=csrfmiddlewaretoken]');
        return input ? input.value : '';
    }

    function escapeHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function createFormHtml(prefill) {
        const data = prefill || {};
        const interval = String(data.interval_months || '6');
        const options = ['3', '6', '9', '12'].map(function (value) {
            const selected = value === interval ? ' selected' : '';
            return `<option value="${value}"${selected}>${value} months</option>`;
        }).join('');

        return `
            <form id="followupCreateForm" class="followup-create-form text-start">
                <div class="row g-3">
                    <div class="col-12">
                        <label class="form-label" for="swalFollowupName">Name</label>
                        <input type="text" id="swalFollowupName" class="form-control" placeholder="Customer name" required autocomplete="name" value="${escapeHtml(data.name)}">
                    </div>
                    <div class="col-md-6">
                        <label class="form-label" for="swalFollowupPhone">Phone</label>
                        <input type="tel" id="swalFollowupPhone" class="form-control" placeholder="07..." autocomplete="tel" value="${escapeHtml(data.phone)}">
                    </div>
                    <div class="col-md-6">
                        <label class="form-label" for="swalFollowupEmail">Email</label>
                        <input type="email" id="swalFollowupEmail" class="form-control" placeholder="name@example.com" autocomplete="email" value="${escapeHtml(data.email)}">
                    </div>
                    <div class="col-12">
                        <label class="form-label" for="swalFollowupInterval">Come back in</label>
                        <select id="swalFollowupInterval" class="form-select" required>
                            ${options}
                        </select>
                    </div>
                    <div class="col-12">
                        <label class="form-label" for="swalFollowupNotes">Notes <span class="text-muted fw-normal">(optional)</span></label>
                        <textarea id="swalFollowupNotes" class="form-control" rows="2" placeholder="e.g. double oven, prefers mornings">${escapeHtml(data.notes)}</textarea>
                    </div>
                </div>
            </form>
        `;
    }

    function submitCreate(data) {
        const form = document.createElement('form');
        form.method = 'post';
        form.action = window.location.pathname;
        form.style.display = 'none';

        function addField(fieldName, value) {
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = fieldName;
            input.value = value;
            form.appendChild(input);
        }

        addField('csrfmiddlewaretoken', csrfToken());
        addField('action', 'add');
        addField('name', data.name);
        addField('phone', data.phone);
        addField('email', data.email);
        addField('interval_months', data.interval_months);
        addField('notes', data.notes);

        document.body.appendChild(form);
        form.submit();
    }

    function openCreateFollowup(prefill, options) {
        if (typeof Swal === 'undefined') {
            window.alert('Could not open create dialog.');
            return;
        }

        const settings = options || {};

        Swal.fire({
            title: settings.title || 'Add follow-up',
            html: createFormHtml(prefill),
            width: window.matchMedia('(max-width: 576px)').matches ? '100%' : 520,
            showCancelButton: true,
            confirmButtonText: settings.confirmButtonText || 'Add follow-up',
            cancelButtonText: 'Cancel',
            confirmButtonColor: '#354f3f',
            cancelButtonColor: '#6b7368',
            focusConfirm: false,
            customClass: {
                popup: 'followup-create-popup',
                htmlContainer: 'followup-create-html',
            },
            didOpen: function () {
                const name = document.getElementById('swalFollowupName');
                if (name) name.focus();
            },
            preConfirm: function () {
                const name = (document.getElementById('swalFollowupName').value || '').trim();
                const phone = (document.getElementById('swalFollowupPhone').value || '').trim();
                const email = (document.getElementById('swalFollowupEmail').value || '').trim();
                const interval = document.getElementById('swalFollowupInterval').value;
                const notes = (document.getElementById('swalFollowupNotes').value || '').trim();

                if (!name) {
                    Swal.showValidationMessage('Enter the customer name.');
                    return false;
                }
                if (!phone && !email) {
                    Swal.showValidationMessage('Enter a phone number or email address.');
                    return false;
                }
                if (!['3', '6', '9', '12'].includes(interval)) {
                    Swal.showValidationMessage('Choose when to come back.');
                    return false;
                }

                return {
                    name: name,
                    phone: phone,
                    email: email,
                    interval_months: interval,
                    notes: notes,
                };
            },
        }).then(function (result) {
            if (!result.isConfirmed || !result.value) {
                if (settings.reloadOnCancel) {
                    window.location.reload();
                }
                return;
            }
            submitCreate(result.value);
        });
    }

    function markDone(button) {
        if (typeof Swal === 'undefined') {
            window.alert('Could not open dialog.');
            return;
        }

        const followupId = button.dataset.followupId;
        const customerName = button.dataset.name || 'this customer';

        Swal.fire({
            title: 'Mark as done?',
            text: `Mark ${customerName} as done?`,
            icon: 'question',
            showCancelButton: true,
            confirmButtonText: 'Mark done',
            cancelButtonText: 'Cancel',
            confirmButtonColor: '#354f3f',
            cancelButtonColor: '#6b7368',
        }).then(function (result) {
            if (!result.isConfirmed) return;

            const body = new FormData();
            body.append('csrfmiddlewaretoken', csrfToken());
            body.append('action', 'done');
            body.append('followup_id', followupId);

            fetch(window.location.pathname, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                },
                body: body,
                credentials: 'same-origin',
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.success) {
                            throw new Error(data.error || 'Could not mark follow-up as done.');
                        }
                        return data;
                    });
                })
                .then(function (data) {

                    return Swal.fire({
                        title: 'Add again?',
                        text: `Do you want to add ${data.name || customerName} again for another 6 months?`,
                        icon: 'question',
                        showCancelButton: true,
                        confirmButtonText: 'Yes, add again',
                        cancelButtonText: 'No thanks',
                        confirmButtonColor: '#354f3f',
                        cancelButtonColor: '#6b7368',
                    }).then(function (renewResult) {
                        if (renewResult.isConfirmed) {
                            openCreateFollowup({
                                name: data.name || customerName,
                                phone: data.phone || '',
                                email: data.email || '',
                                notes: data.notes || '',
                                interval_months: '6',
                            }, {
                                title: 'Add again',
                                confirmButtonText: 'Add follow-up',
                                reloadOnCancel: true,
                            });
                        } else {
                            window.location.reload();
                        }
                    });
                })
                .catch(function (error) {
                    if (typeof showAppToast === 'function') {
                        showAppToast(error.message, 'error');
                    } else {
                        window.alert(error.message);
                    }
                });
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        [
            document.getElementById('followupCreateBtn'),
            document.getElementById('followupCreateEmptyBtn'),
        ].forEach(function (btn) {
            if (btn) {
                btn.addEventListener('click', function () {
                    openCreateFollowup();
                });
            }
        });

        document.querySelectorAll('.followup-mark-done-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                markDone(btn);
            });
        });
    });
})();

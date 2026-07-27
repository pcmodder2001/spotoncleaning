/**
 * Services panel — create dialog via SweetAlert2.
 */
(function () {
    function csrfToken() {
        const panel = document.getElementById('servicePanel');
        if (panel && panel.dataset.csrf) return panel.dataset.csrf;
        const input = document.querySelector('[name=csrfmiddlewaretoken]');
        return input ? input.value : '';
    }

    function createFormHtml() {
        return `
            <form id="serviceCreateForm" class="service-create-form text-start">
                <div class="row g-3">
                    <div class="col-12">
                        <label class="form-label" for="swalServiceName">Name</label>
                        <input type="text" id="swalServiceName" class="form-control" placeholder="e.g. Single Oven" required autocomplete="off">
                    </div>
                    <div class="col-12">
                        <label class="form-label" for="swalServiceDescription">Description</label>
                        <textarea id="swalServiceDescription" class="form-control" rows="3" required placeholder="What’s included"></textarea>
                    </div>
                    <div class="col-md-6">
                        <label class="form-label" for="swalServiceType">Type</label>
                        <select id="swalServiceType" class="form-select">
                            <option value="oven">Oven / main appliance</option>
                            <option value="addon">Add-on</option>
                        </select>
                    </div>
                    <div class="col-md-6">
                        <label class="form-label" for="swalServicePrice">Price (£)</label>
                        <input type="number" id="swalServicePrice" class="form-control" step="0.01" min="0" required>
                    </div>
                    <div class="col-md-6">
                        <label class="form-label" for="swalServiceDuration">Duration (minutes)</label>
                        <input type="number" id="swalServiceDuration" class="form-control" min="15" step="15" value="60" required>
                    </div>
                    <div class="col-md-6">
                        <label class="form-label" for="swalServiceSort">Sort order</label>
                        <input type="number" id="swalServiceSort" class="form-control" min="0" value="0">
                    </div>
                </div>
            </form>
        `;
    }

    function openCreateService() {
        if (typeof Swal === 'undefined') {
            window.alert('Could not open create dialog.');
            return;
        }

        Swal.fire({
            title: 'Add service',
            html: createFormHtml(),
            width: window.matchMedia('(max-width: 576px)').matches ? '100%' : 560,
            showCancelButton: true,
            confirmButtonText: 'Add service',
            cancelButtonText: 'Cancel',
            confirmButtonColor: '#354f3f',
            cancelButtonColor: '#6b7368',
            focusConfirm: false,
            customClass: {
                popup: 'service-create-popup',
                htmlContainer: 'service-create-html',
            },
            didOpen: function () {
                const name = document.getElementById('swalServiceName');
                if (name) name.focus();
            },
            preConfirm: function () {
                const name = (document.getElementById('swalServiceName').value || '').trim();
                const description = (document.getElementById('swalServiceDescription').value || '').trim();
                const price = document.getElementById('swalServicePrice').value;
                const duration = document.getElementById('swalServiceDuration').value;

                if (!name) {
                    Swal.showValidationMessage('Enter a service name.');
                    return false;
                }
                if (!description) {
                    Swal.showValidationMessage('Enter a description.');
                    return false;
                }
                if (price === '' || Number(price) < 0) {
                    Swal.showValidationMessage('Enter a valid price.');
                    return false;
                }
                if (!duration || Number(duration) < 15) {
                    Swal.showValidationMessage('Duration must be at least 15 minutes.');
                    return false;
                }

                return {
                    name: name,
                    description: description,
                    service_type: document.getElementById('swalServiceType').value,
                    price: price,
                    duration_minutes: duration,
                    sort_order: document.getElementById('swalServiceSort').value || '0',
                };
            },
        }).then(function (result) {
            if (!result.isConfirmed || !result.value) return;

            const data = result.value;
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
            addField('action', 'add');
            addField('name', data.name);
            addField('description', data.description);
            addField('service_type', data.service_type);
            addField('price', data.price);
            addField('duration_minutes', data.duration_minutes);
            addField('sort_order', data.sort_order);

            document.body.appendChild(form);
            form.submit();
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        const openers = [
            document.getElementById('serviceCreateBtn'),
            document.getElementById('serviceCreateEmptyBtn'),
        ];
        openers.forEach(function (btn) {
            if (btn) btn.addEventListener('click', openCreateService);
        });
    });
})();

/**
 * Promo codes panel — create dialog via SweetAlert2.
 */
(function () {
    function csrfToken() {
        const panel = document.getElementById('promoPanel');
        if (panel && panel.dataset.csrf) return panel.dataset.csrf;
        const input = document.querySelector('[name=csrfmiddlewaretoken]');
        return input ? input.value : '';
    }

    function createFormHtml() {
        return `
            <form id="promoCreateForm" class="promo-create-form text-start">
                <div class="row g-3">
                    <div class="col-12">
                        <label class="form-label" for="swalPromoCode">Code</label>
                        <input type="text" id="swalPromoCode" name="code" class="form-control text-uppercase" placeholder="SUMMER10" required autocomplete="off">
                    </div>
                    <div class="col-12">
                        <label class="form-label" for="swalPromoDescription">Description</label>
                        <input type="text" id="swalPromoDescription" name="description" class="form-control" placeholder="e.g. 10% off 2+ appliances" autocomplete="off">
                    </div>
                    <div class="col-md-6">
                        <label class="form-label" for="swalPromoType">Type</label>
                        <select id="swalPromoType" name="discount_type" class="form-select">
                            <option value="percent">Percentage off</option>
                            <option value="fixed">Fixed £ off</option>
                        </select>
                    </div>
                    <div class="col-md-6">
                        <label class="form-label" for="swalPromoValue">Value</label>
                        <input type="number" id="swalPromoValue" name="discount_value" class="form-control" step="0.01" min="0" required>
                    </div>
                    <div class="col-md-6">
                        <label class="form-label" for="swalPromoMaxUses">Max uses</label>
                        <input type="number" id="swalPromoMaxUses" name="max_uses" class="form-control" min="1" placeholder="Unlimited">
                    </div>
                    <div class="col-md-6">
                        <label class="form-label" for="swalPromoMinOrder">Min order (£)</label>
                        <input type="number" id="swalPromoMinOrder" name="min_order_amount" class="form-control" step="0.01" min="0" value="0">
                    </div>
                    <div class="col-md-6">
                        <label class="form-label" for="swalPromoMinAppliances">Min appliances</label>
                        <input type="number" id="swalPromoMinAppliances" name="min_appliance_count" class="form-control" min="2" placeholder="Auto promos">
                    </div>
                    <div class="col-12">
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" name="auto_apply" value="1" id="swalPromoAuto">
                            <label class="form-check-label" for="swalPromoAuto">Auto-apply when conditions are met</label>
                        </div>
                    </div>
                    <div class="col-12">
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" name="count_addons" value="1" id="swalPromoAddons">
                            <label class="form-check-label" for="swalPromoAddons">Add-ons count toward the minimum</label>
                        </div>
                    </div>
                    <div class="col-12">
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" name="stackable" value="1" id="swalPromoStackable">
                            <label class="form-check-label" for="swalPromoStackable">Can be used with other offers</label>
                        </div>
                    </div>
                </div>
            </form>
        `;
    }

    function openCreatePromo() {
        if (typeof Swal === 'undefined') {
            window.alert('Could not open create dialog.');
            return;
        }

        Swal.fire({
            title: 'Create promo code',
            html: createFormHtml(),
            width: window.matchMedia('(max-width: 576px)').matches ? '100%' : 560,
            showCancelButton: true,
            confirmButtonText: 'Create code',
            cancelButtonText: 'Cancel',
            confirmButtonColor: '#354f3f',
            cancelButtonColor: '#6b7368',
            focusConfirm: false,
            customClass: {
                popup: 'promo-create-popup',
                htmlContainer: 'promo-create-html',
            },
            didOpen: function () {
                const code = document.getElementById('swalPromoCode');
                if (code) code.focus();
            },
            preConfirm: function () {
                const code = (document.getElementById('swalPromoCode').value || '').trim();
                const value = document.getElementById('swalPromoValue').value;
                const autoApply = document.getElementById('swalPromoAuto').checked;
                const minAppliances = (document.getElementById('swalPromoMinAppliances').value || '').trim();

                if (!code) {
                    Swal.showValidationMessage('Enter a promo code.');
                    return false;
                }
                if (value === '' || Number(value) < 0) {
                    Swal.showValidationMessage('Enter a valid discount value.');
                    return false;
                }
                if (autoApply && !minAppliances) {
                    Swal.showValidationMessage('Auto promos need a minimum appliance count.');
                    return false;
                }

                return {
                    code: code,
                    description: document.getElementById('swalPromoDescription').value || '',
                    discount_type: document.getElementById('swalPromoType').value,
                    discount_value: value,
                    max_uses: document.getElementById('swalPromoMaxUses').value || '',
                    min_order_amount: document.getElementById('swalPromoMinOrder').value || '0',
                    min_appliance_count: minAppliances,
                    auto_apply: autoApply,
                    count_addons: document.getElementById('swalPromoAddons').checked,
                    stackable: document.getElementById('swalPromoStackable').checked,
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
            addField('code', data.code);
            addField('description', data.description);
            addField('discount_type', data.discount_type);
            addField('discount_value', data.discount_value);
            addField('max_uses', data.max_uses);
            addField('min_order_amount', data.min_order_amount);
            addField('min_appliance_count', data.min_appliance_count);
            if (data.auto_apply) addField('auto_apply', '1');
            if (data.count_addons) addField('count_addons', '1');
            if (data.stackable) addField('stackable', '1');

            document.body.appendChild(form);
            form.submit();
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        const openers = [
            document.getElementById('promoCreateBtn'),
            document.getElementById('promoCreateEmptyBtn'),
        ];
        openers.forEach(function (btn) {
            if (btn) btn.addEventListener('click', openCreatePromo);
        });
    });
})();

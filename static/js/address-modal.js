(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        const modalEl = document.getElementById('addressModal');
        if (!modalEl || typeof bootstrap === 'undefined') return;

        const modal = new bootstrap.Modal(modalEl);
        const cfg = window.addressModalConfig || {};
        const form = document.getElementById('addressForm');
        const formAction = document.getElementById('addressFormAction');
        const formId = document.getElementById('addressFormId');
        const modalTitle = document.getElementById('addressModalTitle');
        const formSubmit = document.getElementById('addressFormSubmit');
        const fieldIds = {
            label: 'id_label',
            line1: 'id_address_line_1',
            line2: 'id_address_line_2',
            city: 'id_city',
            postcode: 'id_postcode',
            isDefault: 'id_is_default',
        };

        function field(name) {
            return document.getElementById(fieldIds[name]);
        }

        function setAddMode() {
            if (formAction) formAction.value = 'add';
            if (formId) formId.value = '';
            if (modalTitle) modalTitle.textContent = 'Add address';
            if (formSubmit) formSubmit.textContent = 'Add address';
            if (field('label')) field('label').value = '';
            if (field('line1')) field('line1').value = '';
            if (field('line2')) field('line2').value = '';
            if (field('city')) field('city').value = '';
            if (field('postcode')) field('postcode').value = '';
            if (field('isDefault')) field('isDefault').checked = false;
        }

        function setEditMode(btn) {
            if (formAction) formAction.value = 'edit';
            if (formId) formId.value = btn.dataset.addressId || '';
            if (modalTitle) modalTitle.textContent = 'Edit address';
            if (formSubmit) formSubmit.textContent = 'Save changes';
            if (field('label')) field('label').value = btn.dataset.label || '';
            if (field('line1')) field('line1').value = btn.dataset.line1 || '';
            if (field('line2')) field('line2').value = btn.dataset.line2 || '';
            if (field('city')) field('city').value = btn.dataset.city || '';
            if (field('postcode')) field('postcode').value = btn.dataset.postcode || '';
            if (field('isDefault')) {
                field('isDefault').checked = btn.dataset.isDefault === '1';
            }
        }

        function openAddModal() {
            setAddMode();
            modal.show();
        }

        document.querySelectorAll('#openAddAddressModal, #openAddAddressModalEmpty').forEach(function (btn) {
            btn.addEventListener('click', openAddModal);
        });

        document.querySelectorAll('.address-edit-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                setEditMode(btn);
                modal.show();
            });
        });

        modalEl.addEventListener('hidden.bs.modal', function () {
            if (!cfg.showOnLoad) {
                setAddMode();
            }
        });

        if (cfg.showOnLoad) {
            if (cfg.modalAction === 'edit') {
                if (modalTitle) modalTitle.textContent = 'Edit address';
                if (formSubmit) formSubmit.textContent = 'Save changes';
            }
            modal.show();
        }
    });
})();

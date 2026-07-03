(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        const modalEl = document.getElementById('propertyModal');
        if (!modalEl || typeof bootstrap === 'undefined') return;

        const modal = new bootstrap.Modal(modalEl);
        const cfg = window.propertyModalConfig || {};
        const formAction = document.getElementById('propertyFormAction');
        const formId = document.getElementById('propertyFormId');
        const modalTitle = document.getElementById('propertyModalTitle');
        const formSubmit = document.getElementById('propertyFormSubmit');
        const fieldIds = {
            reference: 'id_reference',
            line1: 'id_address_line_1',
            line2: 'id_address_line_2',
            city: 'id_city',
            postcode: 'id_postcode',
            access: 'id_access_instructions',
            contactName: 'id_contact_name',
            contactPhone: 'id_contact_phone',
            isDefault: 'id_is_default',
        };

        function field(name) {
            return document.getElementById(fieldIds[name]);
        }

        function setAddMode() {
            if (formAction) formAction.value = 'add';
            if (formId) formId.value = '';
            if (modalTitle) modalTitle.textContent = 'Add property';
            if (formSubmit) formSubmit.textContent = 'Add property';
            Object.keys(fieldIds).forEach(function (key) {
                const el = field(key);
                if (!el) return;
                if (el.type === 'checkbox') el.checked = false;
                else el.value = '';
            });
        }

        function setEditMode(btn) {
            if (formAction) formAction.value = 'edit';
            if (formId) formId.value = btn.dataset.propertyId || '';
            if (modalTitle) modalTitle.textContent = 'Edit property';
            if (formSubmit) formSubmit.textContent = 'Save changes';
            if (field('reference')) field('reference').value = btn.dataset.reference || '';
            if (field('line1')) field('line1').value = btn.dataset.line1 || '';
            if (field('line2')) field('line2').value = btn.dataset.line2 || '';
            if (field('city')) field('city').value = btn.dataset.city || '';
            if (field('postcode')) field('postcode').value = btn.dataset.postcode || '';
            if (field('access')) field('access').value = btn.dataset.access || '';
            if (field('contactName')) field('contactName').value = btn.dataset.contactName || '';
            if (field('contactPhone')) field('contactPhone').value = btn.dataset.contactPhone || '';
            if (field('isDefault')) field('isDefault').checked = btn.dataset.isDefault === '1';
        }

        document.querySelectorAll('#openAddPropertyModal, #openAddPropertyModalEmpty').forEach(function (btn) {
            btn.addEventListener('click', function () {
                setAddMode();
                modal.show();
            });
        });

        document.querySelectorAll('.property-edit-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                setEditMode(btn);
                modal.show();
            });
        });

        if (cfg.showOnLoad) {
            if (cfg.modalAction === 'edit') {
                if (modalTitle) modalTitle.textContent = 'Edit property';
                if (formSubmit) formSubmit.textContent = 'Save changes';
            }
            modal.show();
        }
    });
})();

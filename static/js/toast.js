/**
 * SweetAlert2 toast notifications for Django messages and app-wide alerts.
 */
(function () {
    'use strict';

    function mapMessageIcon(tags) {
        const tag = (tags || '').toLowerCase();
        if (tag.includes('error') || tag.includes('danger')) return 'error';
        if (tag.includes('warning')) return 'warning';
        if (tag.includes('info')) return 'info';
        return 'success';
    }

    function getToast() {
        if (typeof Swal === 'undefined') return null;
        return Swal.mixin({
            toast: true,
            position: 'top-end',
            showConfirmButton: false,
            timer: 4500,
            timerProgressBar: true,
            customClass: {
                popup: 'app-toast',
            },
            didOpen: function (toast) {
                toast.addEventListener('mouseenter', Swal.stopTimer);
                toast.addEventListener('mouseleave', Swal.resumeTimer);
            },
        });
    }

    window.showAppToast = function (message, icon) {
        const toast = getToast();
        if (!toast || !message) return;
        toast.fire({
            icon: icon || 'info',
            title: message,
        });
    };

    window.showAppConfirm = function (options) {
        if (typeof Swal === 'undefined') {
            return Promise.resolve({ isConfirmed: window.confirm(options.text || options.title || 'Are you sure?') });
        }
        const opts = options || {};
        return Swal.fire({
            title: opts.title || 'Please confirm',
            text: opts.text || '',
            icon: opts.icon || 'warning',
            showCancelButton: true,
            confirmButtonText: opts.confirmText || 'Yes, continue',
            cancelButtonText: opts.cancelText || 'Cancel',
            confirmButtonColor: opts.danger ? '#111111' : '#111111',
            cancelButtonColor: '#64748b',
            reverseButtons: true,
            focusCancel: !!opts.danger,
            customClass: {
                popup: 'app-confirm',
            },
        });
    };

    document.addEventListener('submit', function (event) {
        const form = event.target;
        if (!form.matches || !form.matches('form[data-confirm]')) {
            return;
        }
        if (form.dataset.confirmed === 'true') {
            delete form.dataset.confirmed;
            return;
        }
        event.preventDefault();
        showAppConfirm({
            title: form.dataset.confirmTitle || 'Please confirm',
            text: form.dataset.confirm || 'Are you sure?',
            danger: form.dataset.confirmDanger === 'true',
            confirmText: form.dataset.confirmYes || undefined,
        }).then(function (result) {
            if (result.isConfirmed) {
                form.dataset.confirmed = 'true';
                if (typeof form.requestSubmit === 'function') {
                    form.requestSubmit();
                } else {
                    form.submit();
                }
            }
        });
    });

    document.addEventListener('DOMContentLoaded', function () {
        if (Array.isArray(window.djangoMessages)) {
            window.djangoMessages.forEach(function (msg) {
                showAppToast(msg.text, mapMessageIcon(msg.tags));
            });
        }
    });
})();

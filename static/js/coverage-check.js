(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        const cfg = window.coverageCheckConfig;
        if (!cfg || !cfg.checkUrl) return;

        document.querySelectorAll('.js-coverage-check-form').forEach(function (form) {
            form.addEventListener('submit', function (event) {
                event.preventDefault();
                const input = form.querySelector('input[name="postcode"], input[type="search"]');
                const button = form.querySelector('button[type="submit"]');
                const postcode = input && input.value.trim();
                if (!postcode) {
                    if (input) input.focus();
                    return;
                }

                if (button) button.disabled = true;

                fetch(cfg.checkUrl + '?postcode=' + encodeURIComponent(postcode), {
                    headers: { 'Accept': 'application/json' },
                })
                    .then(function (response) {
                        return response.json().then(function (data) {
                            return { ok: response.ok, data: data };
                        });
                    })
                    .then(function ({ ok, data }) {
                        if (!ok) {
                            throw new Error((data && data.error) || 'Could not check that postcode.');
                        }
                        showCoverageResult(data, cfg);
                    })
                    .catch(function (error) {
                        showCoverageError(error.message, cfg);
                    })
                    .finally(function () {
                        if (button) button.disabled = false;
                    });
            });
        });
    });

    function showCoverageResult(data, cfg) {
        if (typeof Swal === 'undefined') {
            window.alert(data.message || 'Coverage check complete.');
            return;
        }

        if (data.covered) {
            Swal.fire({
                icon: 'success',
                title: 'We cover your area',
                html: (
                    '<p class="mb-0">' + escapeHtml(data.message || 'Great news — we cover your postcode.') + '</p>'
                ),
                confirmButtonText: 'Book a clean',
                showCancelButton: true,
                cancelButtonText: 'Close',
                confirmButtonColor: '#111111',
                cancelButtonColor: '#64748b',
                customClass: { popup: 'coverage-check-popup' },
            }).then(function (result) {
                if (result.isConfirmed && data.book_url) {
                    window.location.href = data.book_url;
                }
            });
            return;
        }

        Swal.fire({
            icon: 'info',
            title: 'We do not cover this postcode yet',
            html: buildNotCoveredHtml(data, cfg),
            confirmButtonText: 'Contact support',
            showCancelButton: true,
            cancelButtonText: 'Close',
            confirmButtonColor: '#111111',
            cancelButtonColor: '#64748b',
            customClass: { popup: 'coverage-check-popup' },
        }).then(function (result) {
            if (result.isConfirmed) {
                if (data.contact_url) {
                    window.location.href = data.contact_url;
                } else if (cfg.contactUrl) {
                    window.location.href = cfg.contactUrl;
                }
            }
        });
    }

    function showCoverageError(message, cfg) {
        if (typeof Swal === 'undefined') {
            window.alert(message);
            return;
        }
        Swal.fire({
            icon: 'warning',
            title: 'Could not check postcode',
            text: message,
            confirmButtonText: 'OK',
            confirmButtonColor: '#111111',
        });
    }

    function buildNotCoveredHtml(data, cfg) {
        const email = data.support_email || cfg.supportEmail || '';
        const phone = data.support_phone || cfg.supportPhone || '';
        let html = '<p class="mb-3">' + escapeHtml(data.message || 'Sorry — we do not currently cover your postcode.') + '</p>';
        html += '<p class="mb-2">' + escapeHtml(data.support_message || 'Please contact our team for more information.') + '</p>';
        html += '<div class="coverage-check-support">';
        if (phone) {
            html += '<div><a href="tel:' + escapeHtml(phone.replace(/\s+/g, '')) + '"><i class="bi bi-telephone me-1"></i>' + escapeHtml(phone) + '</a></div>';
        }
        if (email) {
            html += '<div><a href="mailto:' + escapeHtml(email) + '"><i class="bi bi-envelope me-1"></i>' + escapeHtml(email) + '</a></div>';
        }
        html += '</div>';
        return html;
    }

    function escapeHtml(value) {
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }
})();

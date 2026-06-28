(function () {
  'use strict';

  const cfg = window.panelBookingConfig || {};
  const csrfToken = cfg.csrfToken || '';

  function apiUrl(path) {
    return `${cfg.apiBase || '/panel/api/bookings'}${path}`;
  }

  function getCookie(name) {
    const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
    return match ? decodeURIComponent(match[2]) : '';
  }

  function csrfHeader() {
    return csrfToken || getCookie('csrftoken');
  }

  function money(value) {
    return `£${Number(value).toFixed(2)}`;
  }

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function pricingHtml(pricing) {
    if (pricing.has_promo) {
      return `
        <div class="booking-pricing booking-pricing-promo">
          <div class="booking-pricing-row"><span>Subtotal</span><span>${money(pricing.subtotal)}</span></div>
          <div class="booking-pricing-row text-success">
            <span>Promo ${escapeHtml(pricing.promo_code)}</span>
            <span>-${money(pricing.discount)}</span>
          </div>
          <div class="booking-pricing-row booking-pricing-total">
            <span>Total</span><strong>${money(pricing.total)}</strong>
          </div>
        </div>`;
    }
    return `
      <div class="booking-pricing">
        <div class="booking-pricing-row booking-pricing-total">
          <span>Total</span><strong>${money(pricing.total)}</strong>
        </div>
      </div>`;
  }

  function servicesHtml(services) {
    if (!services.length) return '<p class="text-muted mb-0">No services</p>';
    return `<ul class="booking-service-list">${services.map(function (service) {
      return `<li>
        <span>${escapeHtml(service.name)}</span>
        <span>${money(service.price)}</span>
      </li>`;
    }).join('')}</ul>`;
  }

  function jobPhotosHtml(services) {
    const withPhotos = services.filter(function (service) {
      return service.before_photo_url || service.after_photo_url;
    });
    if (!withPhotos.length) return '';

    return `
      <div class="booking-view-section">
        <h6>Job photos</h6>
        <div class="booking-job-photos">
          ${withPhotos.map(function (service) {
            return `
              <div class="booking-job-service-photos">
                <p class="booking-job-service-name mb-2">${escapeHtml(service.name)}</p>
                <div class="booking-photo-pair">
                  ${service.before_photo_url ? `
                    <figure class="booking-photo-figure">
                      <a href="${escapeHtml(service.before_photo_url)}" target="_blank" rel="noopener">
                        <img src="${escapeHtml(service.before_photo_url)}" alt="Before — ${escapeHtml(service.name)}">
                      </a>
                      <figcaption>Before</figcaption>
                    </figure>` : `
                    <figure class="booking-photo-figure booking-photo-missing">
                      <div class="booking-photo-placeholder">No before photo</div>
                      <figcaption>Before</figcaption>
                    </figure>`}
                  ${service.after_photo_url ? `
                    <figure class="booking-photo-figure">
                      <a href="${escapeHtml(service.after_photo_url)}" target="_blank" rel="noopener">
                        <img src="${escapeHtml(service.after_photo_url)}" alt="After — ${escapeHtml(service.name)}">
                      </a>
                      <figcaption>After</figcaption>
                    </figure>` : `
                    <figure class="booking-photo-figure booking-photo-missing">
                      <div class="booking-photo-placeholder">No after photo</div>
                      <figcaption>After</figcaption>
                    </figure>`}
                </div>
              </div>`;
          }).join('')}
        </div>
      </div>`;
  }

  function signOffHtml(data) {
    if (!data.signed_by_name && !data.completion_signature) return '';

    return `
      <div class="booking-view-section">
        <h6>Customer sign-off</h6>
        ${data.signed_by_name ? `<p class="mb-2"><strong>Signed by:</strong> ${escapeHtml(data.signed_by_name)}</p>` : ''}
        ${data.completion_signature ? `
          <div class="booking-signature-wrap">
            <img src="${escapeHtml(data.completion_signature)}" alt="Customer signature" class="booking-signature-image">
          </div>` : ''}
      </div>`;
  }

  function buildViewHtml(data) {
    return `
      <div class="booking-view-modal text-start">
        <div class="booking-view-header">
          <span class="badge status-${escapeHtml(data.status)}">${escapeHtml(data.status_label)}</span>
          <span class="text-muted">${escapeHtml(data.date)} · ${escapeHtml(data.time)}</span>
        </div>

        <div class="booking-view-section">
          <h6>Customer</h6>
          <p class="mb-1"><strong>${escapeHtml(data.customer.name)}</strong></p>
          <p class="mb-1"><a href="mailto:${escapeHtml(data.customer.email)}">${escapeHtml(data.customer.email)}</a></p>
          ${data.customer.phone ? `<p class="mb-0"><a href="tel:${escapeHtml(data.customer.phone)}">${escapeHtml(data.customer.phone)}</a></p>` : ''}
        </div>

        <div class="booking-view-section">
          <h6>Address</h6>
          <p class="mb-0">${escapeHtml(data.address.full)}</p>
        </div>

        <div class="booking-view-section">
          <h6>Services</h6>
          ${servicesHtml(data.services)}
          ${pricingHtml(data.pricing)}
        </div>

        ${data.notes ? `<div class="booking-view-section"><h6>Customer notes</h6><p class="mb-0">${escapeHtml(data.notes)}</p></div>` : ''}
        ${data.access_instructions ? `<div class="booking-view-section"><h6>Access</h6><p class="mb-0">${escapeHtml(data.access_instructions)}</p></div>` : ''}

        ${data.started_at ? `<div class="booking-view-section"><h6>Job started</h6><p class="mb-0 small text-muted">${escapeHtml(new Date(data.started_at).toLocaleString())}</p></div>` : ''}
        ${data.completed_at ? `<div class="booking-view-section"><h6>Job completed</h6><p class="mb-0 small text-muted">${escapeHtml(new Date(data.completed_at).toLocaleString())}</p></div>` : ''}

        ${jobPhotosHtml(data.services)}
        ${signOffHtml(data)}

        <div class="booking-view-actions">
          ${data.can_start ? `<button type="button" class="btn btn-primary" id="bookingStartBtn">Start job</button>` : ''}
          ${data.can_complete ? `<button type="button" class="btn btn-success" id="bookingCompleteBtn">Complete job</button>` : ''}
          ${data.can_manage_services ? `<button type="button" class="btn btn-outline-secondary" id="bookingManageServicesBtn">Update services</button>` : ''}
          ${data.can_admin_edit ? `<a href="${escapeHtml(data.edit_url)}" class="btn btn-link btn-sm">Full admin edit</a>` : ''}
        </div>
      </div>`;
  }

  function fetchBooking(id) {
    return fetch(apiUrl(`/${id}/`), {
      headers: { Accept: 'application/json' },
    }).then(function (response) {
      if (!response.ok) throw new Error('Could not load booking');
      return response.json();
    });
  }

  function photoFieldsHtml(services, prefix, labelPrefix) {
    return services.map(function (service) {
      return `
        <div class="booking-photo-field">
          <label class="form-label">${labelPrefix} — ${escapeHtml(service.name)}</label>
          <input type="file" class="form-control" accept="image/*" capture="environment"
                 name="${prefix}_${service.id}" required>
        </div>`;
    }).join('');
  }

  function initSignaturePad(canvas) {
    const ctx = canvas.getContext('2d');
    ctx.strokeStyle = '#0f172a';
    ctx.lineWidth = 2;
    ctx.lineCap = 'round';
    let drawing = false;
    let hasStroke = false;

    function point(event) {
      const rect = canvas.getBoundingClientRect();
      const source = event.touches ? event.touches[0] : event;
      return {
        x: source.clientX - rect.left,
        y: source.clientY - rect.top,
      };
    }

    function start(event) {
      drawing = true;
      hasStroke = true;
      const p = point(event);
      ctx.beginPath();
      ctx.moveTo(p.x, p.y);
      event.preventDefault();
    }

    function move(event) {
      if (!drawing) return;
      const p = point(event);
      ctx.lineTo(p.x, p.y);
      ctx.stroke();
      event.preventDefault();
    }

    function end() {
      drawing = false;
    }

    canvas.addEventListener('mousedown', start);
    canvas.addEventListener('mousemove', move);
    canvas.addEventListener('mouseup', end);
    canvas.addEventListener('mouseleave', end);
    canvas.addEventListener('touchstart', start, { passive: false });
    canvas.addEventListener('touchmove', move, { passive: false });
    canvas.addEventListener('touchend', end);

    return {
      isEmpty: function () { return !hasStroke; },
      clear: function () {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        hasStroke = false;
      },
      toDataURL: function () { return canvas.toDataURL('image/png'); },
    };
  }

  function openStartJobModal(booking) {
    Swal.fire({
      title: 'Start job',
      html: `
        <p class="text-muted small">Take a <strong>before</strong> photo of each item booked.</p>
        <form id="bookingStartForm" class="text-start">
          ${photoFieldsHtml(booking.services, 'before', 'Before photo')}
        </form>`,
      width: 560,
      showCancelButton: true,
      confirmButtonText: 'Start job',
      confirmButtonColor: '#0e7490',
      focusConfirm: false,
      preConfirm: function () {
        const form = document.getElementById('bookingStartForm');
        const formData = new FormData();
        let missing = false;
        booking.services.forEach(function (service) {
          const input = form.querySelector(`[name="before_${service.id}"]`);
          if (!input || !input.files.length) missing = true;
          else formData.append(`before_${service.id}`, input.files[0]);
        });
        if (missing) {
          Swal.showValidationMessage('Please add a before photo for every service.');
          return false;
        }
        return formData;
      },
    }).then(function (result) {
      if (!result.isConfirmed) return;
      fetch(apiUrl(`/${booking.id}/start/`), {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfHeader() },
        body: result.value,
      })
        .then(function (response) { return response.json().then(function (data) { return { ok: response.ok, data: data }; }); })
        .then(function ({ ok, data }) {
          if (!ok) throw new Error(data.error || 'Could not start job');
          window.showAppToast('Job started', 'success');
          openBookingView(booking.id);
        })
        .catch(function (error) {
          window.showAppToast(error.message, 'error');
        });
    });
  }

  function openCompleteJobModal(booking) {
    Swal.fire({
      title: 'Complete job',
      html: `
        <p class="text-muted small">Add <strong>after</strong> photos and customer sign-off.</p>
        <form id="bookingCompleteForm" class="text-start">
          ${photoFieldsHtml(booking.services, 'after', 'After photo')}
          <div class="mt-3">
            <label class="form-label" for="signedByName">Customer name</label>
            <input type="text" class="form-control" id="signedByName" name="signed_by_name"
                   value="${escapeHtml(booking.customer.name)}" required>
          </div>
          <div class="mt-3">
            <label class="form-label">Customer signature</label>
            <canvas id="signatureCanvas" class="signature-canvas" width="480" height="160"></canvas>
            <button type="button" class="btn btn-sm btn-outline-secondary mt-2" id="clearSignatureBtn">Clear signature</button>
          </div>
        </form>`,
      width: 560,
      showCancelButton: true,
      confirmButtonText: 'Complete job',
      confirmButtonColor: '#059669',
      focusConfirm: false,
      didOpen: function () {
        const canvas = document.getElementById('signatureCanvas');
        const pad = initSignaturePad(canvas);
        canvas._signaturePad = pad;
        document.getElementById('clearSignatureBtn').addEventListener('click', function () {
          pad.clear();
        });
      },
      preConfirm: function () {
        const form = document.getElementById('bookingCompleteForm');
        const canvas = document.getElementById('signatureCanvas');
        const pad = canvas._signaturePad;
        const signedByName = form.querySelector('#signedByName').value.trim();
        if (!signedByName) {
          Swal.showValidationMessage('Customer name is required.');
          return false;
        }
        if (!pad || pad.isEmpty()) {
          Swal.showValidationMessage('Please capture the customer signature.');
          return false;
        }
        const formData = new FormData();
        formData.append('signed_by_name', signedByName);
        formData.append('signature', pad.toDataURL());
        let missing = false;
        booking.services.forEach(function (service) {
          const input = form.querySelector(`[name="after_${service.id}"]`);
          if (!input || !input.files.length) missing = true;
          else formData.append(`after_${service.id}`, input.files[0]);
        });
        if (missing) {
          Swal.showValidationMessage('Please add an after photo for every service.');
          return false;
        }
        return formData;
      },
    }).then(function (result) {
      if (!result.isConfirmed) return;
      fetch(apiUrl(`/${booking.id}/complete/`), {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfHeader() },
        body: result.value,
      })
        .then(function (response) { return response.json().then(function (data) { return { ok: response.ok, data: data }; }); })
        .then(function ({ ok, data }) {
          if (!ok) throw new Error(data.error || 'Could not complete job');
          window.showAppToast('Job completed', 'success');
          openBookingView(booking.id);
        })
        .catch(function (error) {
          window.showAppToast(error.message, 'error');
        });
    });
  }

  function openManageServicesModal(booking) {
    fetch('/panel/api/bookings/catalog/', { headers: { Accept: 'application/json' } })
      .then(function (response) { return response.json(); })
      .then(function (catalog) {
        const selected = new Set(booking.services.map(function (service) { return String(service.id); }));
        const ovens = catalog.services.filter(function (s) { return s.service_type === 'oven'; });
        const addons = catalog.services.filter(function (s) { return s.service_type === 'addon'; });

        function servicePickRow(service) {
          const isSelected = selected.has(String(service.id));
          const isOven = service.service_type === 'oven';
          const pickClass = service.exclusive_group ? 'service-pick-exclusive' : 'service-pick-addon';
          const icon = isOven ? 'bi-fire' : 'bi-plus-circle';
          const description = service.description
            ? `<small>${escapeHtml(service.description)}</small>`
            : `<small class="text-muted">${isOven ? 'Oven / cooker clean' : 'Optional add-on'}</small>`;

          return `
            <button type="button"
                    class="service-pick ${pickClass} panel-service-pick${isSelected ? ' selected' : ''}"
                    data-service-id="${service.id}"
                    data-exclusive-group="${escapeHtml(service.exclusive_group || '')}">
              <span class="service-pick-icon"><i class="bi ${icon}"></i></span>
              <span class="service-pick-info">
                <strong>${escapeHtml(service.name)}</strong>
                ${description}
              </span>
              <span class="service-pick-price">${money(service.price)}</span>
              <span class="panel-service-pick-tick" aria-hidden="true"><i class="bi bi-check-lg"></i></span>
            </button>`;
        }

        function serviceGroup(title, hint, services) {
          if (!services.length) return '';
          return `
            <div class="panel-service-group">
              <h3 class="service-group-title">${escapeHtml(title)}${hint ? ` <span class="text-muted fw-normal">${escapeHtml(hint)}</span>` : ''}</h3>
              <div class="service-picker">${services.map(servicePickRow).join('')}</div>
            </div>`;
        }

        Swal.fire({
          title: 'Update services',
          html: `
            <div class="panel-service-editor text-start">
              <p class="panel-service-editor-note">Tap to add or remove services. Pricing updates live — promo discounts recalculate when you save.</p>
              <div class="panel-service-editor-scroll">
                ${serviceGroup('Oven cleaning', '(select all that apply)', ovens)}
                ${serviceGroup('Add-ons', '(optional)', addons)}
              </div>
              <div class="panel-service-editor-footer">
                <div id="servicePickerPreview" class="panel-service-pricing-preview">
                  <p class="text-muted small mb-0">Select services to preview pricing.</p>
                </div>
              </div>
            </div>`,
          width: 620,
          showCancelButton: true,
          confirmButtonText: 'Save services',
          confirmButtonColor: '#0e7490',
          focusConfirm: false,
          customClass: {
            popup: 'panel-service-popup',
            htmlContainer: 'panel-service-html',
          },
          didOpen: function () {
            function preview() {
              const picks = Array.from(document.querySelectorAll('.panel-service-pick.selected')).map(function (btn) {
                return btn.dataset.serviceId;
              });
              const previewEl = document.getElementById('servicePickerPreview');
              if (!picks.length) {
                previewEl.innerHTML = '<p class="text-muted small mb-0">Select at least one service to preview pricing.</p>';
                return;
              }
              previewEl.innerHTML = '<p class="text-muted small mb-0">Calculating…</p>';
              const body = new FormData();
              picks.forEach(function (id) { body.append('service_ids', id); });
              fetch(apiUrl(`/${booking.id}/quote/`), {
                method: 'POST',
                headers: { 'X-CSRFToken': csrfHeader() },
                body: body,
              })
                .then(function (response) { return response.json(); })
                .then(function (data) {
                  if (data.pricing) {
                    previewEl.innerHTML = pricingHtml(data.pricing);
                  }
                });
            }

            document.querySelectorAll('.panel-service-pick').forEach(function (btn) {
              btn.addEventListener('click', function () {
                const group = btn.dataset.exclusiveGroup;
                if (btn.classList.contains('service-pick-exclusive') && group) {
                  document.querySelectorAll('.panel-service-pick[data-exclusive-group="' + group + '"]').forEach(function (other) {
                    other.classList.remove('selected');
                  });
                  btn.classList.add('selected');
                } else {
                  btn.classList.toggle('selected');
                }
                preview();
              });
            });
            preview();
          },
          preConfirm: function () {
            const ids = Array.from(document.querySelectorAll('.panel-service-pick.selected')).map(function (btn) {
              return btn.dataset.serviceId;
            });
            if (!ids.length) {
              Swal.showValidationMessage('Select at least one service.');
              return false;
            }
            return ids;
          },
        }).then(function (result) {
          if (!result.isConfirmed) return;
          const body = new FormData();
          result.value.forEach(function (id) { body.append('service_ids', id); });
          fetch(apiUrl(`/${booking.id}/services/`), {
            method: 'POST',
            headers: { 'X-CSRFToken': csrfHeader() },
            body: body,
          })
            .then(function (response) { return response.json().then(function (data) { return { ok: response.ok, data: data }; }); })
            .then(function ({ ok, data }) {
              if (!ok) throw new Error(data.error || 'Could not update services');
              window.showAppToast('Services updated', 'success');
              openBookingView(booking.id);
            })
            .catch(function (error) {
              window.showAppToast(error.message, 'error');
            });
        });
      });
  }

  function wireViewActions(booking) {
    document.getElementById('bookingStartBtn')?.addEventListener('click', function () {
      Swal.close();
      openStartJobModal(booking);
    });
    document.getElementById('bookingCompleteBtn')?.addEventListener('click', function () {
      Swal.close();
      openCompleteJobModal(booking);
    });
    document.getElementById('bookingManageServicesBtn')?.addEventListener('click', function () {
      Swal.close();
      openManageServicesModal(booking);
    });
  }

  window.openBookingView = function (bookingId) {
    fetchBooking(bookingId)
      .then(function (data) {
        Swal.fire({
          html: buildViewHtml(data),
          width: 640,
          showConfirmButton: false,
          showCloseButton: true,
          customClass: { popup: 'booking-view-popup' },
          didOpen: function () {
            wireViewActions(data);
          },
        });
      })
      .catch(function () {
        window.showAppToast('Could not load booking details', 'error');
      });
  };

  document.addEventListener('click', function (event) {
    const button = event.target.closest('[data-booking-view]');
    if (!button) return;
    event.preventDefault();
    openBookingView(button.dataset.bookingView);
  });
})();

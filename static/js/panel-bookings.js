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
    const discount = Number(pricing.discount);
    const subtotal = Number(pricing.subtotal);
    const total = Number(pricing.total);
    const hasDiscount = discount > 0 || pricing.has_discount;
    const discountLabel = pricing.has_promo && pricing.promo_code
      ? `Promo ${escapeHtml(pricing.promo_code)}`
      : 'Discount';

    if (hasDiscount || subtotal !== total) {
      return `
        <div class="booking-pricing booking-pricing-promo">
          <div class="booking-pricing-row"><span>Subtotal</span><span>${money(subtotal)}</span></div>
          <div class="booking-pricing-row text-success">
            <span>${discountLabel}</span>
            <span>-${money(discount)}</span>
          </div>
          <div class="booking-pricing-row booking-pricing-total">
            <span>Total</span><strong>${money(total)}</strong>
          </div>
        </div>`;
    }
    return `
      <div class="booking-pricing">
        <div class="booking-pricing-row booking-pricing-total">
          <span>Total</span><strong>${money(total)}</strong>
        </div>
      </div>`;
  }

  function discountEditorHtml(data) {
    if (!data.can_edit_discount) return '';
    const pricing = data.pricing;
    return `
      <div class="booking-discount-editor">
        <label class="form-label small mb-1" for="bookingDiscountInput">Discount</label>
        <div class="input-group input-group-sm">
          <span class="input-group-text">£</span>
          <input type="number" class="form-control" id="bookingDiscountInput"
                 min="0" max="${escapeHtml(pricing.subtotal)}" step="0.01"
                 value="${escapeHtml(pricing.discount)}" inputmode="decimal">
        </div>
        <p class="form-text mb-2">Max ${money(pricing.subtotal)} (subtotal). Saving replaces any promo code.</p>
        <button type="button" class="btn btn-sm btn-outline-primary" id="bookingSaveDiscountBtn">Save discount</button>
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
          <p class="mb-2"><strong>${escapeHtml(data.customer.name)}</strong></p>
          <p class="mb-2 text-muted small">${escapeHtml(data.customer.email)}</p>
          ${customerContactHtml(data)}
        </div>

        <div class="booking-view-section">
          <h6>Address</h6>
          <p class="mb-0">${escapeHtml(data.address.full)}</p>
        </div>

        <div class="booking-view-section">
          <h6>Services</h6>
          ${servicesHtml(data.services)}
          ${pricingHtml(data.pricing)}
          ${discountEditorHtml(data)}
        </div>

        ${data.notes ? `<div class="booking-view-section"><h6>Customer notes</h6><p class="mb-0">${escapeHtml(data.notes)}</p></div>` : ''}
        ${data.access_instructions ? `<div class="booking-view-section"><h6>Access</h6><p class="mb-0">${escapeHtml(data.access_instructions)}</p></div>` : ''}

        ${data.started_at ? `<div class="booking-view-section"><h6>Job started</h6><p class="mb-0 small text-muted">${escapeHtml(new Date(data.started_at).toLocaleString())}</p></div>` : ''}
        ${data.completed_at ? `<div class="booking-view-section"><h6>Job completed</h6><p class="mb-0 small text-muted">${escapeHtml(new Date(data.completed_at).toLocaleString())}</p></div>` : ''}

        ${jobPhotosHtml(data.services)}
        ${signOffHtml(data)}

        ${data.status === 'pending' && data.can_admin_edit ? `<p class="text-muted small mb-2">Confirm this booking before the job can be started.</p>` : ''}
        <div class="booking-view-actions">
          ${data.can_start ? `<button type="button" class="btn btn-primary booking-action-btn" id="bookingStartBtn"><i class="bi bi-play-fill me-2"></i>Start job</button>` : ''}
          ${data.can_complete ? `<button type="button" class="btn btn-success booking-action-btn" id="bookingCompleteBtn"><i class="bi bi-check-circle me-2"></i>Complete job</button>` : ''}
          ${data.can_manage_services ? `<button type="button" class="btn btn-outline-secondary booking-action-btn" id="bookingManageServicesBtn"><i class="bi bi-pencil-square me-2"></i>Update services</button>` : ''}
          ${data.can_admin_edit ? `<a href="${escapeHtml(data.edit_url)}" class="btn btn-link btn-sm w-100">Full admin edit</a>` : ''}
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

  function swalMobileClasses(extra) {
    return Object.assign({
      popup: 'panel-booking-popup',
      htmlContainer: 'panel-booking-html',
    }, extra || {});
  }

  function isMobileViewport() {
    return window.matchMedia('(max-width: 767px)').matches;
  }

  function photoFieldsHtml(services, prefix, labelPrefix) {
    return services.map(function (service) {
      return `
        <label class="booking-photo-upload">
          <span class="booking-photo-upload-label">${labelPrefix} — ${escapeHtml(service.name)}</span>
          <span class="booking-photo-upload-btn">
            <i class="bi bi-camera-fill" aria-hidden="true"></i>
            <span>Take or choose photo</span>
          </span>
          <span class="booking-photo-filename text-muted small">No photo selected</span>
          <input type="file" class="booking-photo-input" accept="image/*" capture="environment"
                 name="${prefix}_${service.id}" required>
        </label>`;
    }).join('');
  }

  function wirePhotoUploadPreviews(root) {
    root.querySelectorAll('.booking-photo-upload').forEach(function (label) {
      const input = label.querySelector('.booking-photo-input');
      const filenameEl = label.querySelector('.booking-photo-filename');
      if (!input || !filenameEl) return;
      input.addEventListener('change', function () {
        if (input.files && input.files.length) {
          filenameEl.textContent = input.files[0].name;
          label.classList.add('has-photo');
        } else {
          filenameEl.textContent = 'No photo selected';
          label.classList.remove('has-photo');
        }
      });
    });
  }

  function setupCanvasSize(canvas, cssWidth, cssHeight) {
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.floor(cssWidth * dpr);
    canvas.height = Math.floor(cssHeight * dpr);
    canvas.style.width = cssWidth + 'px';
    canvas.style.height = cssHeight + 'px';
    const ctx = canvas.getContext('2d');
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.scale(dpr, dpr);
    ctx.strokeStyle = '#0f172a';
    ctx.lineWidth = 2.5;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    return ctx;
  }

  function loadSignatureOntoCanvas(canvas, dataUrl, logicalWidth, logicalHeight) {
    if (!dataUrl) return Promise.resolve();
    return new Promise(function (resolve) {
      const img = new Image();
      img.onload = function () {
        const ctx = canvas.getContext('2d');
        const w = logicalWidth || canvas.getBoundingClientRect().width;
        const h = logicalHeight || canvas.getBoundingClientRect().height;
        ctx.clearRect(0, 0, w, h);
        ctx.drawImage(img, 0, 0, w, h);
        resolve();
      };
      img.onerror = resolve;
      img.src = dataUrl;
    });
  }

  function initSignaturePad(canvas, cssWidth, cssHeight) {
    const width = cssWidth || canvas.clientWidth || 480;
    const height = cssHeight || canvas.clientHeight || 160;
    const ctx = setupCanvasSize(canvas, width, height);
    let drawing = false;
    let hasStroke = false;

    function point(event) {
      const rect = canvas.getBoundingClientRect();
      const source = event.touches ? event.touches[0] : event;
      const scaleX = width / rect.width;
      const scaleY = height / rect.height;
      return {
        x: (source.clientX - rect.left) * scaleX,
        y: (source.clientY - rect.top) * scaleY,
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
      markSigned: function () { hasStroke = true; },
      clear: function () {
        ctx.clearRect(0, 0, width, height);
        hasStroke = false;
      },
      toDataURL: function () { return canvas.toDataURL('image/png'); },
    };
  }

  function updateSignaturePreview(previewImg, dataUrl) {
    if (!previewImg) return;
    if (!dataUrl) {
      previewImg.hidden = true;
      previewImg.removeAttribute('src');
      return;
    }
    previewImg.src = dataUrl;
    previewImg.hidden = false;
  }

  function showInlineSignaturePad(popupRoot, existingSignature, onDone) {
    if (!popupRoot) return;

    popupRoot.querySelectorAll('.signature-pad-overlay').forEach(function (el) {
      el.remove();
    });

    const overlay = document.createElement('div');
    overlay.className = 'signature-pad-overlay';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-label', 'Customer signature');
    overlay.innerHTML = `
      <div class="signature-pad-overlay-panel">
        <h3 class="signature-pad-overlay-title">Customer signature</h3>
        <p class="text-muted small mb-2">Ask the customer to sign in the box below.</p>
        <div class="signature-pad-stage">
          <canvas class="signature-canvas signature-canvas-lg signature-canvas-inline" aria-label="Signature pad"></canvas>
        </div>
        <p class="signature-pad-error text-danger small mt-2 mb-0" hidden></p>
        <button type="button" class="btn btn-outline-secondary btn-sm mt-2 signature-clear-inline-btn">Clear signature</button>
        <div class="signature-pad-overlay-actions">
          <button type="button" class="btn btn-outline-secondary signature-cancel-inline-btn">Cancel</button>
          <button type="button" class="btn btn-success signature-save-inline-btn">Save signature</button>
        </div>
      </div>`;
    popupRoot.appendChild(overlay);

    const canvas = overlay.querySelector('.signature-canvas-inline');
    const stage = canvas.parentElement;
    const stageWidth = stage.clientWidth || Math.max(popupRoot.clientWidth - 48, 280);
    const cssHeight = isMobileViewport() ? Math.min(window.innerHeight * 0.4, 280) : 220;
    const pad = initSignaturePad(canvas, stageWidth, cssHeight);
    const errorEl = overlay.querySelector('.signature-pad-error');

    function showError(message) {
      if (!errorEl) return;
      errorEl.textContent = message;
      errorEl.hidden = !message;
    }

    if (existingSignature) {
      loadSignatureOntoCanvas(canvas, existingSignature, stageWidth, cssHeight).then(function () {
        pad.markSigned();
      });
    }

    overlay.querySelector('.signature-clear-inline-btn').addEventListener('click', function () {
      pad.clear();
      showError('');
    });

    overlay.querySelector('.signature-cancel-inline-btn').addEventListener('click', function () {
      overlay.remove();
    });

    overlay.querySelector('.signature-save-inline-btn').addEventListener('click', function () {
      if (pad.isEmpty()) {
        showError('Please capture the customer signature.');
        return;
      }
      if (typeof onDone === 'function') {
        onDone(pad.toDataURL());
      }
      overlay.remove();
    });
  }

  function customerContactHtml(data) {
    return `
      <div class="booking-contact-actions">
        ${data.customer.phone ? `
          <a href="tel:${escapeHtml(data.customer.phone)}" class="btn btn-outline-primary booking-action-btn">
            <i class="bi bi-telephone me-2"></i>Call ${escapeHtml(data.customer.phone)}
          </a>` : ''}
        <a href="mailto:${escapeHtml(data.customer.email)}" class="btn btn-outline-secondary booking-action-btn">
          <i class="bi bi-envelope me-2"></i>Email customer
        </a>
        <a href="https://maps.google.com/?q=${encodeURIComponent(data.address.full)}" target="_blank" rel="noopener"
           class="btn btn-outline-secondary booking-action-btn">
          <i class="bi bi-geo-alt me-2"></i>Open in Maps
        </a>
      </div>`;
  }

  function openStartJobModal(booking) {
    Swal.fire({
      title: 'Start job',
      html: `
        <p class="booking-modal-intro">Take a <strong>before</strong> photo of each item booked.</p>
        <form id="bookingStartForm" class="text-start booking-job-form">
          ${photoFieldsHtml(booking.services, 'before', 'Before photo')}
        </form>`,
      width: isMobileViewport() ? '100%' : 560,
      showCancelButton: true,
      confirmButtonText: 'Start job',
      confirmButtonColor: '#0e7490',
      focusConfirm: false,
      customClass: swalMobileClasses(),
      didOpen: function () {
        wirePhotoUploadPreviews(document.getElementById('bookingStartForm'));
      },
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
    let signatureDataUrl = '';

    Swal.fire({
      title: 'Complete job',
      html: `
        <p class="booking-modal-intro">Add <strong>after</strong> photos and customer sign-off.</p>
        <form id="bookingCompleteForm" class="text-start booking-job-form">
          ${photoFieldsHtml(booking.services, 'after', 'After photo')}
          <div class="mt-3">
            <label class="form-label" for="signedByName">Customer name</label>
            <input type="text" class="form-control form-control-lg" id="signedByName" name="signed_by_name"
                   value="${escapeHtml(booking.customer.name)}" required autocomplete="name">
          </div>
          <div class="mt-3">
            <label class="form-label">Customer signature</label>
            <button type="button" class="signature-pad-trigger" id="openSignaturePadBtn">
              <span class="signature-pad-trigger-placeholder" id="signaturePlaceholder">
                <i class="bi bi-pen"></i>
                Tap to sign — opens larger signature box
              </span>
              <img id="signaturePreviewImg" class="signature-preview-img" alt="Signature preview" hidden>
            </button>
            <button type="button" class="btn btn-sm btn-outline-secondary mt-2" id="clearSignaturePreviewBtn" hidden>Clear signature</button>
          </div>
        </form>`,
      width: isMobileViewport() ? '100%' : 560,
      showCancelButton: true,
      confirmButtonText: 'Complete job',
      confirmButtonColor: '#059669',
      focusConfirm: false,
      customClass: swalMobileClasses(),
      didOpen: function () {
        wirePhotoUploadPreviews(document.getElementById('bookingCompleteForm'));

        const openBtn = document.getElementById('openSignaturePadBtn');
        const clearBtn = document.getElementById('clearSignaturePreviewBtn');
        const placeholder = document.getElementById('signaturePlaceholder');
        const previewImg = document.getElementById('signaturePreviewImg');

        function refreshSignatureUi() {
          const hasSig = Boolean(signatureDataUrl);
          openBtn.classList.toggle('has-signature', hasSig);
          placeholder.hidden = hasSig;
          clearBtn.hidden = !hasSig;
          updateSignaturePreview(previewImg, hasSig ? signatureDataUrl : '');
        }

        openBtn.addEventListener('click', function () {
          showInlineSignaturePad(Swal.getPopup(), signatureDataUrl, function (dataUrl) {
            signatureDataUrl = dataUrl;
            refreshSignatureUi();
          });
        });

        clearBtn.addEventListener('click', function () {
          signatureDataUrl = '';
          refreshSignatureUi();
        });

        refreshSignatureUi();
      },
      preConfirm: function () {
        const form = document.getElementById('bookingCompleteForm');
        const signedByName = form.querySelector('#signedByName').value.trim();
        if (!signedByName) {
          Swal.showValidationMessage('Customer name is required.');
          return false;
        }
        if (!signatureDataUrl) {
          Swal.showValidationMessage('Please capture the customer signature.');
          return false;
        }
        const formData = new FormData();
        formData.append('signed_by_name', signedByName);
        formData.append('signature', signatureDataUrl);
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
          width: isMobileViewport() ? '100%' : 620,
          showCancelButton: true,
          confirmButtonText: 'Save services',
          confirmButtonColor: '#0e7490',
          focusConfirm: false,
          customClass: swalMobileClasses({
            popup: 'panel-booking-popup panel-service-popup',
            htmlContainer: 'panel-service-html',
          }),
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
    document.getElementById('bookingSaveDiscountBtn')?.addEventListener('click', function () {
      saveBookingDiscount(booking);
    });
  }

  function saveBookingDiscount(booking) {
    const input = document.getElementById('bookingDiscountInput');
    if (!input) return;

    const subtotal = Number(booking.pricing.subtotal);
    const discount = Number(input.value);
    if (Number.isNaN(discount) || discount < 0) {
      window.showAppToast('Enter a valid discount amount.', 'error');
      return;
    }
    if (discount > subtotal) {
      window.showAppToast('Discount cannot exceed the subtotal.', 'error');
      return;
    }

    const body = new FormData();
    body.append('discount_amount', discount.toFixed(2));

    fetch(apiUrl(`/${booking.id}/discount/`), {
      method: 'POST',
      headers: { 'X-CSRFToken': csrfHeader() },
      body: body,
    })
      .then(function (response) {
        return response.json().then(function (data) {
          return { ok: response.ok, data: data };
        });
      })
      .then(function ({ ok, data }) {
        if (!ok) throw new Error(data.error || 'Could not save discount');
        let message = 'Discount updated';
        if (data.email_sent === true) {
          message = 'Discount updated — customer emailed';
        } else if (data.email_sent === false) {
          message = 'Discount updated, but the email could not be sent';
        }
        window.showAppToast(message, data.email_sent === false ? 'error' : 'success');
        openBookingView(booking.id);
      })
      .catch(function (error) {
        window.showAppToast(error.message, 'error');
      });
  }

  window.openBookingView = function (bookingId) {
    fetchBooking(bookingId)
      .then(function (data) {
        Swal.fire({
          html: buildViewHtml(data),
          title: 'Booking #' + data.id,
          width: isMobileViewport() ? '100%' : 640,
          showConfirmButton: false,
          showCloseButton: true,
          customClass: swalMobileClasses({ popup: 'panel-booking-popup booking-view-popup' }),
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
    const standalone = event.target.closest('[data-booking-view]:not(td)');
    if (standalone) {
      event.preventDefault();
      openBookingView(standalone.dataset.bookingView);
      return;
    }
    const cell = event.target.closest('td.booking-list-cell[data-booking-view]');
    if (!cell) return;
    event.preventDefault();
    openBookingView(cell.dataset.bookingView);
  });
})();

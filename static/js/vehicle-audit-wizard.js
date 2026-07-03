(function () {
  'use strict';

  var stepsEl = document.getElementById('vehicle-audit-steps');
  var wizard = document.getElementById('vehicleAuditWizard');
  var form = document.getElementById('vehicleAuditForm');
  if (!stepsEl || !wizard || !form) return;

  var photoSteps = JSON.parse(stepsEl.textContent);
  var flow = [{ id: 'mileage', kind: 'mileage' }].concat(
    photoSteps.map(function (step) {
      return { id: step.type, kind: 'photo', meta: step };
    }),
    [{ id: 'review', kind: 'review' }]
  );

  var index = 0;
  var captured = {};
  var stream = null;
  var useInlineCamera = false;
  var isMobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent)
    || window.matchMedia('(max-width: 767px)').matches;

  var progressBar = document.getElementById('wizardProgressBar');
  var stepLabel = document.getElementById('wizardStepLabel');
  var stepCount = document.getElementById('wizardStepCount');
  var advanceNotice = document.getElementById('wizardAdvanceNotice');

  var photoStepEl = wizard.querySelector('[data-wizard-step="photo"]');
  var photoSectionLabel = document.getElementById('photoSectionLabel');
  var photoTitle = document.getElementById('photoTitle');
  var photoHint = document.getElementById('photoHint');
  var cameraVideo = document.getElementById('cameraVideo');
  var cameraCanvas = document.getElementById('cameraCanvas');
  var cameraPreview = document.getElementById('cameraPreview');
  var cameraLive = document.getElementById('cameraLive');
  var cameraCaptureBtn = document.getElementById('cameraCaptureBtn');
  var cameraRetakeBtn = document.getElementById('cameraRetakeBtn');
  var cameraFallbackMsg = document.getElementById('cameraFallbackMsg');
  var reviewGrid = document.getElementById('reviewGrid');

  var mileageInput = document.getElementById('mileage');
  var nativeCaptureInput = document.createElement('input');
  nativeCaptureInput.type = 'file';
  nativeCaptureInput.accept = 'image/*';
  nativeCaptureInput.capture = 'environment';
  nativeCaptureInput.hidden = true;
  document.body.appendChild(nativeCaptureInput);

  function currentStep() {
    return flow[index];
  }

  function totalSteps() {
    return flow.length;
  }

  function updateProgress() {
    var pct = Math.round((index / (totalSteps() - 1)) * 100);
    progressBar.style.width = pct + '%';
    stepCount.textContent = (index + 1) + ' / ' + totalSteps();
    stepLabel.textContent = currentStep().kind === 'photo'
      ? currentStep().meta.label
      : currentStep().kind === 'mileage'
        ? 'Mileage'
        : 'Review';
  }

  function showStepEl(kind) {
    wizard.querySelectorAll('.vehicle-audit-wizard__step').forEach(function (el) {
      var active = el.getAttribute('data-wizard-step') === kind;
      el.hidden = !active;
      el.classList.toggle('is-active', active);
    });
  }

  function clearFileInput(type) {
    var input = document.getElementById('file_' + type);
    if (!input) return;
    input.value = '';
  }

  function stopCamera() {
    if (stream) {
      stream.getTracks().forEach(function (track) { track.stop(); });
      stream = null;
    }
    cameraVideo.srcObject = null;
  }

  function assignFileToInput(type, file) {
    var input = document.getElementById('file_' + type);
    if (!input || !file) return false;
    var dt = new DataTransfer();
    dt.items.add(file);
    input.files = dt.files;
    return true;
  }

  function flashAdvanceNotice() {
    advanceNotice.classList.remove('d-none');
    window.setTimeout(function () {
      advanceNotice.classList.add('d-none');
    }, 700);
  }

  function goNext(auto) {
    if (index >= totalSteps() - 1) return;
    index += 1;
    renderStep(auto);
  }

  function goBack() {
    if (index <= 0) return;
    stopCamera();
    index -= 1;
    renderStep(false);
  }

  function buildReviewGrid() {
    reviewGrid.innerHTML = '';
    photoSteps.forEach(function (step) {
      var item = document.createElement('div');
      item.className = 'vehicle-audit-review-item';
      var img = document.createElement('img');
      img.alt = step.label;
      if (captured[step.type]) {
        img.src = captured[step.type].previewUrl;
      }
      var label = document.createElement('span');
      label.className = 'vehicle-audit-review-item__label';
      label.textContent = step.label;
      item.appendChild(img);
      item.appendChild(label);
      reviewGrid.appendChild(item);
    });
  }

  function startInlineCamera() {
    stopCamera();
    cameraPreview.hidden = true;
    cameraVideo.hidden = false;
    cameraCaptureBtn.classList.remove('d-none');
    cameraRetakeBtn.classList.add('d-none');
    cameraFallbackMsg.classList.add('d-none');
    cameraLive.classList.remove('vehicle-audit-camera__live--mobile');

    if (isMobile) {
      useInlineCamera = false;
      cameraVideo.hidden = true;
      cameraLive.classList.add('vehicle-audit-camera__live--mobile');
      cameraFallbackMsg.textContent = 'Tap Take photo — your phone camera opens for each shot.';
      cameraFallbackMsg.classList.remove('d-none');
      return;
    }

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      useInlineCamera = false;
      cameraVideo.hidden = true;
      cameraFallbackMsg.classList.remove('d-none');
      return;
    }

    navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: 'environment' } },
      audio: false,
    }).then(function (mediaStream) {
      useInlineCamera = true;
      stream = mediaStream;
      cameraVideo.srcObject = stream;
    }).catch(function () {
      useInlineCamera = false;
      cameraVideo.hidden = true;
      cameraFallbackMsg.classList.remove('d-none');
    });
  }

  function captureInlinePhoto() {
    if (!useInlineCamera || !stream) {
      openNativeCamera();
      return;
    }
    var video = cameraVideo;
    var canvas = cameraCanvas;
    canvas.width = video.videoWidth || 1280;
    canvas.height = video.videoHeight || 720;
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(function (blob) {
      if (!blob) return;
      var step = currentStep();
      var file = new File([blob], step.id + '.jpg', { type: 'image/jpeg' });
      acceptPhoto(step.id, file);
    }, 'image/jpeg', 0.88);
  }

  function openNativeCamera() {
    var step = currentStep();
    nativeCaptureInput.value = '';
    nativeCaptureInput.onchange = function () {
      if (!nativeCaptureInput.files || !nativeCaptureInput.files[0]) return;
      acceptPhoto(step.id, nativeCaptureInput.files[0], true);
    };
    nativeCaptureInput.click();
  }

  function acceptPhoto(type, file, fromNative) {
    if (captured[type] && captured[type].previewUrl) {
      URL.revokeObjectURL(captured[type].previewUrl);
    }
    var previewUrl = URL.createObjectURL(file);
    captured[type] = { file: file, previewUrl: previewUrl };
    assignFileToInput(type, file);

    stopCamera();

    if (fromNative && isMobile) {
      flashAdvanceNotice();
      window.setTimeout(function () {
        goNext(true);
      }, 200);
      return;
    }

    cameraPreview.src = previewUrl;
    cameraPreview.hidden = false;
    cameraVideo.hidden = true;
    cameraCaptureBtn.classList.add('d-none');
    cameraRetakeBtn.classList.remove('d-none');

    flashAdvanceNotice();
    window.setTimeout(function () {
      goNext(true);
    }, 450);
  }

  function retakeCurrentPhoto() {
    var step = currentStep();
    if (captured[step.id] && captured[step.id].previewUrl) {
      URL.revokeObjectURL(captured[step.id].previewUrl);
      delete captured[step.id];
    }
    assignFileToInput(step.id, null);
    clearFileInput(step.id);
    startInlineCamera();
  }

  function renderPhotoStep(step) {
    photoSectionLabel.textContent = step.meta.section;
    photoTitle.textContent = step.meta.label;
    photoHint.textContent = step.meta.hint;
    showStepEl('photo');
    startInlineCamera();
  }

  function renderStep(auto) {
    updateProgress();
    var step = currentStep();

    if (step.kind === 'mileage') {
      stopCamera();
      showStepEl('mileage');
      if (!auto) mileageInput.focus();
      return;
    }

    if (step.kind === 'photo') {
      renderPhotoStep(step);
      return;
    }

    if (step.kind === 'review') {
      stopCamera();
      buildReviewGrid();
      showStepEl('review');
    }
  }

  wizard.querySelectorAll('[data-wizard-next]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      if (currentStep().kind === 'mileage') {
        if (!mileageInput.value || !mileageInput.checkValidity()) {
          mileageInput.reportValidity();
          return;
        }
      }
      goNext(false);
    });
  });

  wizard.querySelectorAll('[data-wizard-back]').forEach(function (btn) {
    btn.addEventListener('click', goBack);
  });

  cameraCaptureBtn.addEventListener('click', captureInlinePhoto);
  cameraRetakeBtn.addEventListener('click', retakeCurrentPhoto);

  form.addEventListener('submit', function (event) {
    if (!mileageInput.value) {
      event.preventDefault();
      index = 0;
      renderStep(false);
      mileageInput.reportValidity();
      return;
    }
    var missing = photoSteps.filter(function (step) {
      return !captured[step.type];
    });
    if (missing.length) {
      event.preventDefault();
      index = flow.findIndex(function (item) {
        return item.id === missing[0].type;
      });
      renderStep(false);
      window.alert('Please capture all required photos before submitting.');
    }
  });

  window.addEventListener('pagehide', stopCamera);

  renderStep(false);
})();

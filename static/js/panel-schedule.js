(function () {
  const config = window.panelScheduleConfig;
  if (!config) return;

  const timelineEl = document.getElementById('scheduleTimeline');
  const legsEl = document.getElementById('scheduleLegs');
  const countEl = document.getElementById('scheduleJobCount');
  let map;
  let routeLayer;

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function statusBadge(status) {
    return `<span class="badge status-${escapeHtml(status)}">${escapeHtml(status.replace('_', ' '))}</span>`;
  }

  function renderTimeline(data) {
    if (!data.jobs.length) {
      timelineEl.innerHTML = '<p class="text-muted mb-0">No jobs scheduled for this day.</p>';
      return;
    }

    const legMap = {};
    data.legs.forEach(function (leg) {
      legMap[leg.to_booking_id] = leg;
    });

    timelineEl.innerHTML = data.jobs.map(function (job, index) {
      const leg = legMap[job.booking_id];
      const travelBlock = leg
        ? `<div class="schedule-travel"><i class="bi bi-car-front"></i> ${leg.travel_minutes} min drive from #${leg.from_booking_id} <span class="text-muted">(${escapeHtml(leg.travel_source)})</span></div>`
        : '';

      return `
        ${travelBlock}
        <article class="schedule-job status-${escapeHtml(job.status)}">
          <div class="schedule-job-time">
            <strong>${escapeHtml(job.start)}</strong>
            <span>${escapeHtml(job.end)}</span>
            <small>${job.duration_minutes} min on site</small>
          </div>
          <div class="schedule-job-body">
            <div class="d-flex justify-content-between align-items-start gap-2">
              <div>
                <h3 class="h6 mb-1">#${job.booking_id} · ${escapeHtml(job.customer)}</h3>
                <p class="mb-1 small text-muted">${escapeHtml(job.services)}</p>
                <p class="mb-0 small">${escapeHtml(job.address)}</p>
                ${job.phone ? `<p class="mb-0 small"><a href="tel:${escapeHtml(job.phone)}">${escapeHtml(job.phone)}</a></p>` : ''}
              </div>
              <div class="text-end">
                ${statusBadge(job.status)}
                <div class="mt-2"><button type="button" class="btn btn-sm btn-outline-primary" data-booking-view="${job.booking_id}">View</button></div>
              </div>
            </div>
          </div>
        </article>
      `;
    }).join('');
  }

  function renderLegs(data) {
    if (!data.legs.length) {
      legsEl.innerHTML = '<p class="text-muted small mb-0">Single job or no travel data.</p>';
      return;
    }
    legsEl.innerHTML = `<ul class="list-group list-group-flush">${data.legs.map(function (leg) {
      return `<li class="list-group-item px-0 d-flex justify-content-between">
        <span>#${leg.from_booking_id} → #${leg.to_booking_id}</span>
        <strong>${leg.travel_minutes} min</strong>
      </li>`;
    }).join('')}</ul>`;
  }

  function initMap() {
    if (map || !document.getElementById('scheduleMap')) return;
    map = L.map('scheduleMap', { scrollWheelZoom: false });
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 18,
      attribution: '&copy; OpenStreetMap',
    }).addTo(map);
    routeLayer = L.layerGroup().addTo(map);
  }

  function renderMap(data) {
    initMap();
    routeLayer.clearLayers();
    const bounds = [];
    const markers = [];

    data.jobs.forEach(function (job, index) {
      if (!job.coords) return;
      const latLng = L.latLng(job.coords[0], job.coords[1]);
      bounds.push(latLng);
      const marker = L.marker(latLng).bindPopup(
        `<strong>#${job.booking_id}</strong><br>${escapeHtml(job.start)} · ${escapeHtml(job.customer)}`
      );
      markers.push(marker);
      routeLayer.addLayer(marker);
    });

    data.legs.forEach(function (leg) {
      if (!leg.geometry || !leg.geometry.length) return;
      const latLngs = leg.geometry.map(function (coord) {
        return L.latLng(coord[1], coord[0]);
      });
      routeLayer.addLayer(L.polyline(latLngs, { color: '#0e7490', weight: 4, opacity: 0.85 }));
      latLngs.forEach(function (point) { bounds.push(point); });
    });

    if (bounds.length) {
      map.fitBounds(L.latLngBounds(bounds), { padding: [24, 24] });
    } else {
      map.setView([51.5, -0.12], 10);
    }
  }

  function loadSchedule() {
    fetch(`${config.apiUrl}?date=${encodeURIComponent(config.selectedDate)}`, {
      headers: { Accept: 'application/json' },
    })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        countEl.textContent = `${data.job_count} job${data.job_count === 1 ? '' : 's'}`;
        renderTimeline(data);
        renderLegs(data);
        renderMap(data);
      })
      .catch(function () {
        timelineEl.innerHTML = '<p class="text-danger mb-0">Could not load schedule.</p>';
      });
  }

  loadSchedule();
})();

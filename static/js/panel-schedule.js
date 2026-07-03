(function () {
  'use strict';

  function initSchedulePage() {
    const config = window.panelScheduleConfig;
    if (!config) return;

    const timelineEl = document.getElementById('scheduleTimeline');
    const legsEl = document.getElementById('scheduleLegs');
    const countEl = document.getElementById('scheduleJobCount');
    const layoutEl = document.getElementById('scheduleLayout');
    const mobileQuery = window.matchMedia('(max-width: 1199px)');
    let map;
    let routeLayer;
    let scheduleData = null;
    let mapInitialized = false;

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

    function isMobileScheduleView() {
      return mobileQuery.matches;
    }

    function renderTimeline(data) {
      if (!timelineEl) return;
      if (!data.jobs.length) {
        timelineEl.innerHTML = '<p class="text-muted mb-0">No jobs scheduled for this day.</p>';
        return;
      }

      const legMap = {};
      data.legs.forEach(function (leg) {
        legMap[leg.to_booking_id] = leg;
      });

      timelineEl.innerHTML = data.jobs.map(function (job) {
        const leg = legMap[job.booking_id];
        const travelBlock = leg
          ? `<div class="schedule-travel"><i class="bi bi-car-front"></i> ${leg.travel_minutes} min drive from #${leg.from_booking_id} <span class="text-muted">(${escapeHtml(leg.travel_source)})</span></div>`
          : '';

        return `
          ${travelBlock}
          <article class="schedule-job is-clickable status-${escapeHtml(job.status)}" data-booking-view="${job.booking_id}" tabindex="0"
                   aria-label="View booking #${job.booking_id} for ${escapeHtml(job.customer)}">
            <div class="schedule-job-time">
              <strong>${escapeHtml(job.start)}</strong>
              <span>${escapeHtml(job.end)}</span>
              <small>${job.duration_minutes} min on site</small>
            </div>
            <div class="schedule-job-body">
              <div class="d-flex justify-content-between align-items-start gap-2">
                <div class="min-w-0">
                  <h3 class="h6 mb-1">#${job.booking_id} · ${escapeHtml(job.customer)}</h3>
                  <p class="mb-1 small text-muted">${escapeHtml(job.services)}</p>
                  <p class="mb-0 small">${escapeHtml(job.address)}</p>
                  ${job.phone ? `<p class="mb-0 small mt-1"><a href="tel:${escapeHtml(job.phone)}" onclick="event.stopPropagation()">${escapeHtml(job.phone)}</a></p>` : ''}
                </div>
                <div class="schedule-job-actions">
                  ${statusBadge(job.status)}
                  <button type="button" class="btn btn-sm btn-outline-primary" data-booking-view="${job.booking_id}">View</button>
                </div>
              </div>
            </div>
          </article>
        `;
      }).join('');
    }

    function renderLegs(data) {
      if (!legsEl) return;
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
      if (mapInitialized || !document.getElementById('scheduleMap') || typeof window.L === 'undefined') {
        return false;
      }
      map = window.L.map('scheduleMap', { scrollWheelZoom: false });
      window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 18,
        attribution: '&copy; OpenStreetMap',
      }).addTo(map);
      routeLayer = window.L.layerGroup().addTo(map);
      mapInitialized = true;
      return true;
    }

    function renderMap(data) {
      if (!initMap() || !routeLayer) return;

      routeLayer.clearLayers();
      const bounds = [];

      data.jobs.forEach(function (job) {
        if (!job.coords) return;
        const latLng = window.L.latLng(job.coords[0], job.coords[1]);
        bounds.push(latLng);
        const marker = window.L.marker(latLng).bindPopup(
          `<strong>#${job.booking_id}</strong><br>${escapeHtml(job.start)} · ${escapeHtml(job.customer)}`
        );
        routeLayer.addLayer(marker);
      });

      data.legs.forEach(function (leg) {
        if (!leg.geometry || !leg.geometry.length) return;
        const latLngs = leg.geometry.map(function (coord) {
          return window.L.latLng(coord[1], coord[0]);
        });
        routeLayer.addLayer(window.L.polyline(latLngs, { color: '#0e7490', weight: 4, opacity: 0.85 }));
        latLngs.forEach(function (point) { bounds.push(point); });
      });

      if (bounds.length) {
        map.fitBounds(window.L.latLngBounds(bounds), { padding: [24, 24] });
      } else {
        map.setView([53.8, -1.55], 10);
      }

      refreshMapSize();
    }

    function refreshMapSize() {
      if (!map) return;
      window.setTimeout(function () {
        map.invalidateSize();
      }, 120);
    }

    function setScheduleView(view) {
      const tabs = document.querySelectorAll('[data-schedule-tab]');
      const target = view === 'map' ? 'map' : 'timeline';

      tabs.forEach(function (tab) {
        const active = tab.dataset.scheduleTab === target;
        tab.classList.toggle('is-active', active);
        tab.setAttribute('aria-selected', active ? 'true' : 'false');
      });

      if (layoutEl && isMobileScheduleView()) {
        layoutEl.classList.toggle('schedule-view-map', target === 'map');
        layoutEl.classList.toggle('schedule-view-timeline', target === 'timeline');
      }

      if (target === 'map') {
        if (scheduleData) {
          renderMap(scheduleData);
        }
        refreshMapSize();
        document.getElementById('schedulePanelMap')?.scrollIntoView({ block: 'start', behavior: 'smooth' });
      }
    }

    function bindMobileTabs() {
      const tabBar = document.querySelector('.schedule-mobile-tabs');
      if (!tabBar) return;

      tabBar.addEventListener('click', function (event) {
        const tab = event.target.closest('[data-schedule-tab]');
        if (!tab) return;
        event.preventDefault();
        setScheduleView(tab.dataset.scheduleTab);
      });
    }

    function resetDesktopView() {
      if (!layoutEl || isMobileScheduleView()) return;
      layoutEl.classList.add('schedule-view-timeline');
      layoutEl.classList.remove('schedule-view-map');
    }

    function loadSchedule() {
      fetch(`${config.apiUrl}?date=${encodeURIComponent(config.selectedDate)}`, {
        headers: { Accept: 'application/json' },
      })
        .then(function (response) { return response.json(); })
        .then(function (data) {
          scheduleData = data;
          if (countEl) {
            countEl.textContent = `${data.job_count} job${data.job_count === 1 ? '' : 's'}`;
          }
          renderTimeline(data);
          renderLegs(data);
          if (!isMobileScheduleView() || layoutEl?.classList.contains('schedule-view-map')) {
            renderMap(data);
          }
        })
        .catch(function () {
          if (timelineEl) {
            timelineEl.innerHTML = '<p class="text-danger mb-0">Could not load schedule.</p>';
          }
        });
    }

    bindMobileTabs();
    resetDesktopView();

    mobileQuery.addEventListener('change', function () {
      resetDesktopView();
      if (!isMobileScheduleView()) {
        setScheduleView('timeline');
        if (scheduleData) renderMap(scheduleData);
      }
    });

    const activeWeekDay = document.querySelector('.week-day.active');
    if (activeWeekDay) {
      activeWeekDay.scrollIntoView({ inline: 'center', block: 'nearest' });
    }

    loadSchedule();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSchedulePage);
  } else {
    initSchedulePage();
  }
})();

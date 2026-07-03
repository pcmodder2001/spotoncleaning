(function () {
  'use strict';

  var nav = document.querySelector('[data-hr-nav]');
  if (!nav) return;

  var tabs = nav.querySelectorAll('[data-hr-mode-tab]');
  var panels = nav.querySelectorAll('[data-hr-subnav]');
  if (!tabs.length || !panels.length) return;

  function showPanel(mode) {
    tabs.forEach(function (tab) {
      var active = tab.dataset.hrModeTab === mode;
      tab.classList.toggle('active', active);
      tab.setAttribute('aria-selected', active ? 'true' : 'false');
    });

    panels.forEach(function (panel) {
      var show = panel.dataset.hrSubnav === mode;
      panel.hidden = !show;
      panel.classList.toggle('is-visible', show);
      panel.classList.toggle('is-hidden', !show);
    });
  }

  tabs.forEach(function (tab) {
    tab.addEventListener('click', function (event) {
      event.preventDefault();
      var mode = tab.dataset.hrModeTab;
      showPanel(mode);
      window.location.href = tab.getAttribute('href');
    });
  });
})();

(function () {
  'use strict';

  var MOBILE_QUERY = window.matchMedia('(max-width: 991px)');

  function initPanelNav() {
    var layout = document.getElementById('panelLayout');
    var sidebar = document.getElementById('panelSidebar');
    var backdrop = document.getElementById('panelSidebarBackdrop');
    var openBtn = document.getElementById('panelMenuToggle');
    var closeBtn = document.getElementById('panelSidebarClose');

    if (!layout || !sidebar || !backdrop || !openBtn) {
      return;
    }

    function isMobile() {
      return MOBILE_QUERY.matches;
    }

    function setOpen(open) {
      layout.classList.toggle('is-sidebar-open', open);
      backdrop.hidden = !open;
      openBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
      openBtn.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
      document.body.classList.toggle('panel-nav-open', open);
    }

    function openSidebar() {
      if (!isMobile()) return;
      setOpen(true);
    }

    function closeSidebar() {
      setOpen(false);
    }

    function toggleSidebar() {
      if (!isMobile()) return;
      setOpen(!layout.classList.contains('is-sidebar-open'));
    }

    openBtn.addEventListener('click', function (event) {
      event.preventDefault();
      toggleSidebar();
    });

    if (closeBtn) {
      closeBtn.addEventListener('click', function (event) {
        event.preventDefault();
        closeSidebar();
      });
    }

    backdrop.addEventListener('click', closeSidebar);

    sidebar.querySelectorAll('.panel-nav a').forEach(function (link) {
      link.addEventListener('click', closeSidebar);
    });

    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') {
        closeSidebar();
      }
    });

    MOBILE_QUERY.addEventListener('change', function () {
      if (!isMobile()) {
        closeSidebar();
      }
    });

    window.addEventListener('pagehide', closeSidebar);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPanelNav);
  } else {
    initPanelNav();
  }
})();

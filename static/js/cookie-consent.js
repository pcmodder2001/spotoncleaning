(function () {
  'use strict';

  var COOKIE_NAME = 'spoton_cookie_consent';
  var MAX_AGE = 365 * 24 * 60 * 60;

  function setConsent(value) {
    var secure = window.location.protocol === 'https:' ? '; Secure' : '';
    document.cookie = COOKIE_NAME + '=' + encodeURIComponent(value)
      + '; Max-Age=' + MAX_AGE
      + '; Path=/'
      + '; SameSite=Lax'
      + secure;
    window.location.reload();
  }

  function init() {
    var banner = document.getElementById('cookieConsentBanner');
    if (!banner) return;

    if (banner.dataset.show === 'true') {
      banner.hidden = false;
    }

    banner.querySelectorAll('[data-consent]').forEach(function (button) {
      button.addEventListener('click', function () {
        setConsent(button.getAttribute('data-consent'));
      });
    });

    document.querySelectorAll('[data-cookie-settings]').forEach(function (link) {
      link.addEventListener('click', function (event) {
        event.preventDefault();
        banner.hidden = false;
        banner.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

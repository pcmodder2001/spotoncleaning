(function () {
  'use strict';

  function getCookie(name) {
    var match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
    return match ? decodeURIComponent(match[2]) : '';
  }

  function csrfToken(form) {
    var input = form.querySelector('input[name="csrfmiddlewaretoken"]');
    return (input && input.value) || getCookie('csrftoken');
  }

  function showToast(message, icon) {
    if (typeof window.showAppToast === 'function') {
      window.showAppToast(message, icon || 'success');
    }
  }

  function updateProgress(progress, openTasks) {
    var textEl = document.getElementById('onboarding-progress-text');
    var barEl = document.getElementById('onboarding-progress-bar');
    if (textEl) {
      textEl.textContent = progress + '% complete';
    }
    if (barEl) {
      barEl.style.width = progress + '%';
      barEl.setAttribute('aria-valuenow', String(progress));
    }
    var openEl = document.getElementById('onboarding-open-tasks');
    if (openEl && typeof openTasks === 'number') {
      openEl.textContent = openTasks + ' task' + (openTasks === 1 ? '' : 's') + ' remaining';
    }
  }

  function flashRow(row) {
    row.classList.remove('onboarding-task-row--updated');
    void row.offsetWidth;
    row.classList.add('onboarding-task-row--updated');
    window.setTimeout(function () {
      row.classList.remove('onboarding-task-row--updated');
    }, 700);
  }

  function replaceTaskRow(taskId, html) {
    var existing = document.getElementById('onboarding-task-' + taskId);
    if (!existing) return null;

    var wrapper = document.createElement('div');
    wrapper.innerHTML = html.trim();
    var row = wrapper.firstElementChild;
    if (!row) return null;

    existing.replaceWith(row);
    flashRow(row);
    return row;
  }

  function setFormBusy(form, busy) {
    var button = form.querySelector('button[type="submit"]');
    if (!button) return;
    if (busy) {
      button.disabled = true;
      button.dataset.originalHtml = button.innerHTML;
      button.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';
    } else if (button.dataset.originalHtml) {
      button.disabled = false;
      button.innerHTML = button.dataset.originalHtml;
      delete button.dataset.originalHtml;
    }
  }

  function toggleTask(form) {
    var row = form.closest('.onboarding-task-row');
    var body = new FormData(form);

    setFormBusy(form, true);
    if (row) {
      row.classList.add('onboarding-task-row--pending');
    }

    return fetch(form.action, {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': csrfToken(form),
      },
      body: body,
      credentials: 'same-origin',
    })
      .then(function (response) {
        return response.json().then(function (data) {
          if (!response.ok || !data.ok) {
            throw new Error((data && data.error) || 'Could not update task.');
          }
          return data;
        }, function () {
          throw new Error('Could not update task.');
        });
      })
      .then(function (data) {
        replaceTaskRow(data.task_id, data.html);
        updateProgress(data.progress, data.open_tasks);
        showToast(data.message || 'Task updated.', 'success');
      })
      .catch(function (err) {
        showToast(err.message || 'Could not update task.', 'error');
      })
      .finally(function () {
        setFormBusy(form, false);
        if (row && row.isConnected) {
          row.classList.remove('onboarding-task-row--pending');
        }
      });
  }

  document.addEventListener('submit', function (event) {
    var form = event.target;
    if (!form.matches || !form.matches('form[data-onboarding-toggle]')) {
      return;
    }
    event.preventDefault();
    toggleTask(form);
  });
})();

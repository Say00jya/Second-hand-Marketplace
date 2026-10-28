/* ReMarket - small, dependency-free helpers (Bootstrap provides the rest). */
(function () {
  'use strict';

  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';

  /* 1. Delete / destructive confirmations using one shared Bootstrap modal */
  const modalEl = document.getElementById('confirmModal');
  if (modalEl && window.bootstrap) {
    const modal = new bootstrap.Modal(modalEl);
    const message = document.getElementById('confirmMessage');
    const yesBtn = document.getElementById('confirmYes');
    let pendingForm = null;
    document.addEventListener('submit', function (event) {
      const form = event.target;
      if (!(form instanceof HTMLFormElement) || !form.hasAttribute('data-confirm')) return;
      event.preventDefault();
      pendingForm = form;
      message.textContent = form.getAttribute('data-confirm');
      yesBtn.textContent = form.getAttribute('data-confirm-label') || 'Delete';
      modal.show();
    });
    yesBtn.addEventListener('click', function () {
      if (pendingForm) { const f = pendingForm; pendingForm = null; modal.hide(); f.submit(); }
    });
  }

  /* 2. Client-side validation for forms marked .needs-validation */
  document.querySelectorAll('form.needs-validation').forEach(function (form) {
    form.addEventListener('submit', function (event) {
      if (!form.checkValidity()) {
        event.preventDefault();
        event.stopPropagation();
        const firstBad = form.querySelector(':invalid');
        if (firstBad) firstBad.focus();
      }
      form.classList.add('was-validated');
    });
  });

  /* 3. Show / hide password */
  document.querySelectorAll('.toggle-pw').forEach(function (button) {
    button.addEventListener('click', function () {
      const input = document.getElementById(button.getAttribute('data-target'));
      const show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      button.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
      button.querySelector('i').className = show ? 'bi bi-eye-slash' : 'bi bi-eye';
    });
  });

  /* 4. Confirm-password match (register and profile pages) */
  document.querySelectorAll('[data-match]').forEach(function (input) {
    const other = document.getElementById(input.getAttribute('data-match'));
    function check() {
      input.setCustomValidity(input.value && other.value !== input.value ? 'Passwords do not match.' : '');
    }
    input.addEventListener('input', check);
    other.addEventListener('input', check);
  });

  /* 5. Live image preview on the sell page */
  const fileInput = document.getElementById('image');
  const preview = document.getElementById('imagePreview');
  if (fileInput && preview) {
    fileInput.addEventListener('change', function () {
      const file = fileInput.files[0];
      if (!file) return;
      if (file.size > 3 * 1024 * 1024) {
        fileInput.value = '';
        fileInput.setCustomValidity('Photo must be 3 MB or smaller.');
        fileInput.reportValidity();
        return;
      }
      fileInput.setCustomValidity('');
      preview.src = URL.createObjectURL(file);
    });
  }

  /* 6. Character counters */
  document.querySelectorAll('[data-counter]').forEach(function (field) {
    const target = document.getElementById(field.getAttribute('data-counter'));
    const max = field.getAttribute('maxlength');
    function update() { target.textContent = field.value.length + ' / ' + max; }
    field.addEventListener('input', update);
    update();
  });

  /* 7. Wishlist heart: toggles without reloading the page */
  document.addEventListener('submit', function (event) {
    const form = event.target;
    if (!form.classList || !form.classList.contains('wishlist-form')) return;
    event.preventDefault();
    const button = form.querySelector('.heart-btn');
    fetch(form.action, {
      method: 'POST',
      headers: { 'X-Requested-With': 'fetch', 'X-CSRFToken': csrf },
      credentials: 'same-origin'
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.ok) { showToast(data.message, 'warning'); return; }
        button.classList.toggle('saved', data.saved);
        button.classList.remove('pop'); void button.offsetWidth; button.classList.add('pop');
        const icon = button.querySelector('i');
        icon.className = data.saved ? 'bi bi-heart-fill' : 'bi bi-heart';
        button.setAttribute('aria-pressed', data.saved ? 'true' : 'false');
        button.setAttribute('aria-label', data.saved ? 'Remove from wishlist' : 'Add to wishlist');
        const label = form.querySelector('.wish-label');
        if (label) label.textContent = data.saved ? 'Saved to wishlist' : 'Save to wishlist';
        const pill = document.getElementById('wishlistCount');
        if (pill) { pill.textContent = data.count; pill.hidden = data.count === 0; }
        showToast(data.message, 'success');
        if (document.body.dataset.page === 'wishlist' && !data.saved) {
          const col = form.closest('.product-col');
          if (col) col.remove();
        }
      })
      .catch(function () { form.submit(); });   // fall back to a normal form post
  });

  /* 8. Small toast helper */
  function showToast(text, kind) {
    let wrap = document.getElementById('toastWrap');
    if (!wrap) {
      wrap = document.createElement('div');
      wrap.id = 'toastWrap';
      wrap.className = 'toast-container position-fixed bottom-0 end-0 p-3';
      wrap.setAttribute('aria-live', 'polite');
      document.body.appendChild(wrap);
    }
    const toast = document.createElement('div');
    toast.className = 'toast align-items-center border-0 text-bg-' + (kind === 'warning' ? 'warning' : 'dark');
    toast.setAttribute('role', 'status');
    toast.innerHTML = '<div class="d-flex"><div class="toast-body"></div>' +
      '<button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button></div>';
    toast.querySelector('.toast-body').textContent = text;
    wrap.appendChild(toast);
    const t = new bootstrap.Toast(toast, { delay: 2200 });
    toast.addEventListener('hidden.bs.toast', function () { toast.remove(); });
    t.show();
  }

  /* 9. Auto-dismiss success messages after a few seconds */
  document.querySelectorAll('.alert-success').forEach(function (alert) {
    setTimeout(function () {
      if (window.bootstrap && document.body.contains(alert)) bootstrap.Alert.getOrCreateInstance(alert).close();
    }, 5000);
  });

  /* 10. Admin category modal: fill the edit form from the clicked row */
  const editModal = document.getElementById('categoryModal');
  if (editModal) {
    editModal.addEventListener('show.bs.modal', function (event) {
      const b = event.relatedTarget;
      const form = editModal.querySelector('form');
      const isEdit = b && b.hasAttribute('data-edit-url');
      form.action = isEdit ? b.getAttribute('data-edit-url') : form.getAttribute('data-add-url');
      editModal.querySelector('.modal-title').textContent = isEdit ? 'Edit category' : 'Add category';
      form.elements.name.value = isEdit ? b.getAttribute('data-name') : '';
      form.elements.description.value = isEdit ? b.getAttribute('data-description') : '';
      form.elements.icon.value = isEdit ? b.getAttribute('data-icon') : 'bi-grid';
    });
  }

  /* 11. Price range sanity check on the filter form */
  const minPrice = document.getElementById('min_price');
  const maxPrice = document.getElementById('max_price');
  if (minPrice && maxPrice) {
    const check = function () {
      const lo = parseFloat(minPrice.value), hi = parseFloat(maxPrice.value);
      maxPrice.setCustomValidity(!isNaN(lo) && !isNaN(hi) && hi < lo ? 'Maximum must be at least the minimum.' : '');
    };
    minPrice.addEventListener('input', check);
    maxPrice.addEventListener('input', check);
  }
})();

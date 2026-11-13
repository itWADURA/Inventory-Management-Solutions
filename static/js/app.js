// Itwadura Inventory Application JavaScript

document.addEventListener('DOMContentLoaded', function () {
  // 1. Configure HTMX to automatically include Django CSRF token in requests
  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  document.body.addEventListener('htmx:configRequest', function (event) {
    const csrfToken = getCookie('csrftoken');
    if (csrfToken) {
      event.detail.headers['X-CSRFToken'] = csrfToken;
    }
  });

  // 2. Register Service Worker for PWA capabilities
  if ('serviceWorker' in navigator && window.location.protocol.startsWith('http')) {
    navigator.serviceWorker.register('/static/sw.js')
      .then(function (reg) {
        // Registered successfully
      })
      .catch(function (err) {
        // Non-blocking error in dev environments
      });
  }

  // 3. Dynamic Balance Display on Movement & Adjustment Forms
  const itemSelect = document.querySelector('[data-balance-item]');
  const locationSelect = document.querySelector('[data-balance-location]');
  const balanceDisplay = document.querySelector('[data-balance-display]');
  const deltaDisplay = document.querySelector('[data-delta-display]');
  const countedInput = document.querySelector('[data-counted-input]');

  function updateBalance() {
    if (!itemSelect || !locationSelect || !balanceDisplay) return;
    const itemId = itemSelect.value;
    const locationId = locationSelect.value;

    if (!itemId || !locationId) {
      balanceDisplay.textContent = '-';
      return;
    }

    fetch(`/inventory/api/balance/?item_id=${itemId}&location_id=${locationId}`)
      .then(res => res.json())
      .then(data => {
        balanceDisplay.textContent = `${data.quantity} ${data.unit}`;
        if (countedInput && deltaDisplay) {
          updateAdjustmentDelta(parseFloat(data.quantity) || 0);
        }
      })
      .catch(() => {
        balanceDisplay.textContent = 'Unavailable';
      });
  }

  function updateAdjustmentDelta(currentQty) {
    if (!countedInput || !deltaDisplay) return;
    const counted = parseFloat(countedInput.value);
    if (isNaN(counted)) {
      deltaDisplay.textContent = 'Enter count above';
      deltaDisplay.className = 'text-sm font-semibold text-gray-500';
      return;
    }
    const delta = counted - currentQty;
    if (delta > 0) {
      deltaDisplay.textContent = `+${delta.toFixed(2)} (Stock will increase)`;
      deltaDisplay.className = 'text-sm font-semibold text-emerald-600';
    } else if (delta < 0) {
      deltaDisplay.textContent = `${delta.toFixed(2)} (Stock will decrease)`;
      deltaDisplay.className = 'text-sm font-semibold text-rose-600';
    } else {
      deltaDisplay.textContent = '0.00 (No change)';
      deltaDisplay.className = 'text-sm font-semibold text-gray-600';
    }
  }

  if (itemSelect && locationSelect) {
    itemSelect.addEventListener('change', updateBalance);
    locationSelect.addEventListener('change', updateBalance);
    // Initial fetch if both pre-selected
    if (itemSelect.value && locationSelect.value) {
      updateBalance();
    }
  }

  if (countedInput) {
    countedInput.addEventListener('input', () => {
      const currentText = balanceDisplay ? balanceDisplay.textContent : '0';
      const currentQty = parseFloat(currentText) || 0;
      updateAdjustmentDelta(currentQty);
    });
  }
});


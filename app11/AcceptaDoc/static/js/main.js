// ── Prefiks aplikacji (dla Apache + ProxyFix: /app11; w dev: "") ──
const APP_BASE = (typeof window.APP_BASE === 'string') ? window.APP_BASE : '';

// ── Modals ─────────────────────────────────────────
function showModal(id) {
  const el = document.getElementById(id);
  if (el) { el.classList.add('visible'); el.focus(); }
}
function hideModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove('visible');
}
document.addEventListener('click', e => {
  if (e.target.classList.contains('modal-overlay')) {
    e.target.classList.remove('visible');
  }
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay.visible')
      .forEach(m => m.classList.remove('visible'));
  }
});

// ── Global search ──────────────────────────────────
const searchInput = document.getElementById('globalSearch');
const searchResults = document.getElementById('searchResults');
let searchTimer;

if (searchInput) {
  searchInput.addEventListener('input', () => {
    clearTimeout(searchTimer);
    const q = searchInput.value.trim();
    if (q.length < 2) { searchResults.classList.remove('visible'); return; }
    searchTimer = setTimeout(() => fetchSearch(q), 220);
  });
  searchInput.addEventListener('blur', () => {
    setTimeout(() => searchResults.classList.remove('visible'), 200);
  });
}

async function fetchSearch(q) {
  try {
    const res = await fetch(`${APP_BASE}/api/search?q=${encodeURIComponent(q)}`);
    const data = await res.json();
    renderSearchResults(data);
  } catch(e) {}
}

function renderSearchResults(items) {
  searchResults.innerHTML = '';
  if (!items.length) {
    searchResults.innerHTML = '<div style="padding:14px;color:#8b949e;font-size:.85rem">Brak wyników</div>';
  } else {
    items.forEach(item => {
      const div = document.createElement('div');
      div.className = 'search-result-item';
      div.innerHTML = `
        <span class="search-result-num">${item.name || ''}</span>
      `;
      div.addEventListener('click', () => {
        window.location.href = `${APP_BASE}/products/${item.id}`;
      });
      searchResults.appendChild(div);
    });
  }
  searchResults.classList.add('visible');
}

// ── Table row links ────────────────────────────────
document.querySelectorAll('.table-row-link').forEach(row => {
  row.addEventListener('click', e => {
    if (!e.target.closest('a') && !e.target.closest('button') && !e.target.closest('form')) {
      window.location.href = row.dataset.href;
    }
  });
});

// ── Auto-close alerts ──────────────────────────────
setTimeout(() => {
  document.querySelectorAll('.alert').forEach(el => {
    el.style.transition = 'opacity .4s';
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 400);
  });
}, 5000);

// ══════════════════════════════════════════════════════════════════
// Auto-logout (sliding 1h) — frontend fallback.
// Backend też tego pilnuje (before_request). Ten timer daje
// ostrzeżenie 5 minut przed wygaśnięciem.
// ══════════════════════════════════════════════════════════════════
(function () {
  if (!document.querySelector('.navbar')) return;

  var IDLE_WARN_MS  = 55 * 60 * 1000;
  var IDLE_LOGOUT_MS = 60 * 60 * 1000;
  var warningShown = false;
  var warnTimer, logoutTimer;

  function resetTimers() {
    warningShown = false;
    clearTimeout(warnTimer);
    clearTimeout(logoutTimer);

    warnTimer = setTimeout(function () {
      if (!warningShown) {
        warningShown = true;
        alert('Sesja wygaśnie za 5 minut z powodu braku aktywności.\nKliknij gdziekolwiek, aby ją przedłużyć.');
      }
    }, IDLE_WARN_MS);

    logoutTimer = setTimeout(function () {
      window.location.href = `${APP_BASE}/logout`;
    }, IDLE_LOGOUT_MS);
  }

  ['click', 'keydown', 'mousemove', 'scroll', 'touchstart'].forEach(function (ev) {
    document.addEventListener(ev, resetTimers, { passive: true });
  });

  resetTimers();
})();
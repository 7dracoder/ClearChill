/**
 * Fridge Observer — App Entry Point
 * app.js: Navigation, WebSocket wiring, global utilities
 */

// ── Global Utilities ─────────────────────────────────────────

/** Escape HTML to prevent XSS */
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/** Show a toast notification */
function showToast(message, type = 'info', duration = 3500) {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.setAttribute('role', 'alert');
  toast.setAttribute('aria-live', 'polite');

  const icons = { success: '✓', error: '✕', warning: '⚠', info: 'ℹ' };
  toast.innerHTML = `<span aria-hidden="true">${icons[type] || 'ℹ'}</span> ${escapeHtml(message)}`;

  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.add('toast-out');
    toast.addEventListener('animationend', () => toast.remove(), { once: true });
  }, duration);
}

// Make utilities global
window.escapeHtml = escapeHtml;
window.showToast = showToast;

// ── Navigation ───────────────────────────────────────────────

const SECTIONS = ['inventory', 'recipes', 'notifications', 'settings'];
let _activeSection = 'inventory';
let _sectionInitialized = {};

function navigateTo(section) {
  if (!SECTIONS.includes(section)) return;

  // Update active section
  _activeSection = section;

  // Show/hide content sections
  SECTIONS.forEach(s => {
    const el = document.getElementById(`section-${s}`);
    if (el) el.classList.toggle('active', s === section);
  });

  // Update nav items (sidebar)
  document.querySelectorAll('.nav-item').forEach(item => {
    item.classList.toggle('active', item.dataset.section === section);
    item.setAttribute('aria-current', item.dataset.section === section ? 'page' : 'false');
  });

  // Update tab items (mobile)
  document.querySelectorAll('.tab-item').forEach(item => {
    item.classList.toggle('active', item.dataset.section === section);
  });

  // Update header title
  const titles = {
    inventory: '🥦 Inventory',
    recipes: '🍳 Recipes',
    notifications: '🔔 Notifications',
    settings: '⚙️ Settings',
  };
  const headerTitle = document.querySelector('.content-header-title');
  if (headerTitle) headerTitle.textContent = titles[section] || section;

  // Initialize section on first visit
  if (!_sectionInitialized[section]) {
    _sectionInitialized[section] = true;
    initSection(section);
  }

  // Update URL hash
  history.replaceState(null, '', `#${section}`);
}

function initSection(section) {
  switch (section) {
    case 'inventory':
      if (window.inventoryModule) window.inventoryModule.refreshInventory();
      break;
    case 'recipes':
      if (window.recipesModule) window.recipesModule.refreshRecipes();
      break;
    case 'notifications':
      if (window.notificationsModule) window.notificationsModule.initNotifications();
      break;
    case 'settings':
      if (window.settingsModule) window.settingsModule.initSettings();
      break;
  }
}

// ── WebSocket Wiring ─────────────────────────────────────────

function initWebSocket() {
  const ws = window.fridgeWS;
  if (!ws) return;

  // Inventory updates
  ws.on('inventory_update', (payload) => {
    if (window.inventoryModule && _activeSection === 'inventory') {
      window.inventoryModule.renderInventoryGrid(payload);
    }
  });

  // Notifications
  ws.on('notification', (payload) => {
    const level = payload.level === 'warning' ? 'warning' : 'info';
    showToast(payload.message, level);
  });

  // Temperature updates
  ws.on('temperature_update', (payload) => {
    if (window.settingsModule) {
      window.settingsModule.updateTemperatureDisplay(payload);
    }
  });

  // Connect
  ws.connect();
}

// ── Connection Banner ────────────────────────────────────────

function initConnectionBanner() {
  const closeBtn = document.querySelector('.connection-banner-close');
  if (closeBtn) {
    closeBtn.addEventListener('click', () => {
      document.querySelector('.connection-banner')?.classList.remove('visible');
    });
  }
}

// ── App Initialization ───────────────────────────────────────

function initApp() {
  // Set up navigation
  document.querySelectorAll('.nav-item, .tab-item').forEach(item => {
    item.addEventListener('click', () => {
      const section = item.dataset.section;
      if (section) navigateTo(section);
    });

    item.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        const section = item.dataset.section;
        if (section) navigateTo(section);
      }
    });
  });

  // Initialize connection banner
  initConnectionBanner();

  // Initialize WebSocket
  initWebSocket();

  // Navigate to initial section (from hash or default)
  const hash = location.hash.replace('#', '');
  const initialSection = SECTIONS.includes(hash) ? hash : 'inventory';
  navigateTo(initialSection);

  // Initialize inventory immediately (it's the default section)
  if (window.inventoryModule) {
    initInventory();
  }
}

// Start the app when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initApp);
} else {
  initApp();
}

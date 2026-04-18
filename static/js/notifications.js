/**
 * Fridge Observer — Notifications & History
 * notifications.js
 */

const ACTION_ICONS = {
  added: '➕',
  removed: '➖',
  updated: '✏️',
  expired: '⚠️',
};

/** Fetch activity log */
async function fetchActivityLog() {
  const res = await fetch('/api/notifications/activity-log?limit=50');
  if (!res.ok) throw new Error('Failed to fetch activity log');
  return res.json();
}

/** Fetch weekly report */
async function fetchWeeklyReport() {
  const res = await fetch('/api/notifications/weekly-report');
  if (!res.ok) throw new Error('Failed to fetch weekly report');
  return res.json();
}

/** Fetch streak */
async function fetchStreak() {
  const res = await fetch('/api/notifications/streak');
  if (!res.ok) throw new Error('Failed to fetch streak');
  return res.json();
}

/** Format a datetime string */
function formatDateTime(dateStr) {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    return d.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return dateStr;
  }
}

/** Render the activity log */
function renderActivityLog(entries) {
  const container = document.getElementById('activity-log');
  if (!container) return;

  if (!entries || entries.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">📋</div>
        <div class="empty-state-title">No activity yet</div>
        <div class="empty-state-text">Your fridge activity will appear here as items are added and removed.</div>
      </div>
    `;
    return;
  }

  container.innerHTML = entries.map(entry => `
    <div class="log-entry">
      <div class="log-icon ${entry.action}" aria-hidden="true">
        ${ACTION_ICONS[entry.action] || '•'}
      </div>
      <div class="log-content">
        <div class="log-item-name">${escapeHtml(entry.item_name)}</div>
        <div class="log-meta">
          <span class="action-badge ${entry.action}">${entry.action}</span>
          <span class="log-source">${entry.source}</span>
          <span class="log-timestamp mono">${formatDateTime(entry.occurred_at)}</span>
        </div>
      </div>
    </div>
  `).join('');
}

/** Render the waste report */
function renderWasteReport(report) {
  const container = document.getElementById('waste-report');
  if (!container) return;

  const { expired_count, consumed_count, prev_week_expired_count, prev_week_consumed_count } = report;

  const expiredChange = expired_count - (prev_week_expired_count || 0);
  const consumedChange = consumed_count - (prev_week_consumed_count || 0);

  container.innerHTML = `
    <div class="waste-comparison">
      <div class="waste-stat expired-stat">
        <div class="waste-stat-number">${expired_count}</div>
        <div class="waste-stat-label">Expired this week</div>
      </div>
      <div class="waste-stat consumed-stat">
        <div class="waste-stat-number">${consumed_count}</div>
        <div class="waste-stat-label">Consumed this week</div>
      </div>
    </div>
    <div class="waste-prev-week">
      vs last week: ${prev_week_expired_count} expired, ${prev_week_consumed_count} consumed
    </div>
  `;
}

/** Render the streak */
function renderStreak(data) {
  const container = document.getElementById('streak-display');
  if (!container) return;

  if (!data.gamification_enabled) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">🎮</div>
        <div class="empty-state-title">Gamification disabled</div>
        <div class="empty-state-text">Enable gamification in Settings to track your zero-waste streak.</div>
      </div>
    `;
    return;
  }

  container.innerHTML = `
    <div class="streak-card">
      <span class="streak-icon" aria-hidden="true">🌿</span>
      <div class="streak-number">${data.streak}</div>
      <div class="streak-label">Week${data.streak !== 1 ? 's' : ''} Zero-Waste Streak</div>
      <div class="streak-message">${data.message || ''}</div>
    </div>
  `;
}

/** Initialize the notifications section */
async function initNotifications() {
  // Load all data
  try {
    const [log, report, streak] = await Promise.all([
      fetchActivityLog(),
      fetchWeeklyReport(),
      fetchStreak(),
    ]);
    renderActivityLog(log);
    renderWasteReport(report);
    renderStreak(streak);
  } catch (err) {
    console.error('Failed to load notifications:', err);
  }
}

window.notificationsModule = { initNotifications, renderActivityLog };

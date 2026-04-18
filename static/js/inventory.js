/**
 * Fridge Observer — Inventory Dashboard
 * inventory.js
 */

const CATEGORY_EMOJIS = {
  fruits: '🍎',
  vegetables: '🥦',
  dairy: '🧀',
  beverages: '🥤',
  meat: '🥩',
  packaged_goods: '📦',
};

const CATEGORY_LABELS = {
  fruits: 'Fruits',
  vegetables: 'Vegetables',
  dairy: 'Dairy',
  beverages: 'Beverages',
  meat: 'Meat',
  packaged_goods: 'Packaged',
};

let _currentFilters = {
  category: null,
  sort_by: 'added_at',
  sort_dir: 'desc',
  expiry_before: null,
  expiry_after: null,
};

let _editingItemId = null;

/** Fetch inventory from the API */
async function fetchInventory(filters = {}) {
  const params = new URLSearchParams();
  if (filters.category) params.set('category', filters.category);
  if (filters.sort_by) params.set('sort_by', filters.sort_by);
  if (filters.sort_dir) params.set('sort_dir', filters.sort_dir);
  if (filters.expiry_before) params.set('expiry_before', filters.expiry_before);
  if (filters.expiry_after) params.set('expiry_after', filters.expiry_after);

  const res = await fetch(`/api/inventory?${params}`);
  if (!res.ok) throw new Error(`Failed to fetch inventory: ${res.status}`);
  return res.json();
}

/** Format a date string for display */
function formatDate(dateStr) {
  if (!dateStr) return 'No expiry';
  try {
    const d = new Date(dateStr + 'T00:00:00');
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return dateStr;
  }
}

/** Render the inventory grid */
function renderInventoryGrid(items) {
  const grid = document.getElementById('inventory-grid');
  const statsEl = document.getElementById('inventory-stats');
  if (!grid) return;

  // Update stats
  if (statsEl) {
    const total = items.length;
    const expiring = items.filter(i => i.expiry_status === 'warning').length;
    const expired = items.filter(i => i.expiry_status === 'expired').length;
    statsEl.innerHTML = `
      <div class="stat-card">
        <div class="stat-number">${total}</div>
        <div class="stat-label">Total Items</div>
      </div>
      <div class="stat-card stat-warning">
        <div class="stat-number">${expiring}</div>
        <div class="stat-label">Expiring Soon</div>
      </div>
      <div class="stat-card stat-expired">
        <div class="stat-number">${expired}</div>
        <div class="stat-label">Expired</div>
      </div>
    `;
  }

  if (items.length === 0) {
    grid.innerHTML = `
      <div class="empty-state" style="grid-column: 1 / -1;">
        <div class="empty-state-icon">🥗</div>
        <div class="empty-state-title">Your fridge is empty</div>
        <div class="empty-state-text">Add items using the quick-add form above, or they'll appear automatically when detected.</div>
      </div>
    `;
    return;
  }

  grid.innerHTML = items.map(item => renderFoodCard(item)).join('');

  // Attach event listeners
  grid.querySelectorAll('.food-card').forEach(card => {
    const id = parseInt(card.dataset.id);
    card.addEventListener('click', (e) => {
      if (!e.target.closest('.food-card-actions')) {
        openEditModal(items.find(i => i.id === id));
      }
    });
  });

  grid.querySelectorAll('.delete-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const id = parseInt(btn.dataset.id);
      deleteItem(id);
    });
  });

  grid.querySelectorAll('.edit-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const id = parseInt(btn.dataset.id);
      openEditModal(items.find(i => i.id === id));
    });
  });
}

/** Render a single food card */
function renderFoodCard(item) {
  const emoji = CATEGORY_EMOJIS[item.category] || '🍽️';
  const statusClass = `status-${item.expiry_status || 'ok'}`;
  const badgeClass = `badge--${item.expiry_status || 'ok'}`;

  let expiryText = '';
  let badgeText = '';

  if (item.expiry_date) {
    expiryText = formatDate(item.expiry_date);
    if (item.expiry_status === 'expired') {
      badgeText = 'Expired';
    } else if (item.expiry_status === 'warning') {
      const days = item.days_until_expiry;
      badgeText = days === 1 ? 'Tomorrow' : `${days}d left`;
    } else {
      const days = item.days_until_expiry;
      badgeText = days !== null ? `${days}d` : 'Fresh';
    }
  } else {
    badgeText = 'No expiry';
    expiryText = 'No expiry date';
  }

  return `
    <div class="food-card ${statusClass}" data-id="${item.id}" role="button" tabindex="0" aria-label="${item.name}">
      <span class="category-icon" aria-hidden="true">${emoji}</span>
      <div class="food-card-name">${escapeHtml(item.name)}</div>
      <div class="food-card-expiry mono">${expiryText}</div>
      <div class="food-card-meta">
        <span class="food-card-quantity">×${item.quantity}</span>
        <span class="badge ${badgeClass}">${badgeText}</span>
      </div>
      <div class="food-card-actions">
        <button class="btn btn-ghost btn-sm edit-btn" data-id="${item.id}" aria-label="Edit ${item.name}">✏️</button>
        <button class="btn btn-ghost btn-sm delete-btn" data-id="${item.id}" aria-label="Delete ${item.name}">🗑️</button>
      </div>
    </div>
  `;
}

/** Open the edit modal with pre-filled data */
function openEditModal(item) {
  if (!item) return;
  _editingItemId = item.id;

  const modal = document.getElementById('edit-modal');
  if (!modal) return;

  document.getElementById('edit-name').value = item.name || '';
  document.getElementById('edit-quantity').value = item.quantity || 1;
  document.getElementById('edit-expiry').value = item.expiry_date || '';
  document.getElementById('edit-category').value = item.category || 'packaged_goods';
  document.getElementById('edit-notes').value = item.notes || '';

  modal.classList.add('open');
}

/** Close the edit modal */
function closeEditModal() {
  const modal = document.getElementById('edit-modal');
  if (modal) modal.classList.remove('open');
  _editingItemId = null;
}

/** Delete an item with confirmation */
async function deleteItem(id) {
  if (!confirm('Remove this item from your fridge?')) return;

  try {
    const res = await fetch(`/api/inventory/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(`Delete failed: ${res.status}`);
    showToast('Item removed', 'success');
    await refreshInventory();
  } catch (err) {
    console.error('Delete error:', err);
    showToast('Failed to remove item', 'error');
  }
}

/** Refresh the inventory display */
async function refreshInventory() {
  try {
    const items = await fetchInventory(_currentFilters);
    renderInventoryGrid(items);
  } catch (err) {
    console.error('Failed to refresh inventory:', err);
  }
}

/** Initialize the inventory section */
function initInventory() {
  // Quick-add form
  const quickAddForm = document.getElementById('quick-add-form');
  if (quickAddForm) {
    quickAddForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const formData = new FormData(quickAddForm);
      const data = {
        name: formData.get('name'),
        category: formData.get('category'),
        quantity: parseInt(formData.get('quantity')) || 1,
        expiry_date: formData.get('expiry_date') || null,
      };

      // Validate
      if (!data.name.trim()) {
        showToast('Please enter an item name', 'error');
        return;
      }

      try {
        const res = await fetch('/api/inventory', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data),
        });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Failed to add item');
        }
        quickAddForm.reset();
        showToast(`${data.name} added to fridge`, 'success');
        await refreshInventory();
      } catch (err) {
        console.error('Add item error:', err);
        showToast(err.message || 'Failed to add item', 'error');
      }
    });
  }

  // Edit modal save
  const editSaveBtn = document.getElementById('edit-save-btn');
  if (editSaveBtn) {
    editSaveBtn.addEventListener('click', async () => {
      if (!_editingItemId) return;

      const patch = {
        name: document.getElementById('edit-name').value.trim(),
        quantity: parseInt(document.getElementById('edit-quantity').value) || 1,
        expiry_date: document.getElementById('edit-expiry').value || null,
        notes: document.getElementById('edit-notes').value.trim() || null,
      };

      try {
        const res = await fetch(`/api/inventory/${_editingItemId}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(patch),
        });
        if (!res.ok) throw new Error('Failed to update item');
        closeEditModal();
        showToast('Item updated', 'success');
        await refreshInventory();
      } catch (err) {
        console.error('Update error:', err);
        showToast('Failed to update item', 'error');
      }
    });
  }

  // Edit modal close
  document.getElementById('edit-modal-close')?.addEventListener('click', closeEditModal);
  document.getElementById('edit-cancel-btn')?.addEventListener('click', closeEditModal);
  document.getElementById('edit-modal')?.addEventListener('click', (e) => {
    if (e.target.id === 'edit-modal') closeEditModal();
  });

  // Category filter chips
  document.querySelectorAll('.category-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const cat = chip.dataset.category;
      document.querySelectorAll('.category-chip').forEach(c => c.classList.remove('active'));

      if (_currentFilters.category === cat) {
        _currentFilters.category = null;
      } else {
        _currentFilters.category = cat;
        chip.classList.add('active');
      }
      refreshInventory();
    });
  });

  // Sort controls
  const sortSelect = document.getElementById('sort-by-select');
  if (sortSelect) {
    sortSelect.addEventListener('change', () => {
      _currentFilters.sort_by = sortSelect.value;
      refreshInventory();
    });
  }

  const sortDirSelect = document.getElementById('sort-dir-select');
  if (sortDirSelect) {
    sortDirSelect.addEventListener('change', () => {
      _currentFilters.sort_dir = sortDirSelect.value;
      refreshInventory();
    });
  }

  // Initial load
  refreshInventory();
}

// Expose for WebSocket updates
window.inventoryModule = {
  renderInventoryGrid,
  refreshInventory,
};

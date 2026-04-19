/**
 * Fridge Observer — Recipe Section
 * recipes.js
 */

// ── Image load queue ──────────────────────────────────────────
// Loads recipe images one at a time to avoid HF rate limits
const _imageQueue = [];
let _imageQueueRunning = false;

function queueImageLoad(imgEl, url) {
  _imageQueue.push({ imgEl, url });
  if (!_imageQueueRunning) _processImageQueue();
}

async function _processImageQueue() {
  if (_imageQueue.length === 0) { _imageQueueRunning = false; return; }
  _imageQueueRunning = true;

  const { imgEl, url } = _imageQueue.shift();

  // Skip if element no longer in DOM
  if (!document.contains(imgEl)) {
    _processImageQueue();
    return;
  }

  // Get placeholder before loading
  const placeholder = imgEl.parentElement?.querySelector('.recipe-img-placeholder');

  try {
    const res = await fetch(url, { credentials: 'include' });
    if (res.ok) {
      const blob = await res.blob();
      imgEl.src = URL.createObjectURL(blob);
      imgEl.classList.add('loaded');
    } else {
      console.warn('Recipe image failed to load:', url, res.status);
      imgEl.dispatchEvent(new Event('error'));
    }
  } catch (err) {
    console.error('Recipe image error:', url, err);
    imgEl.dispatchEvent(new Event('error'));
  }
  
  // ALWAYS hide the loading placeholder after attempt
  if (placeholder) {
    placeholder.style.display = 'none';
  }

  // Small delay between requests to avoid rate limiting
  await new Promise(r => setTimeout(r, 500));
  _processImageQueue();
}

// ── Filters state ─────────────────────────────────────────────
let _recipeFilters = {
  dietary: null,
  cuisine: null,
  max_prep_minutes: null,
  favorites_only: false,
};

async function fetchRecipes(filters = {}) {
  const params = new URLSearchParams();
  if (filters.dietary) params.set('dietary', filters.dietary);
  if (filters.cuisine) params.set('cuisine', filters.cuisine);
  if (filters.max_prep_minutes) params.set('max_prep_minutes', filters.max_prep_minutes);
  if (filters.favorites_only) params.set('favorites_only', 'true');

  const res = await fetch(`/api/recipes?${params}`, { credentials: 'include' });
  if (!res.ok) throw new Error(`Failed to fetch recipes: ${res.status}`);
  return res.json();
}

function getUrgencyLevel(score) {
  if (score >= 1.5) return 'high';
  if (score >= 0.5) return 'medium';
  return 'low';
}

// ── Cuisine icon (SVG-based, no emoji) ────────────────────────
function getCuisineIcon(cuisine) {
  const icons = {
    Italian: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/><path d="M8 12h8M12 8v8"/></svg>`,
    Asian: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>`,
    default: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 11l19-9-9 19-2-8-8-2z"/></svg>`,
  };
  return icons[cuisine] || icons.default;
}

// ── Render recipe cards ───────────────────────────────────────
function renderRecipeCards(scoredRecipes) {
  const grid = document.getElementById('recipe-grid');
  if (!grid) return;

  if (scoredRecipes.length === 0) {
    grid.innerHTML = `
      <div class="empty-state" style="grid-column: 1 / -1;">
        <div class="empty-state-title">No recipes found</div>
        <div class="empty-state-text">Add more items to your fridge to unlock recipe suggestions.</div>
      </div>
    `;
    return;
  }

  grid.innerHTML = scoredRecipes.map(sr => renderRecipeCard(sr)).join('');

  // Queue image loads sequentially
  grid.querySelectorAll('.recipe-flux-img[data-src]').forEach(img => {
    const url = img.dataset.src;
    img.removeAttribute('data-src');
    queueImageLoad(img, url);
  });

  // Event listeners
  grid.querySelectorAll('.heart-btn').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      await toggleFavorite(parseInt(btn.dataset.id), btn.classList.contains('favorited'), btn);
    });
  });

  grid.querySelectorAll('.made-this-btn').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      await madeThis(parseInt(btn.dataset.id), btn.dataset.name);
    });
  });

  // Click on card body opens detail modal
  grid.querySelectorAll('.recipe-card').forEach(card => {
    card.addEventListener('click', (e) => {
      if (e.target.closest('.recipe-actions')) return;
      const id = parseInt(card.dataset.id);
      const name = card.dataset.name;
      openRecipeModal(id, name);
    });
    card.style.cursor = 'pointer';
  });
}

function renderRecipeCard(scoredRecipe) {
  const { recipe, urgency_score, matching_expiring_items } = scoredRecipe;
  const urgencyLevel = getUrgencyLevel(urgency_score);
  const scoreDisplay = urgency_score > 0 ? urgency_score.toFixed(1) : null;

  const tagsHtml = (recipe.dietary_tags || []).map(tag =>
    `<span class="recipe-tag">${escapeHtml(tag)}</span>`
  ).join('');

  const expiringHtml = matching_expiring_items?.length ? `
    <div class="expiring-ingredients">
      <span class="expiring-label">Uses expiring:</span>
      ${matching_expiring_items.map(n => `<span class="expiring-ingredient-item">${escapeHtml(n)}</span>`).join('')}
    </div>
  ` : '';

  const metaItems = [
    recipe.prep_minutes ? `${recipe.prep_minutes} min` : null,
    recipe.cuisine || null,
  ].filter(Boolean).map(t => `<span class="recipe-meta-item">${escapeHtml(t)}</span>`).join('');

  // Use data-src for lazy sequential loading
  const imgUrl = `/api/ai/recipe-image?name=${encodeURIComponent(recipe.name)}&cuisine=${encodeURIComponent(recipe.cuisine || '')}`;

  return `
    <div class="recipe-card" data-id="${recipe.id}" data-name="${escapeHtml(recipe.name)}">
      <div class="recipe-image-area flux-image-area">
        <img
          data-src="${imgUrl}"
          alt="${escapeHtml(recipe.name)}"
          class="recipe-flux-img"
          src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='1' height='1'%3E%3C/svg%3E"
        />
        <div class="recipe-img-placeholder">
          <div class="recipe-img-placeholder-icon">${getCuisineIcon(recipe.cuisine)}</div>
        </div>
        ${scoreDisplay ? `<div class="urgency-badge ${urgencyLevel}">${scoreDisplay}</div>` : ''}
      </div>
      <div class="recipe-content">
        <div class="recipe-name">${escapeHtml(recipe.name)}</div>
        ${recipe.description ? `<div class="recipe-description">${escapeHtml(recipe.description)}</div>` : ''}
        ${metaItems ? `<div class="recipe-meta">${metaItems}</div>` : ''}
        ${tagsHtml ? `<div class="recipe-tags">${tagsHtml}</div>` : ''}
        ${expiringHtml}
      </div>
      <div class="recipe-actions">
        <button class="heart-btn ${recipe.is_favorite ? 'favorited' : ''}"
                data-id="${recipe.id}"
                aria-label="${recipe.is_favorite ? 'Remove from favorites' : 'Save recipe'}">
          <svg viewBox="0 0 24 24" fill="${recipe.is_favorite ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2" width="16" height="16">
            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
          </svg>
        </button>
        <button class="btn btn-primary btn-sm made-this-btn"
                data-id="${recipe.id}"
                data-name="${escapeHtml(recipe.name)}">
          Made This
        </button>
      </div>
    </div>
  `;
}

async function toggleFavorite(id, isFav, btn) {
  try {
    const res = await fetch(`/api/recipes/${id}/favorite`, {
      method: isFav ? 'DELETE' : 'POST',
      credentials: 'include',
    });
    if (!res.ok) throw new Error();
    btn.classList.toggle('favorited');
    const isFavNow = btn.classList.contains('favorited');
    btn.querySelector('svg path').setAttribute('fill', isFavNow ? 'currentColor' : 'none');
    btn.setAttribute('aria-label', isFavNow ? 'Remove from favorites' : 'Save recipe');
    showToast(isFavNow ? 'Recipe saved' : 'Recipe removed', 'success');
  } catch {
    showToast('Failed to update favorite', 'error');
  }
}

async function madeThis(id, name) {
  if (!confirm(`Mark "${name}" as made? Used ingredients will be removed from your fridge.`)) return;
  try {
    const res = await fetch(`/api/recipes/${id}/made-this`, { method: 'POST', credentials: 'include' });
    if (!res.ok) throw new Error();
    const data = await res.json();
    const removed = data.removed_items || [];
    showToast(removed.length ? `Removed: ${removed.join(', ')}` : `Marked as made`, 'success');
    if (window.inventoryModule) await window.inventoryModule.refreshInventory();
  } catch {
    showToast('Failed to process recipe', 'error');
  }
}

async function refreshRecipes() {
  const grid = document.getElementById('recipe-grid');
  if (grid) grid.innerHTML = '<div class="loading-container"><div class="spinner spinner-lg"></div></div>';
  try {
    const recipes = await fetchRecipes(_recipeFilters);
    renderRecipeCards(recipes);
  } catch {
    if (grid) grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1;"><div class="empty-state-title">Failed to load recipes</div></div>`;
  }
}

// ── Recipe Detail Modal ───────────────────────────────────────

let _currentRecipeId = null;

async function openRecipeModal(id, name) {
  _currentRecipeId = id;
  const modal = document.getElementById('recipe-modal');
  const title = document.getElementById('recipe-modal-title');
  const body = document.getElementById('recipe-modal-body');
  if (!modal || !body) return;

  title.textContent = name;
  body.innerHTML = `<div class="loading-container" style="padding:40px;"><div class="spinner spinner-lg"></div><p style="margin-top:12px;color:var(--color-text-muted);font-size:13px;">Loading recipe details...</p></div>`;
  modal.style.display = 'flex';
  modal.classList.add('open');
  document.body.style.overflow = 'hidden';

  try {
    const res = await fetch(`/api/recipes/${id}/detail`, { credentials: 'include' });
    if (!res.ok) throw new Error();
    const data = await res.json();
    renderRecipeModal(data);
  } catch {
    body.innerHTML = `<div class="empty-state"><div class="empty-state-title">Could not load recipe details</div></div>`;
  }
}

function renderRecipeModal(data) {
  const body = document.getElementById('recipe-modal-body');
  const title = document.getElementById('recipe-modal-title');
  if (!body) return;

  title.textContent = data.name;

  const imgUrl = `/api/ai/recipe-image?name=${encodeURIComponent(data.name)}&cuisine=${encodeURIComponent(data.cuisine || '')}`;

  const metaHtml = [
    data.prep_minutes ? `<div class="recipe-detail-meta-item"><strong>${data.prep_minutes} min</strong> prep</div>` : '',
    data.servings ? `<div class="recipe-detail-meta-item"><strong>${data.servings}</strong> servings</div>` : '',
    data.cuisine ? `<div class="recipe-detail-meta-item"><strong>${escapeHtml(data.cuisine)}</strong></div>` : '',
  ].filter(Boolean).join('');

  const tagsHtml = (data.dietary_tags || []).length ? `
    <div class="recipe-detail-tags">
      ${data.dietary_tags.map(t => `<span class="recipe-tag">${escapeHtml(t)}</span>`).join('')}
    </div>
  ` : '';

  const ingredientsHtml = (data.ingredients || []).map(ing => {
    const qty = data.quantities?.[ing.name] || data.quantities?.[ing.name.toLowerCase()] || '';
    const isExpiring = ing.expiry_status === 'warning' || ing.expiry_status === 'expired';
    const isPantry = ing.is_pantry_staple;
    const cls = isExpiring ? 'expiring' : isPantry ? 'pantry' : '';
    return `
      <div class="recipe-ingredient-row ${cls}">
        <span class="recipe-ingredient-name">${escapeHtml(ing.name)}${isPantry ? ' <span style="font-size:11px;color:var(--color-text-muted)">(pantry)</span>' : ''}</span>
        <span class="recipe-ingredient-qty">${escapeHtml(qty || '—')}</span>
      </div>
    `;
  }).join('');

  const stepsHtml = (data.steps || []).map((step, i) => `
    <div class="recipe-step">
      <div class="recipe-step-num">${i + 1}</div>
      <div class="recipe-step-text">${escapeHtml(step)}</div>
    </div>
  `).join('');

  body.innerHTML = `
    <div class="recipe-detail-img-container" id="recipe-modal-img-container">
      <div class="recipe-detail-img-placeholder">
        <div class="recipe-img-placeholder-icon">${getCuisineIcon(data.cuisine)}</div>
      </div>
    </div>

    ${data.description ? `<p style="font-size:14px;color:var(--color-text-secondary);margin-bottom:var(--space-4);line-height:1.6;">${escapeHtml(data.description)}</p>` : ''}

    <div class="recipe-detail-meta">${metaHtml}</div>
    ${tagsHtml}

    <div class="recipe-detail-section">
      <div class="recipe-detail-section-title">Ingredients</div>
      <div class="recipe-ingredients-list">${ingredientsHtml}</div>
      <p style="font-size:11.5px;color:var(--color-text-muted);margin-top:8px;">Items with amber border are expiring soon in your fridge.</p>
    </div>

    <div class="recipe-detail-section">
      <div class="recipe-detail-section-title">Instructions</div>
      <div class="recipe-instructions-list">${stepsHtml}</div>
    </div>
  `;

  // Load image after DOM is set — avoids onerror on blank placeholder
  const imgContainer = document.getElementById('recipe-modal-img-container');
  if (imgContainer) {
    fetch(imgUrl, { credentials: 'include' })
      .then(r => r.ok ? r.blob() : null)
      .then(blob => {
        if (blob && imgContainer) {
          const url = URL.createObjectURL(blob);
          imgContainer.innerHTML = `<img src="${url}" alt="${escapeHtml(data.name)}" class="recipe-detail-hero" />`;
        }
      })
      .catch(() => {});
  }
}

function closeRecipeModal() {
  const modal = document.getElementById('recipe-modal');
  if (modal) {
    modal.style.display = 'none';
    modal.classList.remove('open');
  }
  document.body.style.overflow = '';
  _currentRecipeId = null;
}

function initRecipeModal() {
  document.getElementById('recipe-modal-close')?.addEventListener('click', closeRecipeModal);
  document.getElementById('recipe-modal-cancel')?.addEventListener('click', closeRecipeModal);
  document.getElementById('recipe-modal')?.addEventListener('click', (e) => {
    if (e.target.id === 'recipe-modal') closeRecipeModal();
  });
  document.getElementById('recipe-modal-made-this')?.addEventListener('click', async () => {
    if (!_currentRecipeId) return;
    const title = document.getElementById('recipe-modal-title')?.textContent || '';
    closeRecipeModal();
    await madeThis(_currentRecipeId, title);
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeRecipeModal();
  });
}

function initRecipes() {
  document.querySelectorAll('.dietary-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const diet = chip.dataset.dietary;
      document.querySelectorAll('.dietary-chip').forEach(c => c.classList.remove('active'));
      _recipeFilters.dietary = _recipeFilters.dietary === diet ? null : diet;
      if (_recipeFilters.dietary) chip.classList.add('active');
      refreshRecipes();
    });
  });

  const cuisineSelect = document.getElementById('cuisine-filter');
  if (cuisineSelect) {
    cuisineSelect.addEventListener('change', () => {
      _recipeFilters.cuisine = cuisineSelect.value || null;
      refreshRecipes();
    });
  }

  const prepSlider = document.getElementById('prep-time-slider');
  const prepLabel = document.getElementById('prep-time-label');
  if (prepSlider) {
    prepSlider.addEventListener('input', () => {
      const val = parseInt(prepSlider.value);
      _recipeFilters.max_prep_minutes = val < parseInt(prepSlider.max) ? val : null;
      if (prepLabel) prepLabel.textContent = _recipeFilters.max_prep_minutes ? `${val} min` : 'Any';
      refreshRecipes();
    });
  }

  const favToggle = document.getElementById('favorites-toggle');
  if (favToggle) {
    favToggle.addEventListener('click', () => {
      _recipeFilters.favorites_only = !_recipeFilters.favorites_only;
      favToggle.classList.toggle('active', _recipeFilters.favorites_only);
      refreshRecipes();
    });
  }

  refreshRecipes();
  initRecipeModal();
}

window.recipesModule = { refreshRecipes, initRecipes };

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initRecipes);
} else {
  initRecipes();
}

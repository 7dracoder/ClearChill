/**
 * Fridge Observer — Recipe Section
 * recipes.js
 */

const CUISINE_EMOJIS = {
  Italian: '🍝',
  Asian: '🍜',
  Mexican: '🌮',
  Indian: '🍛',
  French: '🥐',
  Mediterranean: '🫒',
  American: '🥞',
  Modern: '🥑',
  Tropical: '🥭',
  default: '🍳',
};

let _recipeFilters = {
  dietary: null,
  cuisine: null,
  max_prep_minutes: null,
  favorites_only: false,
};

/** Fetch recipes from the API */
async function fetchRecipes(filters = {}) {
  const params = new URLSearchParams();
  if (filters.dietary) params.set('dietary', filters.dietary);
  if (filters.cuisine) params.set('cuisine', filters.cuisine);
  if (filters.max_prep_minutes) params.set('max_prep_minutes', filters.max_prep_minutes);
  if (filters.favorites_only) params.set('favorites_only', 'true');

  const res = await fetch(`/api/recipes?${params}`);
  if (!res.ok) throw new Error(`Failed to fetch recipes: ${res.status}`);
  return res.json();
}

/** Get urgency level from score */
function getUrgencyLevel(score) {
  if (score >= 1.5) return 'high';
  if (score >= 0.5) return 'medium';
  return 'low';
}

/** Render recipe cards */
function renderRecipeCards(scoredRecipes) {
  const grid = document.getElementById('recipe-grid');
  if (!grid) return;

  if (scoredRecipes.length === 0) {
    grid.innerHTML = `
      <div class="empty-state" style="grid-column: 1 / -1;">
        <div class="empty-state-icon">🍽️</div>
        <div class="empty-state-title">No recipes found</div>
        <div class="empty-state-text">Try adjusting your filters, or add more items to your fridge to unlock recipe suggestions.</div>
      </div>
    `;
    return;
  }

  grid.innerHTML = scoredRecipes.map(sr => renderRecipeCard(sr)).join('');

  // Attach event listeners
  grid.querySelectorAll('.heart-btn').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const id = parseInt(btn.dataset.id);
      const isFav = btn.classList.contains('favorited');
      await toggleFavorite(id, isFav, btn);
    });
  });

  grid.querySelectorAll('.made-this-btn').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const id = parseInt(btn.dataset.id);
      const name = btn.dataset.name;
      await madeThis(id, name);
    });
  });
}

/** Render a single recipe card */
function renderRecipeCard(scoredRecipe) {
  const { recipe, urgency_score, matching_expiring_items } = scoredRecipe;
  const emoji = CUISINE_EMOJIS[recipe.cuisine] || CUISINE_EMOJIS.default;
  const urgencyLevel = getUrgencyLevel(urgency_score);
  const scoreDisplay = urgency_score > 0 ? urgency_score.toFixed(1) : '0';

  const tagsHtml = (recipe.dietary_tags || []).map(tag =>
    `<span class="recipe-tag ${tag.replace(/\s+/g, '-').toLowerCase()}">${tag}</span>`
  ).join('');

  const expiringHtml = matching_expiring_items && matching_expiring_items.length > 0 ? `
    <div class="expiring-ingredients">
      <div class="expiring-ingredients-title">🕐 Uses expiring items</div>
      ${matching_expiring_items.map(name =>
        `<div class="expiring-ingredient-item">${escapeHtml(name)}</div>`
      ).join('')}
    </div>
  ` : '';

  const prepTime = recipe.prep_minutes ? `⏱ ${recipe.prep_minutes} min` : '';
  const cuisine = recipe.cuisine ? `🌍 ${recipe.cuisine}` : '';

  return `
    <div class="recipe-card">
      <div class="recipe-image-area">
        <span aria-hidden="true">${emoji}</span>
        ${urgency_score > 0 ? `
          <div class="urgency-badge ${urgencyLevel}">
            🔥 ${scoreDisplay}
          </div>
        ` : ''}
      </div>
      <div class="recipe-content">
        <div class="recipe-name">${escapeHtml(recipe.name)}</div>
        ${recipe.description ? `<div class="recipe-description">${escapeHtml(recipe.description)}</div>` : ''}
        <div class="recipe-meta">
          ${prepTime ? `<span class="recipe-meta-item">${prepTime}</span>` : ''}
          ${cuisine ? `<span class="recipe-meta-item">${cuisine}</span>` : ''}
        </div>
        ${tagsHtml ? `<div class="recipe-tags">${tagsHtml}</div>` : ''}
        ${expiringHtml}
      </div>
      <div class="recipe-actions">
        <button class="heart-btn ${recipe.is_favorite ? 'favorited' : ''}" 
                data-id="${recipe.id}" 
                aria-label="${recipe.is_favorite ? 'Remove from favorites' : 'Add to favorites'}"
                title="${recipe.is_favorite ? 'Remove from favorites' : 'Save recipe'}">
        </button>
        <button class="btn btn-primary btn-sm made-this-btn flex-1" 
                data-id="${recipe.id}" 
                data-name="${escapeHtml(recipe.name)}">
          ✓ I Made This
        </button>
      </div>
    </div>
  `;
}

/** Toggle favorite status */
async function toggleFavorite(id, isFav, btn) {
  try {
    const method = isFav ? 'DELETE' : 'POST';
    const res = await fetch(`/api/recipes/${id}/favorite`, { method });
    if (!res.ok) throw new Error('Failed to update favorite');

    btn.classList.toggle('favorited');
    const label = btn.classList.contains('favorited') ? 'Remove from favorites' : 'Add to favorites';
    btn.setAttribute('aria-label', label);

    showToast(
      btn.classList.contains('favorited') ? 'Recipe saved to favorites' : 'Recipe removed from favorites',
      'success'
    );
  } catch (err) {
    console.error('Favorite error:', err);
    showToast('Failed to update favorite', 'error');
  }
}

/** Handle "I Made This" */
async function madeThis(id, name) {
  if (!confirm(`Mark "${name}" as made? This will remove the used ingredients from your fridge.`)) return;

  try {
    const res = await fetch(`/api/recipes/${id}/made-this`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to process');
    const data = await res.json();

    const removed = data.removed_items || [];
    const msg = removed.length > 0
      ? `Great cooking! Removed: ${removed.join(', ')}`
      : `Marked "${name}" as made!`;
    showToast(msg, 'success');

    // Refresh inventory
    if (window.inventoryModule) {
      await window.inventoryModule.refreshInventory();
    }
  } catch (err) {
    console.error('Made this error:', err);
    showToast('Failed to process recipe', 'error');
  }
}

/** Refresh recipes */
async function refreshRecipes() {
  const grid = document.getElementById('recipe-grid');
  if (grid) {
    grid.innerHTML = '<div class="loading-container"><div class="spinner spinner-lg"></div></div>';
  }

  try {
    const recipes = await fetchRecipes(_recipeFilters);
    renderRecipeCards(recipes);
  } catch (err) {
    console.error('Failed to load recipes:', err);
    if (grid) {
      grid.innerHTML = `
        <div class="empty-state" style="grid-column: 1 / -1;">
          <div class="empty-state-icon">⚠️</div>
          <div class="empty-state-title">Failed to load recipes</div>
          <div class="empty-state-text">Please check your connection and try again.</div>
        </div>
      `;
    }
  }
}

/** Initialize the recipes section */
function initRecipes() {
  // Dietary filter chips
  document.querySelectorAll('.dietary-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const diet = chip.dataset.dietary;
      document.querySelectorAll('.dietary-chip').forEach(c => c.classList.remove('active'));

      if (_recipeFilters.dietary === diet) {
        _recipeFilters.dietary = null;
      } else {
        _recipeFilters.dietary = diet;
        chip.classList.add('active');
      }
      refreshRecipes();
    });
  });

  // Cuisine filter
  const cuisineSelect = document.getElementById('cuisine-filter');
  if (cuisineSelect) {
    cuisineSelect.addEventListener('change', () => {
      _recipeFilters.cuisine = cuisineSelect.value || null;
      refreshRecipes();
    });
  }

  // Prep time slider
  const prepSlider = document.getElementById('prep-time-slider');
  const prepLabel = document.getElementById('prep-time-label');
  if (prepSlider) {
    prepSlider.addEventListener('input', () => {
      const val = parseInt(prepSlider.value);
      _recipeFilters.max_prep_minutes = val < parseInt(prepSlider.max) ? val : null;
      if (prepLabel) {
        prepLabel.textContent = _recipeFilters.max_prep_minutes ? `≤${val} min` : 'Any';
      }
      refreshRecipes();
    });
  }

  // Favorites toggle
  const favToggle = document.getElementById('favorites-toggle');
  if (favToggle) {
    favToggle.addEventListener('click', () => {
      _recipeFilters.favorites_only = !_recipeFilters.favorites_only;
      favToggle.classList.toggle('active', _recipeFilters.favorites_only);
      refreshRecipes();
    });
  }

  // Initial load
  refreshRecipes();
}

window.recipesModule = { refreshRecipes };

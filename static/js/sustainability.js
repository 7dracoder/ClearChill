/**
 * Fridge Observer — EcoScan (Sustainability Blueprint)
 * sustainability.js
 */

window.sustainabilityModule = (() => {

  let _items = [];
  let _selectedItem = null;
  let _activeTab = 'full';
  let _isStreaming = false;
  let _initialized = false;

  // ── Init ──────────────────────────────────────────────────

  async function initSustainability() {
    if (_initialized) { await refreshItems(); return; }
    _initialized = true;
    const container = document.getElementById('sustainability-content');
    if (!container) return;
    container.innerHTML = renderShell();
    bindEvents();
    await refreshItems();
  }

  async function refreshItems() {
    try {
      const res = await fetch('/api/sustainability/inventory-items', { credentials: 'include' });
      if (!res.ok) throw new Error();
      _items = await res.json();
      renderItemList();
    } catch {}
  }

  // ── Shell ─────────────────────────────────────────────────

  function renderShell() {
    return `
      <div class="sus-layout">
        <div class="sus-sidebar">
          <div class="sus-sidebar-header">
            <div class="sus-sidebar-title">🥦 Your Fridge Items</div>
            <div class="sus-sidebar-sub">Select a product to scan</div>
          </div>
          <div class="sus-search-wrap">
            <input type="text" id="sus-search" class="sus-search" placeholder="Search products..." autocomplete="off" />
          </div>
          <div id="sus-item-list" class="sus-item-list">
            <div class="sus-empty">Add items to your inventory to scan them here.</div>
          </div>
          <div class="sus-manual-wrap">
            <div class="sus-manual-label">Or type any product:</div>
            <div class="sus-manual-row">
              <input type="text" id="sus-manual-input" class="sus-manual-input" placeholder="e.g. Coca-Cola, Chicken..." />
              <button class="btn btn-primary sus-manual-btn" id="sus-manual-btn">Scan</button>
            </div>
          </div>
        </div>

        <div class="sus-main">
          <div id="sus-welcome" class="sus-welcome">
            <div class="sus-welcome-icon">🌿</div>
            <h3>EcoScan — Product Sustainability</h3>
            <p>Select any product from your fridge or type one manually to get a full sustainability report — CO₂ impact, eco-friendly alternatives, and a redesign blueprint.</p>
            <div class="sus-welcome-chips">
              <span class="sus-example-chip" data-name="Milk" data-cat="dairy">🥛 Milk</span>
              <span class="sus-example-chip" data-name="Chicken breast" data-cat="meat">🍗 Chicken</span>
              <span class="sus-example-chip" data-name="Coca-Cola" data-cat="beverages">🥤 Coca-Cola</span>
              <span class="sus-example-chip" data-name="Strawberries" data-cat="fruits">🍓 Strawberries</span>
              <span class="sus-example-chip" data-name="Cheddar cheese" data-cat="dairy">🧀 Cheddar</span>
            </div>
          </div>

          <div id="sus-analysis" class="sus-analysis" style="display:none;">
            <div class="sus-analysis-header">
              <div class="sus-product-badge" id="sus-product-badge"></div>
              <div class="sus-analysis-tabs">
                <button class="sus-tab active" data-tab="full">📊 Full Report</button>
                <button class="sus-tab" data-tab="co2">💨 CO₂</button>
                <button class="sus-tab" data-tab="alternatives">♻️ Alternatives</button>
                <button class="sus-tab" data-tab="blueprint">🔧 Redesign</button>
              </div>
            </div>
            <div id="sus-output" class="sus-output">
              <div class="sus-loading">
                <div class="sus-loading-dots"><span></span><span></span><span></span></div>
                <div class="sus-loading-text">Scanning product...</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  // ── Item list ─────────────────────────────────────────────

  function renderItemList(filter = '') {
    const list = document.getElementById('sus-item-list');
    if (!list) return;
    const filtered = filter
      ? _items.filter(i => i.name.toLowerCase().includes(filter.toLowerCase()))
      : _items;
    if (filtered.length === 0) {
      list.innerHTML = _items.length === 0
        ? '<div class="sus-empty">Add items to your inventory to scan them here.</div>'
        : '<div class="sus-empty">No items match.</div>';
      return;
    }
    list.innerHTML = filtered.map(item => `
      <div class="sus-item ${_selectedItem?.id === item.id ? 'active' : ''}"
           data-id="${item.id}" data-name="${esc(item.name)}" data-cat="${esc(item.category)}">
        <span class="sus-item-icon">${catEmoji(item.category)}</span>
        <div class="sus-item-info">
          <div class="sus-item-name">${esc(item.name)}</div>
          <div class="sus-item-cat">${fmtCat(item.category)}</div>
        </div>
        <span class="sus-item-arrow">›</span>
      </div>
    `).join('');
  }

  // ── Events ────────────────────────────────────────────────

  function bindEvents() {
    document.getElementById('sus-search')?.addEventListener('input', e => renderItemList(e.target.value));

    document.getElementById('sus-item-list')?.addEventListener('click', e => {
      const item = e.target.closest('.sus-item');
      if (item) selectProduct(item.dataset.name, item.dataset.cat, parseInt(item.dataset.id));
    });

    document.getElementById('sus-manual-btn')?.addEventListener('click', () => {
      const val = document.getElementById('sus-manual-input')?.value.trim();
      if (val) selectProduct(val, null, null);
    });

    document.getElementById('sus-manual-input')?.addEventListener('keydown', e => {
      if (e.key === 'Enter') { const v = e.target.value.trim(); if (v) selectProduct(v, null, null); }
    });

    document.querySelector('.sus-analysis-tabs')?.addEventListener('click', e => {
      const tab = e.target.closest('.sus-tab');
      if (!tab || _isStreaming) return;
      document.querySelectorAll('.sus-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      _activeTab = tab.dataset.tab;
      if (_selectedItem) runAnalysis(_selectedItem.name, _selectedItem.category, _activeTab);
    });

    document.querySelector('.sus-welcome-chips')?.addEventListener('click', e => {
      const chip = e.target.closest('.sus-example-chip');
      if (chip) selectProduct(chip.dataset.name, chip.dataset.cat, null);
    });
  }

  // ── Select product ────────────────────────────────────────

  function selectProduct(name, category, id) {
    _selectedItem = { name, category, id };
    _activeTab = 'full';

    document.querySelectorAll('.sus-item').forEach(el =>
      el.classList.toggle('active', parseInt(el.dataset.id) === id)
    );

    document.getElementById('sus-welcome').style.display = 'none';
    document.getElementById('sus-analysis').style.display = 'flex';

    const badge = document.getElementById('sus-product-badge');
    if (badge) badge.innerHTML = `
      <span class="sus-badge-icon">${catEmoji(category)}</span>
      <div>
        <div class="sus-badge-name">${esc(name)}</div>
        ${category ? `<div class="sus-badge-cat">${fmtCat(category)}</div>` : ''}
      </div>
    `;

    document.querySelectorAll('.sus-tab').forEach(t =>
      t.classList.toggle('active', t.dataset.tab === 'full')
    );

    runAnalysis(name, category, 'full');
  }

  // ── Run analysis ──────────────────────────────────────────

  async function runAnalysis(name, category, focus) {
    const output = document.getElementById('sus-output');
    if (!output || _isStreaming) return;

    _isStreaming = true;
    output.innerHTML = `
      <div class="sus-loading">
        <div class="sus-loading-dots"><span></span><span></span><span></span></div>
        <div class="sus-loading-text">Analysing ${esc(name)}...</div>
      </div>
    `;

    try {
      const res = await fetch('/api/sustainability/analyse-product', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_name: name, category, focus }),
        credentials: 'include',
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const raw = line.slice(6);
          if (raw === '[DONE]') break;
          try {
            const msg = JSON.parse(raw);
            if (msg.type === 'structured') {
              output.innerHTML = renderStructured(msg.focus, msg.data, name, category);
              // Load blueprint image
              if (msg.focus === 'full' || msg.focus === 'blueprint') {
                loadBlueprintImage(name, output);
              }
            } else if (msg.type === 'text') {
              output.innerHTML = `<div class="sus-text">${esc(msg.data)}</div>`;
            } else if (msg.type === 'error') {
              output.innerHTML = `<div class="sus-error">${esc(msg.data)}</div>`;
            }
          } catch {}
        }
      }
    } catch (err) {
      output.innerHTML = `<div class="sus-error">Could not load analysis. Please try again.</div>`;
    } finally {
      _isStreaming = false;
    }
  }

  // ── Blueprint image ───────────────────────────────────────

  async function loadBlueprintImage(productName, container) {
    const imgSection = container.querySelector('.sus-blueprint-img-section');
    if (!imgSection) return;

    imgSection.innerHTML = `<div class="sus-loading" style="padding:20px;"><div class="sus-loading-dots"><span></span><span></span><span></span></div></div>`;

    try {
      const url = `/api/sustainability/blueprint-image?product=${encodeURIComponent(productName)}`;
      imgSection.innerHTML = `
        <div class="sus-blueprint-img-wrap">
          <img src="${url}" alt="Blueprint for ${esc(productName)}" class="sus-blueprint-img" />
          <div class="sus-blueprint-img-label">Product Blueprint Visualisation</div>
        </div>
      `;
    } catch {
      imgSection.innerHTML = '';
    }
  }

  // ── Structured renderers ──────────────────────────────────

  function renderStructured(focus, data, name, category) {
    switch (focus) {
      case 'full':     return renderFull(data, name, category);
      case 'co2':      return renderCO2(data, name);
      case 'alternatives': return renderAlternatives(data, name);
      case 'blueprint': return renderBlueprint(data, name);
      default:         return `<div class="sus-text">${esc(JSON.stringify(data, null, 2))}</div>`;
    }
  }

  function renderFull(d, name, category) {
    const score = d.impact_score || 5;
    const scoreColor = score <= 3 ? 'var(--color-ok)' : score <= 6 ? 'var(--color-warning)' : 'var(--color-expired)';
    const scoreLabel = score <= 3 ? 'Low Impact' : score <= 6 ? 'Moderate Impact' : 'High Impact';

    return `
      <div class="sus-structured">

        <!-- Score hero -->
        <div class="sus-score-hero">
          <div class="sus-score-ring" style="--score-color:${scoreColor};">
            <div class="sus-score-number">${score}</div>
            <div class="sus-score-max">/10</div>
          </div>
          <div class="sus-score-info">
            <div class="sus-score-label" style="color:${scoreColor};">${scoreLabel}</div>
            <div class="sus-score-sub">Environmental Impact Score</div>
            <div class="sus-score-verdict">${esc(d.verdict || '')}</div>
          </div>
        </div>

        <!-- Key metrics -->
        <div class="sus-metrics-grid">
          ${metricCard('💨', 'CO₂ per unit', d.co2_per_unit || '—')}
          ${metricCard('💧', 'Water usage', d.water_usage || '—')}
          ${metricCard('📦', 'Packaging', d.packaging_rating || '—')}
          ${metricCard('🚚', 'Food miles', d.food_miles || '—')}
        </div>

        <!-- Key facts -->
        ${d.key_facts && d.key_facts.length ? `
          <div class="sus-section">
            <div class="sus-section-title">📌 Key Facts</div>
            <ul class="sus-fact-list">
              ${d.key_facts.map(f => `<li>${esc(f)}</li>`).join('')}
            </ul>
          </div>
        ` : ''}

        <!-- Alternatives -->
        ${d.alternatives && d.alternatives.length ? `
          <div class="sus-section">
            <div class="sus-section-title">♻️ Sustainable Alternatives</div>
            <div class="sus-alt-list">
              ${d.alternatives.map(a => `
                <div class="sus-alt-card">
                  <div class="sus-alt-name">✓ ${esc(a.name)}</div>
                  <div class="sus-alt-saving">${esc(a.co2_saving || '')}</div>
                  <div class="sus-alt-reason">${esc(a.reason || '')}</div>
                </div>
              `).join('')}
            </div>
          </div>
        ` : ''}

        <!-- Blueprint summary -->
        ${d.blueprint ? `
          <div class="sus-section">
            <div class="sus-section-title">🔧 Redesign Blueprint</div>
            <div class="sus-blueprint-grid">
              ${blueprintRow('📦', 'Packaging', d.blueprint.packaging)}
              ${blueprintRow('🌾', 'Sourcing', d.blueprint.sourcing)}
              ${blueprintRow('🏭', 'Production', d.blueprint.production)}
              ${blueprintRow('♻️', 'End of Life', d.blueprint.end_of_life)}
            </div>
          </div>
        ` : ''}

        <!-- Blueprint image placeholder -->
        <div class="sus-section sus-blueprint-img-section"></div>

      </div>
    `;
  }

  function renderCO2(d, name) {
    return `
      <div class="sus-structured">
        <div class="sus-section">
          <div class="sus-section-title">💨 Carbon Footprint — ${esc(name)}</div>
          <div class="sus-metrics-grid">
            ${metricCard('💨', 'CO₂ per unit', d.co2_per_unit || '—')}
            ${metricCard('📊', 'vs Average', d.vs_average || '—')}
          </div>
        </div>
        ${d.breakdown ? `
          <div class="sus-section">
            <div class="sus-section-title">📊 Emissions Breakdown</div>
            <div class="sus-breakdown-list">
              ${Object.entries(d.breakdown).map(([k, v]) => `
                <div class="sus-breakdown-row">
                  <span class="sus-breakdown-label">${esc(k.charAt(0).toUpperCase() + k.slice(1))}</span>
                  <span class="sus-breakdown-value">${esc(v)}</span>
                </div>
              `).join('')}
            </div>
          </div>
        ` : ''}
        ${d.reduction_tips && d.reduction_tips.length ? `
          <div class="sus-section">
            <div class="sus-section-title">💡 Reduction Tips</div>
            <ul class="sus-fact-list">
              ${d.reduction_tips.map(t => `<li>${esc(t)}</li>`).join('')}
            </ul>
          </div>
        ` : ''}
        ${d.low_carbon_alternative ? `
          <div class="sus-section">
            <div class="sus-section-title">🌿 Best Low-Carbon Alternative</div>
            <div class="sus-highlight-box">${esc(d.low_carbon_alternative)}</div>
          </div>
        ` : ''}
      </div>
    `;
  }

  function renderAlternatives(d, name) {
    const alts = d.alternatives || [];
    return `
      <div class="sus-structured">
        <div class="sus-section">
          <div class="sus-section-title">♻️ Sustainable Alternatives to ${esc(name)}</div>
          <div class="sus-alt-list-full">
            ${alts.map((a, i) => `
              <div class="sus-alt-full-card">
                <div class="sus-alt-full-header">
                  <span class="sus-alt-rank">${i + 1}</span>
                  <div>
                    <div class="sus-alt-full-name">${esc(a.name)}</div>
                    <span class="sus-alt-type-badge">${esc(a.type || '')}</span>
                  </div>
                  <div class="sus-alt-full-saving">${esc(a.co2_saving || '')}</div>
                </div>
                <div class="sus-alt-full-body">
                  <div class="sus-alt-full-benefit">🌱 ${esc(a.benefit || '')}</div>
                  ${a.where_to_find ? `<div class="sus-alt-full-where">🛒 ${esc(a.where_to_find)}</div>` : ''}
                </div>
              </div>
            `).join('')}
          </div>
        </div>
        ${d.best_pick ? `
          <div class="sus-section">
            <div class="sus-section-title">⭐ Best Pick</div>
            <div class="sus-highlight-box sus-highlight-green">${esc(d.best_pick)}</div>
          </div>
        ` : ''}
      </div>
    `;
  }

  function renderBlueprint(d, name) {
    const redesign = d.redesign || {};
    return `
      <div class="sus-structured">
        <div class="sus-section">
          <div class="sus-section-title">🔧 Sustainability Redesign Blueprint — ${esc(name)}</div>
          ${d.current_issues && d.current_issues.length ? `
            <div class="sus-issues-list">
              ${d.current_issues.map(i => `<div class="sus-issue-item">⚠️ ${esc(i)}</div>`).join('')}
            </div>
          ` : ''}
        </div>

        ${Object.keys(redesign).length ? `
          <div class="sus-section">
            <div class="sus-section-title">📐 Redesign Proposals</div>
            <div class="sus-redesign-grid">
              ${Object.entries(redesign).map(([key, val]) => `
                <div class="sus-redesign-card">
                  <div class="sus-redesign-key">${esc(key.charAt(0).toUpperCase() + key.slice(1))}</div>
                  <div class="sus-redesign-row">
                    <span class="sus-redesign-label">Now:</span>
                    <span class="sus-redesign-current">${esc(val.current || '')}</span>
                  </div>
                  <div class="sus-redesign-row">
                    <span class="sus-redesign-label">Proposed:</span>
                    <span class="sus-redesign-proposed">${esc(val.proposed || '')}</span>
                  </div>
                  <div class="sus-redesign-impact">✓ ${esc(val.impact || '')}</div>
                </div>
              `).join('')}
            </div>
          </div>
        ` : ''}

        <div class="sus-metrics-grid">
          ${metricCard('📉', 'CO₂ Reduction', d.estimated_co2_reduction || '—')}
          ${metricCard('🔨', 'Difficulty', d.implementation_difficulty || '—')}
        </div>

        ${d.summary ? `
          <div class="sus-section">
            <div class="sus-highlight-box sus-highlight-green">${esc(d.summary)}</div>
          </div>
        ` : ''}

        <!-- Blueprint image -->
        <div class="sus-section sus-blueprint-img-section"></div>
      </div>
    `;
  }

  // ── Component helpers ─────────────────────────────────────

  function metricCard(icon, label, value) {
    return `
      <div class="sus-metric-card">
        <div class="sus-metric-icon">${icon}</div>
        <div class="sus-metric-label">${esc(label)}</div>
        <div class="sus-metric-value">${esc(value)}</div>
      </div>
    `;
  }

  function blueprintRow(icon, label, text) {
    if (!text) return '';
    return `
      <div class="sus-bp-row">
        <div class="sus-bp-row-header">${icon} ${esc(label)}</div>
        <div class="sus-bp-row-text">${esc(text)}</div>
      </div>
    `;
  }

  // ── Utilities ─────────────────────────────────────────────

  function catEmoji(cat) {
    return { fruits:'🍎', vegetables:'🥦', dairy:'🧀', beverages:'🥤', meat:'🥩', packaged_goods:'📦' }[cat] || '🍽️';
  }

  function fmtCat(cat) {
    if (!cat) return '';
    return cat.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  }

  function esc(str) {
    if (!str) return '';
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  return { initSustainability, refreshItems };
})();

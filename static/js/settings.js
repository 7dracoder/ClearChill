/**
 * Fridge Observer — Settings Page
 * settings.js
 */

let _currentSettings = {};

/** Fetch settings from the API */
async function fetchSettings() {
  const res = await fetch('/api/settings');
  if (!res.ok) throw new Error('Failed to fetch settings');
  return res.json();
}

/** Render the settings form */
function renderSettingsForm(settings) {
  _currentSettings = { ...settings };

  // Spoilage thresholds
  const categories = ['fruits', 'vegetables', 'dairy', 'beverages', 'meat', 'packaged_goods'];
  categories.forEach(cat => {
    const input = document.getElementById(`threshold-${cat}`);
    if (input) {
      input.value = settings[`spoilage_threshold_${cat}`] || '';
    }
  });

  // Temperature thresholds
  const fridgeTemp = document.getElementById('temp-fridge');
  if (fridgeTemp) fridgeTemp.value = settings['temp_threshold_fridge'] || '';

  const freezerTemp = document.getElementById('temp-freezer');
  if (freezerTemp) freezerTemp.value = settings['temp_threshold_freezer'] || '';

  // Toggles
  setToggle('shopping-list-toggle', settings['shopping_list_enabled'] === 'true');
  setToggle('echo-dot-toggle', settings['echo_dot_enabled'] === 'true');
  setToggle('gamification-toggle', settings['gamification_enabled'] === 'true');

  // Webhook URL
  const webhookInput = document.getElementById('webhook-url');
  if (webhookInput) webhookInput.value = settings['shopping_list_webhook_url'] || '';

  // Show/hide webhook URL based on shopping list toggle
  updateWebhookVisibility(settings['shopping_list_enabled'] === 'true');
}

/** Set a toggle switch value */
function setToggle(id, value) {
  const toggle = document.getElementById(id);
  if (toggle) toggle.checked = value;
}

/** Update webhook URL field visibility */
function updateWebhookVisibility(enabled) {
  const webhookRow = document.getElementById('webhook-url-row');
  if (webhookRow) {
    webhookRow.style.display = enabled ? '' : 'none';
  }
}

/** Validate settings inputs */
function validateSettings() {
  let valid = true;
  clearValidationErrors();

  // Spoilage thresholds: 1-14
  const categories = ['fruits', 'vegetables', 'dairy', 'beverages', 'meat', 'packaged_goods'];
  categories.forEach(cat => {
    const input = document.getElementById(`threshold-${cat}`);
    if (input) {
      const val = parseInt(input.value);
      if (isNaN(val) || val < 1 || val > 14) {
        showValidationError(input, 'Must be between 1 and 14 days');
        valid = false;
      }
    }
  });

  // Fridge temp: 0-10°C
  const fridgeTemp = document.getElementById('temp-fridge');
  if (fridgeTemp) {
    const val = parseFloat(fridgeTemp.value);
    if (isNaN(val) || val < 0 || val > 10) {
      showValidationError(fridgeTemp, 'Fridge temp must be 0–10°C');
      valid = false;
    }
  }

  // Freezer temp: -30 to -10°C
  const freezerTemp = document.getElementById('temp-freezer');
  if (freezerTemp) {
    const val = parseFloat(freezerTemp.value);
    if (isNaN(val) || val < -30 || val > -10) {
      showValidationError(freezerTemp, 'Freezer temp must be -30 to -10°C');
      valid = false;
    }
  }

  // Webhook URL validation
  const shoppingEnabled = document.getElementById('shopping-list-toggle')?.checked;
  const webhookInput = document.getElementById('webhook-url');
  if (shoppingEnabled && webhookInput && webhookInput.value.trim()) {
    try {
      new URL(webhookInput.value.trim());
    } catch {
      showValidationError(webhookInput, 'Please enter a valid URL');
      valid = false;
    }
  }

  return valid;
}

/** Show a validation error for an input */
function showValidationError(input, message) {
  input.classList.add('error');
  const errorEl = document.createElement('div');
  errorEl.className = 'validation-error';
  errorEl.textContent = '⚠ ' + message;
  errorEl.dataset.validationFor = input.id;
  input.parentNode.appendChild(errorEl);
}

/** Clear all validation errors */
function clearValidationErrors() {
  document.querySelectorAll('.validation-error[data-validation-for]').forEach(el => el.remove());
  document.querySelectorAll('.form-input.error, .threshold-input.error').forEach(el => {
    el.classList.remove('error');
  });
}

/** Collect current form values */
function collectFormValues() {
  const values = {};
  const categories = ['fruits', 'vegetables', 'dairy', 'beverages', 'meat', 'packaged_goods'];

  categories.forEach(cat => {
    const input = document.getElementById(`threshold-${cat}`);
    if (input) values[`spoilage_threshold_${cat}`] = input.value;
  });

  const fridgeTemp = document.getElementById('temp-fridge');
  if (fridgeTemp) values['temp_threshold_fridge'] = fridgeTemp.value;

  const freezerTemp = document.getElementById('temp-freezer');
  if (freezerTemp) values['temp_threshold_freezer'] = freezerTemp.value;

  const shoppingToggle = document.getElementById('shopping-list-toggle');
  if (shoppingToggle) values['shopping_list_enabled'] = shoppingToggle.checked ? 'true' : 'false';

  const echoToggle = document.getElementById('echo-dot-toggle');
  if (echoToggle) values['echo_dot_enabled'] = echoToggle.checked ? 'true' : 'false';

  const gamToggle = document.getElementById('gamification-toggle');
  if (gamToggle) values['gamification_enabled'] = gamToggle.checked ? 'true' : 'false';

  const webhookInput = document.getElementById('webhook-url');
  if (webhookInput) values['shopping_list_webhook_url'] = webhookInput.value.trim();

  return values;
}

/** Initialize the settings section */
async function initSettings() {
  try {
    const settings = await fetchSettings();
    renderSettingsForm(settings);
  } catch (err) {
    console.error('Failed to load settings:', err);
    showToast('Failed to load settings', 'error');
  }

  // Shopping list toggle → show/hide webhook URL
  const shoppingToggle = document.getElementById('shopping-list-toggle');
  if (shoppingToggle) {
    shoppingToggle.addEventListener('change', () => {
      updateWebhookVisibility(shoppingToggle.checked);
    });
  }

  // Live validation on threshold inputs
  document.querySelectorAll('.threshold-input').forEach(input => {
    input.addEventListener('input', () => {
      const val = parseInt(input.value);
      const errorEl = document.querySelector(`[data-validation-for="${input.id}"]`);
      if (isNaN(val) || val < 1 || val > 14) {
        input.classList.add('error');
        if (!errorEl) showValidationError(input, 'Must be 1–14 days');
      } else {
        input.classList.remove('error');
        if (errorEl) errorEl.remove();
      }
    });
  });

  // Save button
  const saveBtn = document.getElementById('settings-save-btn');
  if (saveBtn) {
    saveBtn.addEventListener('click', async () => {
      if (!validateSettings()) {
        showToast('Please fix the errors before saving', 'error');
        return;
      }

      const values = collectFormValues();
      saveBtn.disabled = true;
      saveBtn.textContent = 'Saving...';

      try {
        const res = await fetch('/api/settings', {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(values),
        });
        if (!res.ok) throw new Error('Failed to save settings');
        _currentSettings = await res.json();
        showToast('Settings saved successfully', 'success');
      } catch (err) {
        console.error('Save settings error:', err);
        showToast('Failed to save settings', 'error');
      } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = 'Save Settings';
      }
    });
  }
}

/** Update temperature display from WebSocket */
function updateTemperatureDisplay(data) {
  const fridgeEl = document.getElementById('current-temp-fridge');
  const freezerEl = document.getElementById('current-temp-freezer');

  if (fridgeEl && data.fridge !== null && data.fridge !== undefined) {
    fridgeEl.textContent = `${data.fridge.toFixed(1)}°C`;
  }
  if (freezerEl && data.freezer !== null && data.freezer !== undefined) {
    freezerEl.textContent = `${data.freezer.toFixed(1)}°C`;
  }
}

window.settingsModule = { initSettings, updateTemperatureDisplay };

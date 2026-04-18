/**
 * Fridge Observer — AI Assistant
 * ai-assistant.js: K2-Think chat panel with streaming responses
 */

class AIAssistant {
  constructor() {
    this._isOpen = false;
    this._isStreaming = false;
    this._panel = null;
    this._messages = null;
    this._input = null;
    this._sendBtn = null;
    this._fab = null;
    this._overlay = null;
  }

  init() {
    this._injectHTML();
    this._panel = document.getElementById('ai-panel');
    this._messages = document.getElementById('ai-messages');
    this._input = document.getElementById('ai-input');
    this._sendBtn = document.getElementById('ai-send-btn');
    this._fab = document.getElementById('ai-fab');
    this._overlay = document.getElementById('ai-overlay');

    this._bindEvents();
    this._messages.innerHTML = '';
  }

  // ── HTML Injection ──────────────────────────────────────────

  _injectHTML() {
    const overlay = document.createElement('div');
    overlay.id = 'ai-overlay';
    overlay.className = 'ai-overlay';
    document.body.appendChild(overlay);

    const fab = document.createElement('button');
    fab.id = 'ai-fab';
    fab.className = 'ai-fab';
    fab.setAttribute('aria-label', 'Open AI Assistant');
    fab.setAttribute('title', 'Ask AI');
    fab.innerHTML = '✨';
    document.body.appendChild(fab);

    const panel = document.createElement('div');
    panel.id = 'ai-panel';
    panel.className = 'ai-panel';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-label', 'AI Assistant');
    panel.innerHTML = `
      <div class="ai-panel-header">
        <div class="ai-panel-icon">✨</div>
        <div class="ai-panel-title">
          <h3>Assistant</h3>
        </div>
        <button class="ai-panel-close" id="ai-panel-close" aria-label="Close AI panel">×</button>
      </div>

      <div class="ai-quick-actions">
        <button class="ai-quick-btn" data-prompt="What can I cook with what I have?">What can I cook?</button>
        <button class="ai-quick-btn" data-prompt="What's expiring soon and what should I use first?">What's expiring?</button>
        <button class="ai-quick-btn" data-prompt="Give me a quick fridge summary and any tips to reduce waste.">Fridge summary</button>
        <button class="ai-quick-btn" data-prompt="Suggest a healthy meal I can make today.">Healthy meal idea</button>
        <button class="ai-quick-btn" data-prompt="What should I buy next time I go shopping based on what I'm running low on?">Shopping tips</button>
      </div>

      <div class="ai-messages" id="ai-messages" role="log" aria-live="polite"></div>

      <div class="ai-input-area">
        <label for="ai-image-upload" class="ai-image-btn" title="Identify food from image (Gemini Vision)">
          📷
          <input type="file" id="ai-image-upload" accept="image/*" style="display:none" />
        </label>
        <textarea
          id="ai-input"
          class="ai-input"
          placeholder="Ask anything about your fridge..."
          rows="1"
          aria-label="Ask the AI assistant"
        ></textarea>
        <button id="ai-send-btn" class="ai-send-btn" aria-label="Send message" disabled>
          ➤
        </button>
      </div>
    `;
    document.body.appendChild(panel);
  }

  // ── Events ──────────────────────────────────────────────────

  _bindEvents() {
    // FAB toggle
    this._fab.addEventListener('click', () => this.toggle());

    // Close button
    document.getElementById('ai-panel-close').addEventListener('click', () => this.close());

    // Overlay click to close
    this._overlay.addEventListener('click', () => this.close());

    // Input events
    this._input.addEventListener('input', () => {
      this._sendBtn.disabled = !this._input.value.trim() || this._isStreaming;
      // Auto-resize textarea
      this._input.style.height = 'auto';
      this._input.style.height = Math.min(this._input.scrollHeight, 100) + 'px';
    });

    this._input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (!this._sendBtn.disabled) this._send();
      }
    });

    // Send button
    this._sendBtn.addEventListener('click', () => this._send());

    // Quick action buttons
    document.querySelectorAll('.ai-quick-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const prompt = btn.dataset.prompt;
        if (prompt && !this._isStreaming) {
          this._input.value = prompt;
          this._sendBtn.disabled = false;
          this._send();
        }
      });
    });

    // Image upload (Gemini vision)
    document.getElementById('ai-image-upload').addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (file) this._identifyImage(file);
      e.target.value = ''; // reset
    });

    // Escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this._isOpen) this.close();
    });
  }

  // ── Panel open/close ────────────────────────────────────────

  open() {
    this._isOpen = true;
    this._panel.classList.add('open');
    this._overlay.classList.add('visible');
    this._fab.style.display = 'none';
    setTimeout(() => this._input.focus(), 350);
  }

  close() {
    this._isOpen = false;
    this._panel.classList.remove('open');
    this._overlay.classList.remove('visible');
    this._fab.style.display = '';
  }

  toggle() {
    this._isOpen ? this.close() : this.open();
  }

  // ── Welcome message ─────────────────────────────────────────

  _showWelcome() {
    this._messages.innerHTML = '';
  }

  // ── Message rendering ────────────────────────────────────────

  _addUserMessage(text) {
    const welcome = this._messages.querySelector('.ai-welcome');
    if (welcome) welcome.remove();

    const el = document.createElement('div');
    el.className = 'ai-message user';
    el.innerHTML = `
      <div class="ai-message-avatar">👤</div>
      <div class="ai-message-bubble">${window.escapeHtml ? window.escapeHtml(text) : text}</div>
    `;
    this._messages.appendChild(el);
    this._scrollToBottom();
    return el;
  }

  _addAssistantMessage() {
    const el = document.createElement('div');
    el.className = 'ai-message assistant';
    el.innerHTML = `
      <div class="ai-message-avatar">✨</div>
      <div class="ai-message-bubble ai-streaming-cursor" id="ai-streaming-bubble"></div>
    `;
    this._messages.appendChild(el);
    this._scrollToBottom();
    return el.querySelector('#ai-streaming-bubble');
  }

  _addThinking() {
    const el = document.createElement('div');
    el.className = 'ai-message assistant';
    el.id = 'ai-thinking-msg';
    el.innerHTML = `
      <div class="ai-message-avatar">✨</div>
      <div class="ai-thinking">
        <div class="ai-thinking-dot"></div>
        <div class="ai-thinking-dot"></div>
        <div class="ai-thinking-dot"></div>
      </div>
    `;
    this._messages.appendChild(el);
    this._scrollToBottom();
    return el;
  }

  _removeThinking() {
    document.getElementById('ai-thinking-msg')?.remove();
  }

  _scrollToBottom() {
    this._messages.scrollTop = this._messages.scrollHeight;
  }

  // ── Send message ─────────────────────────────────────────────

  async _send() {
    const text = this._input.value.trim();
    if (!text || this._isStreaming) return;

    this._input.value = '';
    this._input.style.height = 'auto';
    this._sendBtn.disabled = true;
    this._isStreaming = true;

    this._addUserMessage(text);
    const thinking = this._addThinking();

    try {
      const response = await fetch('/api/ai/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: text }),
      });

      if (!response.ok) {
        // Try to get error message from response
        let errorMsg = `HTTP ${response.status}`;
        try {
          const errorData = await response.json();
          errorMsg = errorData.detail || errorMsg;
        } catch (e) {
          // If not JSON, try text
          try {
            const errorText = await response.text();
            if (errorText) errorMsg = errorText;
          } catch (e2) {
            // Keep default error message
          }
        }
        throw new Error(errorMsg);
      }

      this._removeThinking();
      const bubble = this._addAssistantMessage();
      let fullText = '';

      await this._readSSE(response, (token) => {
        fullText += token;
        bubble.textContent = fullText;
        this._scrollToBottom();
      });

      // Remove streaming cursor
      bubble.classList.remove('ai-streaming-cursor');
      bubble.id = '';

    } catch (err) {
      this._removeThinking();
      const bubble = this._addAssistantMessage();
      bubble.textContent = `Sorry, I ran into an issue: ${err.message}`;
      bubble.classList.remove('ai-streaming-cursor');
      bubble.id = '';
      console.error('[AI] Error:', err);
    } finally {
      this._isStreaming = false;
      this._sendBtn.disabled = !this._input.value.trim();
    }
  }

  // ── SSE reader ───────────────────────────────────────────────

  async _readSSE(response, onToken) {
    const reader = response.body.getReader();
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
        const data = line.slice(6);
        if (data === '[DONE]') return;
        onToken(data);
      }
    }
  }

  // ── Gemini image identification ──────────────────────────────

  async _identifyImage(file) {
    if (this._isStreaming) return;
    this._isStreaming = true;

    const welcome = this._messages.querySelector('.ai-welcome');
    if (welcome) welcome.remove();

    // Show user message with image preview
    const reader = new FileReader();
    reader.onload = async (e) => {
      const imgEl = document.createElement('div');
      imgEl.className = 'ai-message user';
      imgEl.innerHTML = `
        <div class="ai-message-avatar">👤</div>
        <div class="ai-message-bubble">
          <img src="${e.target.result}" alt="Uploaded food image"
               style="max-width:180px; border-radius:8px; display:block; margin-bottom:4px;" />
          <span style="font-size:12px; opacity:0.85;">Identify food items in this image</span>
        </div>
      `;
      this._messages.appendChild(imgEl);
      this._scrollToBottom();

      const thinking = this._addThinking();

      try {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch('/api/ai/identify', {
          method: 'POST',
          body: formData,
        });

        this._removeThinking();

        if (!response.ok) {
          const err = await response.json();
          throw new Error(err.detail || `HTTP ${response.status}`);
        }

        const result = await response.json();
        const items = result.items || [];

        const bubble = document.createElement('div');
        bubble.className = 'ai-message assistant';

        if (items.length === 0) {
          bubble.innerHTML = `
            <div class="ai-message-avatar">✨</div>
            <div class="ai-message-bubble">I couldn't identify any food items in that image. Try a clearer photo with better lighting.</div>
          `;
        } else {
          const itemList = items.map(item => {
            const conf = Math.round((item.confidence || 0) * 100);
            const emoji = this._categoryEmoji(item.category);
            return `${emoji} <strong>${item.name}</strong> (${item.category}, ${conf}% confidence)`;
          }).join('<br>');

          bubble.innerHTML = `
            <div class="ai-message-avatar">✨</div>
            <div class="ai-message-bubble">
              I identified ${items.length} item${items.length !== 1 ? 's' : ''}:<br><br>
              ${itemList}<br><br>
              <button class="btn btn-primary" style="font-size:12px; padding:6px 12px;" id="ai-add-identified-btn">
                ➕ Add to Inventory
              </button>
            </div>
          `;

          this._messages.appendChild(bubble);
          this._scrollToBottom();

          // Wire up the add button
          document.getElementById('ai-add-identified-btn')?.addEventListener('click', async () => {
            await this._addIdentifiedItems(items);
          });

          this._isStreaming = false;
          return;
        }

        this._messages.appendChild(bubble);
        this._scrollToBottom();

      } catch (err) {
        this._removeThinking();
        const bubble = document.createElement('div');
        bubble.className = 'ai-message assistant';
        bubble.innerHTML = `
          <div class="ai-message-avatar">✨</div>
          <div class="ai-message-bubble">Sorry, I couldn't analyse that image: ${err.message}</div>
        `;
        this._messages.appendChild(bubble);
        this._scrollToBottom();
        console.error('[AI] Image identify error:', err);
      } finally {
        this._isStreaming = false;
      }
    };
    reader.readAsDataURL(file);
  }

  async _addIdentifiedItems(items) {
    let added = 0;
    for (const item of items) {
      if ((item.confidence || 0) < 0.5) continue;
      try {
        await fetch('/api/inventory', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: item.name,
            category: item.category || 'packaged_goods',
            quantity: 1,
          }),
        });
        added++;
      } catch (e) {
        console.warn('[AI] Failed to add item:', item.name, e);
      }
    }

    if (window.showToast) {
      window.showToast(`Added ${added} item${added !== 1 ? 's' : ''} to inventory`, 'success');
    }

    // Refresh inventory if visible
    if (window.inventoryModule) {
      window.inventoryModule.refreshInventory();
    }

    // Confirm in chat
    const bubble = document.createElement('div');
    bubble.className = 'ai-message assistant';
    bubble.innerHTML = `
      <div class="ai-message-avatar">✨</div>
      <div class="ai-message-bubble">Done! Added ${added} item${added !== 1 ? 's' : ''} to your inventory. 🎉</div>
    `;
    this._messages.appendChild(bubble);
    this._scrollToBottom();
  }

  _categoryEmoji(category) {
    const map = {
      fruits: '🍎', vegetables: '🥦', dairy: '🧀',
      beverages: '🥤', meat: '🥩', packaged_goods: '📦',
    };
    return map[category] || '🍽️';
  }
}

// Initialise when DOM is ready
window.aiAssistant = new AIAssistant();
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => window.aiAssistant.init());
} else {
  window.aiAssistant.init();
}

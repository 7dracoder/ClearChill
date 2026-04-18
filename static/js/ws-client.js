/**
 * Fridge Observer — WebSocket Client
 * ws-client.js: Real-time connection with exponential backoff reconnection
 */

class FridgeWebSocket {
  constructor() {
    this._ws = null;
    this._handlers = {};
    this._reconnectAttempts = 0;
    this._reconnectTimer = null;
    this._pingTimer = null;
    this._manualClose = false;
    this._connected = false;

    // Backoff delays: 1s, 2s, 4s, 8s, max 30s
    this._backoffDelays = [1000, 2000, 4000, 8000, 16000, 30000];
  }

  /** Connect to the WebSocket server */
  connect() {
    if (this._ws && (this._ws.readyState === WebSocket.OPEN || this._ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this._manualClose = false;
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${location.host}/ws`;

    try {
      this._ws = new WebSocket(url);
    } catch (err) {
      console.error('[WS] Failed to create WebSocket:', err);
      this._scheduleReconnect();
      return;
    }

    this._ws.onopen = () => {
      console.log('[WS] Connected');
      this._connected = true;
      this._reconnectAttempts = 0;
      this._updateStatus('connected');
      this._startPing();
    };

    this._ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        this._dispatch(message);
      } catch (err) {
        console.warn('[WS] Failed to parse message:', err);
      }
    };

    this._ws.onclose = (event) => {
      console.log('[WS] Disconnected', event.code, event.reason);
      this._connected = false;
      this._stopPing();

      if (!this._manualClose) {
        this._updateStatus('reconnecting');
        this._scheduleReconnect();
      } else {
        this._updateStatus('disconnected');
      }
    };

    this._ws.onerror = (err) => {
      console.warn('[WS] Error:', err);
    };
  }

  /** Register a handler for a message type */
  on(type, handler) {
    if (!this._handlers[type]) {
      this._handlers[type] = [];
    }
    this._handlers[type].push(handler);
    return this; // chainable
  }

  /** Remove a handler */
  off(type, handler) {
    if (this._handlers[type]) {
      this._handlers[type] = this._handlers[type].filter(h => h !== handler);
    }
  }

  /** Send a message */
  send(message) {
    if (this._ws && this._ws.readyState === WebSocket.OPEN) {
      this._ws.send(JSON.stringify(message));
    }
  }

  /** Close the connection */
  close() {
    this._manualClose = true;
    this._stopPing();
    if (this._reconnectTimer) {
      clearTimeout(this._reconnectTimer);
      this._reconnectTimer = null;
    }
    if (this._ws) {
      this._ws.close();
    }
  }

  get isConnected() {
    return this._connected;
  }

  // ── Private methods ──────────────────────────────────────────

  _dispatch(message) {
    const { type } = message;
    const handlers = this._handlers[type] || [];
    handlers.forEach(h => {
      try {
        h(message.payload, message);
      } catch (err) {
        console.error(`[WS] Handler error for type "${type}":`, err);
      }
    });

    // Also dispatch to wildcard handlers
    const wildcardHandlers = this._handlers['*'] || [];
    wildcardHandlers.forEach(h => {
      try {
        h(message.payload, message);
      } catch (err) {
        console.error('[WS] Wildcard handler error:', err);
      }
    });
  }

  _scheduleReconnect() {
    if (this._reconnectTimer) return;

    const delay = this._backoffDelays[
      Math.min(this._reconnectAttempts, this._backoffDelays.length - 1)
    ];
    this._reconnectAttempts++;

    console.log(`[WS] Reconnecting in ${delay}ms (attempt ${this._reconnectAttempts})`);

    this._reconnectTimer = setTimeout(() => {
      this._reconnectTimer = null;
      this.connect();
    }, delay);
  }

  _startPing() {
    this._stopPing();
    this._pingTimer = setInterval(() => {
      if (this._ws && this._ws.readyState === WebSocket.OPEN) {
        this._ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000);
  }

  _stopPing() {
    if (this._pingTimer) {
      clearInterval(this._pingTimer);
      this._pingTimer = null;
    }
  }

  _updateStatus(status) {
    // Update connection dot
    const dot = document.querySelector('.connection-dot');
    if (dot) {
      dot.className = 'connection-dot ' + status;
      dot.title = status.charAt(0).toUpperCase() + status.slice(1);
    }

    // Update connection banner
    const banner = document.querySelector('.connection-banner');
    if (banner) {
      if (status === 'disconnected' || status === 'reconnecting') {
        banner.classList.add('visible');
        const msg = banner.querySelector('.connection-banner-msg');
        if (msg) {
          msg.textContent = status === 'reconnecting'
            ? '⚡ Reconnecting to Fridge Observer...'
            : '⚠️ Disconnected from Fridge Observer. Updates paused.';
        }
      } else {
        banner.classList.remove('visible');
      }
    }
  }
}

// Global WebSocket instance
window.fridgeWS = new FridgeWebSocket();

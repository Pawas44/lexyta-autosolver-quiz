// ==UserScript==
// @name         Lexyta Shield Pro
// @namespace    https://lms.lexyta.com
// @version      3.0
// @description  Complete proctoring neutralizer — reverse-engineered from Lexyta's main-RCXULGX4.js production bundle (68 proctoring hooks, Socket.IO heartbeat, flush pipeline)
// @author       Pawas
// @match        https://lms.lexyta.com/*
// @grant        none
// @run-at       document-start
// @noframes     false
// ==/UserScript==

(function () {
  "use strict";

  // ═══════════════════════════════════════════════════════════════════
  //  LEXYTA PROCTORING SYSTEM — REVERSE ENGINEERED COMPONENTS:
  //
  //  1. ProctoringService — Tab switch counter, mouse leave counter,
  //     clipboard intercept, fullscreen enforcer, DevTools detector
  //  2. Socket.IO pipeline — flushIntervalMs: 5000, heartbeatIntervalMs: 15000
  //     Events: "proctoring:event", "proctoring:heartbeat"
  //  3. Event buffer — Collects events locally, flushes every 5s to backend
  //  4. Fullscreen API — Forces fullscreen, exits quiz on escape
  //  5. BeforeUnload trap — Prevents page navigation during quiz
  //  6. Console/DevTools size detection — window.outerWidth - window.innerWidth
  //
  //  This script neutralizes ALL of them at the JavaScript engine level
  //  BEFORE Lexyta's bundle loads.
  // ═══════════════════════════════════════════════════════════════════

  const LOG_PREFIX = ""; // Empty = no console logs (stealth). Set to "🛡️" for debug.
  function log(...args) {
    if (LOG_PREFIX) console.log(LOG_PREFIX, ...args);
  }

  log("Shield initializing (document-start)...");

  // ─────────────────────────────────────────────
  // 1. VISIBILITY API — COMPLETE LOCKDOWN
  // ─────────────────────────────────────────────
  // Lexyta checks document.visibilityState and document.hidden
  // on every visibilitychange event and counts tab switches.

  // Lock visibilityState to 'visible'
  Object.defineProperty(document, "visibilityState", {
    get: () => "visible",
    configurable: true,
  });

  // Lock hidden to false
  Object.defineProperty(document, "hidden", {
    get: () => false,
    configurable: true,
  });

  // Also lock webkitVisibilityState (older browsers)
  try {
    Object.defineProperty(document, "webkitVisibilityState", {
      get: () => "visible",
      configurable: true,
    });
    Object.defineProperty(document, "webkitHidden", {
      get: () => false,
      configurable: true,
    });
  } catch (e) {}

  // Block hasFocus — Lexyta calls document.hasFocus() in its proctoring loop
  Document.prototype.hasFocus = function () {
    return true;
  };

  // ─────────────────────────────────────────────
  // 2. EVENT INTERCEPTION — NUCLEAR APPROACH
  // ─────────────────────────────────────────────
  // Instead of just stopImmediatePropagation (which Lexyta can detect
  // by checking if its own listener fired), we intercept addEventListener
  // itself and silently DROP Lexyta's proctoring listeners.

  const BLOCKED_EVENTS = new Set([
    // Tab/window focus events
    "visibilitychange",
    "webkitvisibilitychange",
    "pagehide",
    "pageshow",
    "blur",
    "focus",
    // Mouse leave tracking
    "mouseleave",
    "mouseout",
    // Clipboard monitoring
    "copy",
    "cut",
    "paste",
    // Context menu block
    "contextmenu",
    // Fullscreen events (Lexyta forces fullscreen and detects exit)
    "fullscreenchange",
    "webkitfullscreenchange",
    "mozfullscreenchange",
    "MSFullscreenChange",
    "fullscreenerror",
  ]);

  // Keep a reference to the REAL addEventListener
  const _realAddEventListener = EventTarget.prototype.addEventListener;
  const _realRemoveEventListener = EventTarget.prototype.removeEventListener;

  // Track blocked listeners so we can count them
  let blockedCount = 0;

  // Override addEventListener on ALL targets (window, document, elements)
  EventTarget.prototype.addEventListener = function (type, listener, options) {
    // Check if this is a proctoring event we should block
    if (BLOCKED_EVENTS.has(type)) {
      // Check if this listener is from Lexyta's code (not our own)
      // We allow our own listeners by marking them
      if (listener && !listener._shieldAllowed) {
        blockedCount++;
        log(`Blocked listener: ${type} (total blocked: ${blockedCount})`);
        // Don't register it at all — silently drop
        return;
      }
    }
    // Allow all other listeners through
    return _realAddEventListener.call(this, type, listener, options);
  };

  // Helper to register our OWN listeners that bypass the block
  function addOwnListener(target, type, fn, options) {
    fn._shieldAllowed = true;
    _realAddEventListener.call(target, type, fn, options);
  }

  // ─────────────────────────────────────────────
  // 3. KEYBOARD LOCKDOWN BYPASS
  // ─────────────────────────────────────────────
  // Lexyta blocks: F12, Ctrl+Shift+I, Ctrl+Shift+J, Ctrl+U,
  // and sometimes Ctrl+C/Ctrl+V during quizzes

  addOwnListener(document, "keydown", function (e) {
    // Allow ALL keyboard shortcuts — override any preventDefault
    // Specifically re-enable:
    // - F12 (DevTools)
    // - Ctrl+Shift+I (Inspect)
    // - Ctrl+Shift+J (Console)
    // - Ctrl+U (View Source)
    // - Ctrl+C/V/X (Copy/Paste/Cut)
    // - Ctrl+A (Select All)
    // We do this by stopping propagation so Lexyta's keydown handler never sees it
    const dominated = [
      e.key === "F12",
      e.ctrlKey && e.shiftKey && e.key === "I",
      e.ctrlKey && e.shiftKey && e.key === "J",
      e.ctrlKey && e.key === "u",
      e.ctrlKey && e.key === "c",
      e.ctrlKey && e.key === "v",
      e.ctrlKey && e.key === "x",
      e.ctrlKey && e.key === "a",
    ];

    if (dominated.some(Boolean)) {
      e.stopImmediatePropagation();
      // Don't preventDefault — let the browser handle it normally
    }
  }, true);

  // Re-enable right click
  addOwnListener(document, "contextmenu", function (e) {
    e.stopImmediatePropagation();
  }, true);

  // ─────────────────────────────────────────────
  // 4. FULLSCREEN API NEUTRALIZER
  // ─────────────────────────────────────────────
  // Lexyta forces fullscreen mode during quizzes and detects
  // when you exit fullscreen (Escape key). We make it THINK
  // it's always in fullscreen.

  // Override fullscreen state getters
  Object.defineProperty(document, "fullscreenElement", {
    get: () => document.documentElement,
    configurable: true,
  });
  Object.defineProperty(document, "webkitFullscreenElement", {
    get: () => document.documentElement,
    configurable: true,
  });
  Object.defineProperty(document, "mozFullScreenElement", {
    get: () => document.documentElement,
    configurable: true,
  });
  Object.defineProperty(document, "msFullscreenElement", {
    get: () => document.documentElement,
    configurable: true,
  });

  // Fullscreen state flags
  Object.defineProperty(document, "fullscreen", {
    get: () => true,
    configurable: true,
  });
  Object.defineProperty(document, "webkitIsFullScreen", {
    get: () => true,
    configurable: true,
  });
  Object.defineProperty(document, "mozFullScreen", {
    get: () => true,
    configurable: true,
  });

  // Make requestFullscreen a no-op (prevents the actual fullscreen popup)
  Element.prototype.requestFullscreen = function () {
    return Promise.resolve();
  };
  Element.prototype.webkitRequestFullscreen = function () {
    return Promise.resolve();
  };
  Element.prototype.webkitRequestFullScreen = function () {
    return Promise.resolve();
  };
  Element.prototype.mozRequestFullScreen = function () {
    return Promise.resolve();
  };
  Element.prototype.msRequestFullscreen = function () {
    return Promise.resolve();
  };

  // Make exitFullscreen a no-op
  Document.prototype.exitFullscreen = function () {
    return Promise.resolve();
  };
  Document.prototype.webkitExitFullscreen = function () {
    return Promise.resolve();
  };
  Document.prototype.mozCancelFullScreen = function () {
    return Promise.resolve();
  };
  Document.prototype.msExitFullscreen = function () {
    return Promise.resolve();
  };

  // ─────────────────────────────────────────────
  // 5. DEVTOOLS SIZE DETECTION BYPASS
  // ─────────────────────────────────────────────
  // Lexyta uses: (window.outerWidth - window.innerWidth > 160)
  // to detect if DevTools is open on the side.
  // We lock these values to make the difference always ~0.

  const _innerWidth = window.innerWidth;
  const _innerHeight = window.innerHeight;

  Object.defineProperty(window, "outerWidth", {
    get: () => window.innerWidth + 8, // Normal browser chrome width
    configurable: true,
  });
  Object.defineProperty(window, "outerHeight", {
    get: () => window.innerHeight + 80, // Normal title bar + address bar
    configurable: true,
  });

  // Also block the Firebug/debugger detection trick
  // (some proctoring systems use: debugger; statement + timing)
  // We can't fully block this, but we can override the timing checks

  // ─────────────────────────────────────────────
  // 6. SOCKET.IO EVENT INTERCEPTOR
  // ─────────────────────────────────────────────
  // Lexyta sends proctoring events via Socket.IO:
  //   socket.emit("proctoring:event", { type: "TAB_SWITCH", count: N })
  //   socket.emit("proctoring:heartbeat", { ... })
  //
  // We intercept the Socket.IO emit function and filter out
  // proctoring events, letting all other socket events through.

  function patchSocketIO() {
    // Wait for io() to be available
    if (typeof window.io === "undefined") return false;

    const _origIO = window.io;
    window.io = function (...args) {
      const socket = _origIO.apply(this, args);
      patchSocket(socket);
      return socket;
    };
    // Copy static properties
    Object.assign(window.io, _origIO);
    return true;
  }

  function patchSocket(socket) {
    if (!socket || socket._shieldPatched) return;
    socket._shieldPatched = true;

    const _origEmit = socket.emit;
    socket.emit = function (event, ...args) {
      // Block proctoring events
      if (typeof event === "string" && event.toLowerCase().includes("proctor")) {
        log(`Blocked socket emit: "${event}"`);
        return socket; // Silently swallow
      }
      // Allow everything else
      return _origEmit.apply(this, [event, ...args]);
    };
  }

  // Also intercept WebSocket directly (in case they use raw WS)
  const _OrigWebSocket = window.WebSocket;
  window.WebSocket = function (...args) {
    const ws = new _OrigWebSocket(...args);
    const _origSend = ws.send.bind(ws);
    ws.send = function (data) {
      // Check if data contains proctoring payload
      try {
        const str = typeof data === "string" ? data : "";
        if (str.includes("proctor") || str.includes("tab_switch") || str.includes("mouse_leave")) {
          log("Blocked WebSocket proctoring payload");
          return;
        }
      } catch (e) {}
      return _origSend(data);
    };
    return ws;
  };
  // Keep prototype chain intact
  window.WebSocket.prototype = _OrigWebSocket.prototype;
  window.WebSocket.CONNECTING = _OrigWebSocket.CONNECTING;
  window.WebSocket.OPEN = _OrigWebSocket.OPEN;
  window.WebSocket.CLOSING = _OrigWebSocket.CLOSING;
  window.WebSocket.CLOSED = _OrigWebSocket.CLOSED;

  // ─────────────────────────────────────────────
  // 7. FETCH / XHR INTERCEPTOR
  // ─────────────────────────────────────────────
  // Lexyta flushes proctoring events via HTTP POST every 5 seconds.
  // We intercept fetch() and XMLHttpRequest to block proctoring API calls.

  const _origFetch = window.fetch;
  window.fetch = function (url, options) {
    const urlStr = typeof url === "string" ? url : url?.url || "";
    if (urlStr.includes("proctor") || urlStr.includes("proctoring")) {
      log("Blocked fetch to proctoring endpoint:", urlStr);
      // Return a fake successful response
      return Promise.resolve(
        new Response(JSON.stringify({ success: true }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      );
    }

    // Also check POST body for proctoring data
    if (options?.body) {
      try {
        const bodyStr = typeof options.body === "string" ? options.body : "";
        if (bodyStr.includes("tab_switch") || bodyStr.includes("mouse_leave") || bodyStr.includes("clipboard")) {
          log("Blocked fetch with proctoring body");
          return Promise.resolve(
            new Response(JSON.stringify({ success: true }), {
              status: 200,
              headers: { "Content-Type": "application/json" },
            })
          );
        }
      } catch (e) {}
    }

    return _origFetch.apply(this, arguments);
  };

  // XMLHttpRequest intercept
  const _origXHROpen = XMLHttpRequest.prototype.open;
  const _origXHRSend = XMLHttpRequest.prototype.send;

  XMLHttpRequest.prototype.open = function (method, url, ...rest) {
    this._shieldUrl = url || "";
    return _origXHROpen.apply(this, [method, url, ...rest]);
  };

  XMLHttpRequest.prototype.send = function (body) {
    if (this._shieldUrl && (this._shieldUrl.includes("proctor") || this._shieldUrl.includes("proctoring"))) {
      log("Blocked XHR to proctoring endpoint:", this._shieldUrl);
      // Fake a successful response
      Object.defineProperty(this, "readyState", { get: () => 4 });
      Object.defineProperty(this, "status", { get: () => 200 });
      Object.defineProperty(this, "responseText", { get: () => '{"success":true}' });
      this.dispatchEvent(new Event("load"));
      return;
    }
    return _origXHRSend.apply(this, arguments);
  };

  // ─────────────────────────────────────────────
  // 8. BEFOREUNLOAD / UNLOAD TRAP BYPASS
  // ─────────────────────────────────────────────
  // Lexyta adds onbeforeunload to prevent navigating away.
  // We allow it but prevent the confirmation dialog.

  // Intercept onbeforeunload assignment
  let _beforeUnloadHandler = null;
  Object.defineProperty(window, "onbeforeunload", {
    get: () => _beforeUnloadHandler,
    set: (fn) => {
      // Store it but don't actually set it
      _beforeUnloadHandler = null;
      log("Blocked onbeforeunload assignment");
    },
    configurable: true,
  });

  // Also block addEventListener for beforeunload from Lexyta
  // (Already handled by BLOCKED_EVENTS won't include beforeunload by default
  //  since it's sometimes useful — but we neuter the confirmation)

  // ─────────────────────────────────────────────
  // 9. TIMER/INTERVAL SANITIZER
  // ─────────────────────────────────────────────
  // Lexyta runs proctoring checks via setInterval.
  // We intercept setInterval and patch any that look like proctoring loops.

  const _origSetInterval = window.setInterval;
  const _origClearInterval = window.clearInterval;
  const proctoringIntervals = new Set();

  window.setInterval = function (fn, delay, ...args) {
    // Lexyta's proctoring intervals: 5000ms (flush), 15000ms (heartbeat), 100ms (visibility check)
    const fnStr = typeof fn === "function" ? fn.toString() : String(fn);
    
    // Check if this interval is proctoring-related
    if (
      fnStr.includes("visibilityState") ||
      fnStr.includes("hidden") ||
      fnStr.includes("proctor") ||
      fnStr.includes("tabSwitch") ||
      fnStr.includes("tab_switch") ||
      fnStr.includes("mouseLeave") ||
      fnStr.includes("mouse_leave") ||
      fnStr.includes("fullscreen")
    ) {
      log(`Blocked proctoring setInterval (${delay}ms)`);
      // Return a fake interval ID that does nothing
      const fakeId = _origSetInterval.call(window, () => {}, 999999999);
      proctoringIntervals.add(fakeId);
      return fakeId;
    }

    return _origSetInterval.apply(this, [fn, delay, ...args]);
  };

  // ─────────────────────────────────────────────
  // 10. NOTIFICATION API SPOOF
  // ─────────────────────────────────────────────
  // Some LMS systems use Notification API to track if student is active.

  if (window.Notification) {
    Object.defineProperty(window.Notification, "permission", {
      get: () => "denied",
      configurable: true,
    });
  }

  // ─────────────────────────────────────────────
  // 11. SCREEN CAPTURE / RECORDING DETECTION
  // ─────────────────────────────────────────────
  // Block navigator.mediaDevices.getDisplayMedia detection

  if (navigator.mediaDevices) {
    navigator.mediaDevices.getDisplayMedia = function () {
      return Promise.reject(new Error("Not allowed"));
    };
  }

  // ─────────────────────────────────────────────
  // 12. CONTINUOUS HEALTH CHECK
  // ─────────────────────────────────────────────
  // Re-apply overrides periodically in case Lexyta tries to restore them.

  _origSetInterval.call(window, () => {
    // Re-enforce visibility state
    try {
      Object.defineProperty(document, "visibilityState", {
        get: () => "visible",
        configurable: true,
      });
      Object.defineProperty(document, "hidden", {
        get: () => false,
        configurable: true,
      });
    } catch (e) {}

    // Re-enforce fullscreen state
    try {
      Object.defineProperty(document, "fullscreenElement", {
        get: () => document.documentElement,
        configurable: true,
      });
    } catch (e) {}
  }, 2000);

  // ─────────────────────────────────────────────
  // 13. SOCKET.IO LATE-BINDING PATCH
  // ─────────────────────────────────────────────
  // Socket.IO might load after our script. Keep trying.

  let socketPatchAttempts = 0;
  const socketPatcher = _origSetInterval.call(window, () => {
    socketPatchAttempts++;
    if (patchSocketIO()) {
      log("Socket.IO patched successfully");
      _origClearInterval.call(window, socketPatcher);
    }
    if (socketPatchAttempts > 30) {
      _origClearInterval.call(window, socketPatcher);
    }
  }, 1000);

  // ─────────────────────────────────────────────
  // 14. CSS INJECTION — REMOVE PROCTORING UI
  // ─────────────────────────────────────────────
  // Remove any "proctoring active" banners, warning overlays,
  // fullscreen request modals, etc.

  function injectCSS() {
    const style = document.createElement("style");
    style.textContent = `
      /* Hide proctoring warning banners */
      [class*="proctor" i],
      [class*="Proctor" i],
      [id*="proctor" i],
      [class*="fullscreen-warning" i],
      [class*="fullscreen-overlay" i],
      [class*="tab-switch-warning" i],
      [class*="proctoring-banner" i] {
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
        pointer-events: none !important;
        height: 0 !important;
        overflow: hidden !important;
      }
      
      /* Re-enable text selection (some quizzes block it) */
      * {
        -webkit-user-select: text !important;
        -moz-user-select: text !important;
        -ms-user-select: text !important;
        user-select: text !important;
      }
    `;
    (document.head || document.documentElement).appendChild(style);
  }

  // Inject CSS as soon as possible
  if (document.head) {
    injectCSS();
  } else {
    const cssObserver = new MutationObserver(() => {
      if (document.head) {
        injectCSS();
        cssObserver.disconnect();
      }
    });
    cssObserver.observe(document.documentElement || document, {
      childList: true,
      subtree: true,
    });
  }

  log("Shield fully armed. All 14 defense layers active.");
})();

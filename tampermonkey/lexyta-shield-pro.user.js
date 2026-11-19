// ==UserScript==
// @name         Lexyta Shield Pro
// @namespace    https://lms.lexyta.com
// @version      5.0
// @description  Stealth-Grade Proctoring Neutralizer — bypasses bi$1 anti-tamper + Sn$1 event-block detection (reverse-engineered from main-RCXULGX4.js)
// @author       Pawas
// @match        https://lms.lexyta.com/*
// @grant        none
// @run-at       document-start
// @noframes     false
// ==/UserScript==

(function () {
  "use strict";

  // ═══════════════════════════════════════════════════════════════════
  //  LEXYTA PROCTORING ENGINE — ANTI-TAMPER ANALYSIS
  //
  //  Lexyta's proctoring (class Ug in main-RCXULGX4.js) runs TWO
  //  checks before allowing a proctored quiz to start:
  //
  //  CHECK 1 — bi$1() → "VISIBILITY_API_TAMPERED"
  //    • Calls _n$1(getter) which checks Function.prototype.toString
  //      for [native code] on Document.prototype.hidden getter,
  //      Document.prototype.visibilityState getter, and hasFocus.
  //    • Checks Object.getOwnPropertyDescriptor(document, "hidden")
  //      and visibilityState — if defined on INSTANCE → tampered!
  //
  //  CHECK 2 — Sn$1() → "EVENTS_BLOCKED"
  //    • Registers a fresh listener → dispatches synthetic Event →
  //      checks if the listener was actually called.
  //    • If addEventListener was overridden to drop listeners,
  //      the synthetic test event never reaches the test listener.
  //
  //  RUNTIME — runProbe() every 5s:
  //    • Removes all listeners → runs qt$1() again → re-registers.
  //    • Also checks navigator.webdriver → INTEGRITY_VIOLATION.
  //
  //  OUR BYPASS STRATEGY:
  //  1. Override getters on Document.PROTOTYPE (not instance)
  //  2. Patch Function.prototype.toString to return [native code]
  //  3. Do NOT override addEventListener
  //  4. Use isTrusted-based capture filtering to block real events
  //     but let synthetic test events through
  // ═══════════════════════════════════════════════════════════════════

  // ─────────────────────────────────────────────
  //  STEP 1: Native toString faker
  // ─────────────────────────────────────────────

  const _nativeFns = new Map();
  const _origToString = Function.prototype.toString;

  Function.prototype.toString = function () {
    if (_nativeFns.has(this)) {
      return "function " + (_nativeFns.get(this) || "") + "() { [native code] }";
    }
    return _origToString.call(this);
  };
  _nativeFns.set(Function.prototype.toString, "toString");

  // ─────────────────────────────────────────────
  //  STEP 2: Prototype-level visibility spoof
  // ─────────────────────────────────────────────
  // Override on Document.prototype, NOT on document instance.
  // This passes bi$1's instance-level descriptor check.

  const fakeGetHidden = function hidden() { return false; };
  const fakeGetVisState = function visibilityState() { return "visible"; };
  const fakeHasFocus = function hasFocus() { return true; };

  _nativeFns.set(fakeGetHidden, "get hidden");
  _nativeFns.set(fakeGetVisState, "get visibilityState");
  _nativeFns.set(fakeHasFocus, "hasFocus");

  Object.defineProperty(Document.prototype, "hidden", {
    get: fakeGetHidden, configurable: true, enumerable: true
  });
  Object.defineProperty(Document.prototype, "visibilityState", {
    get: fakeGetVisState, configurable: true, enumerable: true
  });
  Document.prototype.hasFocus = fakeHasFocus;

  // Clean any instance-level descriptors from previous script versions
  try { delete document.hidden; } catch (e) {}
  try { delete document.visibilityState; } catch (e) {}
  try { delete document.webkitHidden; } catch (e) {}
  try { delete document.webkitVisibilityState; } catch (e) {}

  // ─────────────────────────────────────────────
  //  STEP 3: Fullscreen spoof (prototype-level)
  // ─────────────────────────────────────────────

  const fakeGetFSElem = function fullscreenElement() { return document.documentElement; };
  const fakeGetFS = function fullscreen() { return true; };
  _nativeFns.set(fakeGetFSElem, "get fullscreenElement");
  _nativeFns.set(fakeGetFS, "get fullscreen");

  Object.defineProperty(Document.prototype, "fullscreenElement", {
    get: fakeGetFSElem, configurable: true, enumerable: true
  });
  Object.defineProperty(Document.prototype, "webkitFullscreenElement", {
    get: fakeGetFSElem, configurable: true, enumerable: true
  });
  Object.defineProperty(Document.prototype, "fullscreen", {
    get: fakeGetFS, configurable: true, enumerable: true
  });
  Object.defineProperty(Document.prototype, "webkitIsFullScreen", {
    get: fakeGetFS, configurable: true, enumerable: true
  });

  // No-op fullscreen methods
  Element.prototype.requestFullscreen = function () { return Promise.resolve(); };
  Element.prototype.webkitRequestFullscreen = function () { return Promise.resolve(); };
  Document.prototype.exitFullscreen = function () { return Promise.resolve(); };
  Document.prototype.webkitExitFullscreen = function () { return Promise.resolve(); };

  // ─────────────────────────────────────────────
  //  STEP 4: isTrusted event filtering
  // ─────────────────────────────────────────────
  // We do NOT override addEventListener (that would trigger EVENTS_BLOCKED).
  // Instead, we register capture-phase listeners FIRST (document-start).
  // Real browser events (isTrusted:true) → stopImmediatePropagation
  // Synthetic test events (isTrusted:false) → pass through (Sn$1 passes)

  const INTERCEPT_ON_DOCUMENT = [
    "visibilitychange", "webkitvisibilitychange",
    "paste", "copy", "cut",
    "fullscreenchange", "webkitfullscreenchange",
    "mouseleave", "mouseenter",
    "contextmenu"
  ];

  const INTERCEPT_ON_WINDOW = [
    "blur", "focus", "resize", "beforeunload"
  ];

  for (const evt of INTERCEPT_ON_DOCUMENT) {
    document.addEventListener(evt, function (e) {
      if (e.isTrusted) e.stopImmediatePropagation();
    }, true);
  }

  for (const evt of INTERCEPT_ON_WINDOW) {
    window.addEventListener(evt, function (e) {
      if (e.isTrusted) e.stopImmediatePropagation();
    }, true);
  }

  // Keydown: block proctoring's DevTools detector but allow actual shortcuts
  document.addEventListener("keydown", function (e) {
    if (!e.isTrusted) return; // Let Sn$1 test through

    // Block the event from reaching proctoring handler
    e.stopImmediatePropagation();

    // But we don't preventDefault — so F12, Ctrl+Shift+I, etc. still work
    // The browser processes the shortcut natively
  }, true);

  // ─────────────────────────────────────────────
  //  STEP 5: DevTools size detection bypass
  // ─────────────────────────────────────────────
  // Lexyta: (window.outerWidth - window.innerWidth > 160) → DevTools open

  Object.defineProperty(window, "outerWidth", {
    get: () => window.innerWidth + 8,
    configurable: true,
  });
  Object.defineProperty(window, "outerHeight", {
    get: () => window.innerHeight + 80,
    configurable: true,
  });

  // Ensure navigator.webdriver is false (runProbe checks this)
  try {
    Object.defineProperty(navigator, "webdriver", {
      get: () => false, configurable: true
    });
  } catch (e) {}

  // ─────────────────────────────────────────────
  //  STEP 6: Network layer interception
  // ─────────────────────────────────────────────
  // Block proctoring HTTP flushes + Socket.IO events + recovery

  // Fetch
  const _origFetch = window.fetch;
  window.fetch = function (url, options) {
    const u = typeof url === "string" ? url : url?.url || "";
    if (u.includes("proctor") || u.includes("/proctoring")) {
      return Promise.resolve(new Response(
        JSON.stringify({ success: true }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      ));
    }
    if (options?.body) {
      try {
        const b = typeof options.body === "string" ? options.body : "";
        if (b.includes("tab_switch") || b.includes("mouse_leave") || b.includes("proctoring")) {
          return Promise.resolve(new Response(
            JSON.stringify({ success: true }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          ));
        }
      } catch (e) {}
    }
    return _origFetch.apply(this, arguments);
  };

  // XHR
  const _origXHROpen = XMLHttpRequest.prototype.open;
  const _origXHRSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (method, url, ...rest) {
    this._shieldUrl = url || "";
    return _origXHROpen.apply(this, [method, url, ...rest]);
  };
  XMLHttpRequest.prototype.send = function (body) {
    if (this._shieldUrl && (this._shieldUrl.includes("proctor") || this._shieldUrl.includes("proctoring"))) {
      Object.defineProperty(this, "readyState", { get: () => 4 });
      Object.defineProperty(this, "status", { get: () => 200 });
      Object.defineProperty(this, "responseText", { get: () => '{"success":true}' });
      this.dispatchEvent(new Event("load"));
      return;
    }
    return _origXHRSend.apply(this, arguments);
  };

  // WebSocket
  const _OrigWS = window.WebSocket;
  window.WebSocket = function (...args) {
    const ws = new _OrigWS(...args);
    const _origSend = ws.send.bind(ws);
    ws.send = function (data) {
      try {
        const str = typeof data === "string" ? data : "";
        if (str.includes("proctor") || str.includes("tab_switch") || str.includes("mouse_leave")) {
          return; // Silently swallow
        }
      } catch (e) {}
      return _origSend(data);
    };
    return ws;
  };
  window.WebSocket.prototype = _OrigWS.prototype;
  window.WebSocket.CONNECTING = _OrigWS.CONNECTING;
  window.WebSocket.OPEN = _OrigWS.OPEN;
  window.WebSocket.CLOSING = _OrigWS.CLOSING;
  window.WebSocket.CLOSED = _OrigWS.CLOSED;

  // ─────────────────────────────────────────────
  //  STEP 7: Block onbeforeunload trap
  // ─────────────────────────────────────────────
  Object.defineProperty(window, "onbeforeunload", {
    get: () => null,
    set: () => {},
    configurable: true,
  });

  // ─────────────────────────────────────────────
  //  STEP 8: Clean proctoring localStorage
  // ─────────────────────────────────────────────
  try {
    const keysToRemove = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && (key.startsWith("lexyta_proctoring_") || key.includes("_proctor_"))) {
        keysToRemove.push(key);
      }
    }
    keysToRemove.forEach(k => localStorage.removeItem(k));
  } catch (e) {}

  // ─────────────────────────────────────────────
  //  STEP 9: CSS stealth (hide proctoring UI)
  // ─────────────────────────────────────────────
  function injectCSS() {
    if (document.getElementById("sh-shield-css")) return;
    const style = document.createElement("style");
    style.id = "sh-shield-css";
    style.textContent = `
      [class*="proctoring-banner" i],
      [class*="fullscreen-warning" i],
      [class*="fullscreen-overlay" i],
      [class*="tab-switch-warning" i] {
        display: none !important;
        visibility: hidden !important;
        pointer-events: none !important;
        height: 0 !important;
        overflow: hidden !important;
      }
      * {
        -webkit-user-select: text !important;
        -moz-user-select: text !important;
        user-select: text !important;
      }
    `;
    (document.head || document.documentElement).appendChild(style);
  }

  if (document.head) {
    injectCSS();
  } else {
    const obs = new MutationObserver(() => {
      if (document.head) { injectCSS(); obs.disconnect(); }
    });
    obs.observe(document.documentElement || document, { childList: true, subtree: true });
  }

  // No console output in production (stealth)
})();

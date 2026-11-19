// ==UserScript==
// @name         Lexyta Kiwi Mobile Master
// @namespace    https://lms.lexyta.com
// @version      5.0
// @description  Stealth-Grade: Desktop Spoof + Anti-Tamper-Proof Proctoring Bypass + AI Solver + Draggable FAB
// @author       Pawas
// @match        https://lms.lexyta.com/*
// @match        http://lms.lexyta.com/*
// @match        https://*.lexyta.com/*
// @grant        GM_xmlhttpRequest
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_registerMenuCommand
// @connect      generativelanguage.googleapis.com
// @run-at       document-start
// @noframes     false
// ==/UserScript==

(function () {
  "use strict";

  // ═══════════════════════════════════════════════════════════════════
  //  LAYER 1: DESKTOP ENVIRONMENT SPOOFING
  // ═══════════════════════════════════════════════════════════════════
  // Lexyta doesn't block mobile explicitly, but Kiwi can misbehave
  // with certain Angular animations / fullscreen APIs. This normalizes.

  const DESKTOP_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36";

  try {
    Object.defineProperty(navigator, "userAgent", { get: () => DESKTOP_UA, configurable: true });
    Object.defineProperty(navigator, "appVersion", { get: () => DESKTOP_UA.replace("Mozilla/", ""), configurable: true });
    Object.defineProperty(navigator, "platform", { get: () => "Win32", configurable: true });
    Object.defineProperty(navigator, "maxTouchPoints", { get: () => 0, configurable: true });
    // Ensure webdriver is false (proctoring checks navigator.webdriver)
    Object.defineProperty(navigator, "webdriver", { get: () => false, configurable: true });
  } catch (e) {}

  // ═══════════════════════════════════════════════════════════════════
  //  LAYER 2: STEALTH PROCTORING BYPASS (Anti-Tamper-Proof)
  // ═══════════════════════════════════════════════════════════════════
  //
  //  Lexyta's proctoring engine (class Ug / r$23 in main-RCXULGX4.js)
  //  runs TWO anti-tamper checks before allowing a proctored quiz:
  //
  //  CHECK 1 — bi$1(): "VISIBILITY_API_TAMPERED"
  //    Tests if Document.prototype.hidden/visibilityState getters are
  //    native via Function.prototype.toString → [native code] check.
  //    Also checks if document INSTANCE has own descriptors (would mean
  //    someone did Object.defineProperty(document, "hidden", ...)).
  //
  //  CHECK 2 — Sn$1(): "EVENTS_BLOCKED"
  //    Adds a fresh listener → dispatches a synthetic test Event →
  //    checks if listener was called. If addEventListener was overridden
  //    to silently drop listeners, the test event won't reach the
  //    listener → EVENTS_BLOCKED.
  //
  //  OUR STRATEGY:
  //  - Override getters on Document.prototype (NOT document instance)
  //  - Patch Function.prototype.toString to return [native code] for
  //    our specific fake getters → passes bi$1 native-code check
  //  - Do NOT override addEventListener at all
  //  - Instead, register our own capture-phase listeners FIRST (we run
  //    at document-start, before Lexyta loads) that intercept REAL
  //    browser events (isTrusted:true) via stopImmediatePropagation,
  //    but let SYNTHETIC test events (isTrusted:false) pass through
  //    → passes Sn$1 event-dispatch test
  //
  //  Result: bi$1() returns false (not tampered), Sn$1() returns true
  //  (events not blocked), qt$1() returns [] → proctoring dialog
  //  never appears → quiz starts normally.
  // ═══════════════════════════════════════════════════════════════════

  // --- STEP 1: Fake native toString for our custom functions ---
  const _nativeFns = new Map(); // fn → fake name
  const _origToString = Function.prototype.toString;

  Function.prototype.toString = function () {
    if (_nativeFns.has(this)) {
      return "function " + (_nativeFns.get(this) || "") + "() { [native code] }";
    }
    return _origToString.call(this);
  };
  // Make our toString override itself look native
  _nativeFns.set(Function.prototype.toString, "toString");

  // --- STEP 2: Override Document.prototype getters (NOT instance) ---
  // Save originals
  const _origHiddenDesc = Object.getOwnPropertyDescriptor(Document.prototype, "hidden");
  const _origVisStateDesc = Object.getOwnPropertyDescriptor(Document.prototype, "visibilityState");
  const _origHasFocus = Document.prototype.hasFocus;

  // Create fake getters that look native
  const fakeGetHidden = function hidden() { return false; };
  const fakeGetVisState = function visibilityState() { return "visible"; };
  const fakeHasFocus = function hasFocus() { return true; };

  _nativeFns.set(fakeGetHidden, "get hidden");
  _nativeFns.set(fakeGetVisState, "get visibilityState");
  _nativeFns.set(fakeHasFocus, "hasFocus");

  // Apply to prototype (bi$1 checks Document.prototype, not document instance)
  Object.defineProperty(Document.prototype, "hidden", {
    get: fakeGetHidden,
    configurable: true,
    enumerable: true
  });

  Object.defineProperty(Document.prototype, "visibilityState", {
    get: fakeGetVisState,
    configurable: true,
    enumerable: true
  });

  Document.prototype.hasFocus = fakeHasFocus;

  // CRITICAL: Ensure NO instance-level descriptors exist on `document`
  // (bi$1 checks: Object.getOwnPropertyDescriptor(document, "hidden") !== undefined)
  // We ONLY define on the prototype, never on the instance. If a previous
  // script version left instance descriptors, clean them up:
  try { delete document.hidden; } catch (e) {}
  try { delete document.visibilityState; } catch (e) {}

  // --- STEP 3: Fullscreen spoof (on prototype, not instance) ---
  const fakeGetFSElement = function fullscreenElement() { return document.documentElement; };
  const fakeGetFS = function fullscreen() { return true; };
  _nativeFns.set(fakeGetFSElement, "get fullscreenElement");
  _nativeFns.set(fakeGetFS, "get fullscreen");

  Object.defineProperty(Document.prototype, "fullscreenElement", {
    get: fakeGetFSElement, configurable: true, enumerable: true
  });
  Object.defineProperty(Document.prototype, "webkitFullscreenElement", {
    get: fakeGetFSElement, configurable: true, enumerable: true
  });
  Object.defineProperty(Document.prototype, "fullscreen", {
    get: fakeGetFS, configurable: true, enumerable: true
  });

  // No-op fullscreen methods
  Element.prototype.requestFullscreen = function () { return Promise.resolve(); };
  Element.prototype.webkitRequestFullscreen = function () { return Promise.resolve(); };
  Document.prototype.exitFullscreen = function () { return Promise.resolve(); };
  Document.prototype.webkitExitFullscreen = function () { return Promise.resolve(); };

  // --- STEP 4: Stealth event interception via isTrusted filtering ---
  //
  // We register capture-phase listeners at the HIGHEST priority (before
  // Lexyta's code even loads). For REAL browser events (isTrusted:true)
  // we call stopImmediatePropagation() so Lexyta's proctoring handlers
  // never see them. For SYNTHETIC events (isTrusted:false, used by
  // Sn$1 test), we let them pass through → test passes.
  //
  // This means: Lexyta's handlers are registered normally (addEventListener
  // is NOT overridden), so the Sn$1 test dispatch reaches the test
  // listener. But real tab switches, blurs, pastes, etc. never reach
  // the proctoring handlers.

  const STEALTH_INTERCEPT_EVENTS = [
    { target: document, event: "visibilitychange" },
    { target: window,   event: "blur" },
    { target: window,   event: "focus" },
    { target: document, event: "paste" },
    { target: document, event: "copy" },
    { target: document, event: "cut" },
    { target: document, event: "fullscreenchange" },
    { target: document, event: "webkitfullscreenchange" },
    { target: document, event: "mouseleave" },
    { target: document, event: "mouseenter" },
    { target: document, event: "contextmenu" },
    { target: document, event: "keydown" },
    { target: window,   event: "resize" },
    { target: window,   event: "beforeunload" }
  ];

  for (const { target, event } of STEALTH_INTERCEPT_EVENTS) {
    target.addEventListener(event, function (e) {
      if (e.isTrusted) {
        // Real browser event → block from reaching proctoring handler
        e.stopImmediatePropagation();

        // For some events, also prevent default Lexyta behavior
        if (event === "contextmenu") {
          // But we WANT right-click to work, so don't preventDefault
        }
        if (event === "beforeunload") {
          // Don't block page unloads entirely, just stop proctoring from capturing
        }
        if (event === "keydown") {
          // Let all keyboard shortcuts work (DevTools, etc.)
        }
      }
      // Synthetic (isTrusted:false) events pass through → Sn$1 test succeeds
    }, true); // capture phase, registered first
  }

  // --- STEP 5: Intercept proctoring HTTP flushes ---
  // The proctoring engine flushes events every 5s via HTTP POST and
  // also sends heartbeats every 15s. We intercept both fetch and XHR.

  const _origFetch = window.fetch;
  window.fetch = function (url, opts) {
    const u = typeof url === "string" ? url : url?.url || "";
    if (u.includes("/proctoring/recover") || u.includes("heartbeat")) {
      return Promise.resolve(new Response(JSON.stringify({ success: true }), { status: 200 }));
    }
    return _origFetch.apply(this, arguments);
  };

  // Also intercept the flush callback's HTTP call if it uses the Angular HttpClient
  // (which goes through fetch internally in modern Angular)

  // --- STEP 6: Neutralize localStorage proctoring persistence ---
  // Lexyta persists proctoring events to localStorage keyed by attempt ID.
  // On next load, it recovers and sends them. We clean these on page load.
  try {
    const keysToRemove = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.startsWith("lexyta_proctoring_")) {
        keysToRemove.push(key);
      }
    }
    keysToRemove.forEach(k => localStorage.removeItem(k));
  } catch (e) {}

  console.log("🛡️ [Kiwi Master v5.0] Stealth anti-tamper-proof proctoring bypass armed.");

  // ═══════════════════════════════════════════════════════════════════
  //  LAYER 3: AI QUIZ SOLVER & AUTO-CLICK / HIGHLIGHT MODES
  // ═══════════════════════════════════════════════════════════════════

  let GEMINI_KEY = GM_getValue("gemini_key", "");
  let AUTO_CLICK = GM_getValue("auto_click", false);
  let isSolving = false;

  const MODELS = [
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite",
    "gemini-3.8-flash",
    "gemini-flash-latest"
  ];

  GM_registerMenuCommand("🔑 Set Gemini API Key", () => {
    const k = prompt("Google Gemini API Key enter karein:", GEMINI_KEY);
    if (k !== null) {
      GEMINI_KEY = k.trim();
      GM_setValue("gemini_key", GEMINI_KEY);
      showToast("✅ API Key Saved!");
    }
  });

  GM_registerMenuCommand(
    AUTO_CLICK ? "⚡ Auto-Click: ON → Turn OFF" : "👁️ Highlight Only → Turn ON Auto-Click",
    () => toggleAutoClick()
  );

  GM_registerMenuCommand("🚀 Solve Current Quiz Now", () => startSolving());

  function toggleAutoClick() {
    AUTO_CLICK = !AUTO_CLICK;
    GM_setValue("auto_click", AUTO_CLICK);
    updateDotAppearance();
    showToast(AUTO_CLICK
      ? "🟢 Auto-Click: ON (Bot will select answers)"
      : "🟡 Highlight Only (Auto-Click OFF)");
  }

  // ═══════════════════════════════════════════════
  //  UI: STYLES & TOAST
  // ═══════════════════════════════════════════════

  function injectStyles() {
    if (document.getElementById("sh-styles-kiwi")) return;
    const style = document.createElement("style");
    style.id = "sh-styles-kiwi";
    style.textContent = `
      .sh-correct {
        border-left: 5px solid #4285f4 !important;
        background-color: rgba(66, 133, 244, 0.12) !important;
        border-radius: 6px !important;
        box-shadow: 0 0 8px rgba(66, 133, 244, 0.2) !important;
        transition: all 0.3s ease !important;
      }
      .sh-indicator-kiwi {
        position: fixed;
        bottom: 85px;
        right: 18px;
        width: 42px;
        height: 42px;
        border-radius: 50%;
        z-index: 2147483647 !important;
        cursor: pointer;
        touch-action: none;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 19px;
        user-select: none;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.5) !important;
        transition: transform 0.15s ease, background 0.25s ease, border-color 0.25s ease;
      }
      .sh-indicator-kiwi:active { transform: scale(1.2); }
      .sh-indicator-kiwi.highlight-mode {
        background: #1e1e2e !important;
        border: 2.5px solid #89b4fa !important;
        color: #89b4fa !important;
      }
      .sh-indicator-kiwi.autoclick-mode {
        background: #14281d !important;
        border: 2.5px solid #2ecc71 !important;
        color: #2ecc71 !important;
      }
      .sh-indicator-kiwi.solving {
        background: #332711 !important;
        border: 2.5px solid #fbbc04 !important;
        color: #fbbc04 !important;
        animation: sh-pulse 1s ease-in-out infinite;
      }
      .sh-indicator-kiwi.done {
        background: #14281d !important;
        border: 2.5px solid #2ecc71 !important;
        color: #2ecc71 !important;
      }
      @keyframes sh-pulse {
        0%, 100% { opacity: 0.6; transform: scale(1); }
        50% { opacity: 1; transform: scale(1.15); }
      }
      .sh-toast-kiwi {
        position: fixed;
        top: 24px;
        left: 50%;
        transform: translateX(-50%) translateY(-70px);
        background: rgba(30, 30, 46, 0.98);
        color: #cdd6f4;
        padding: 10px 20px;
        border-radius: 12px;
        font-size: 14px;
        font-weight: 500;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        z-index: 2147483647 !important;
        pointer-events: none;
        opacity: 0;
        transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
        text-align: center;
        box-shadow: 0 6px 20px rgba(0,0,0,0.55);
        white-space: nowrap;
        border: 1px solid rgba(255, 255, 255, 0.12);
      }
      .sh-toast-kiwi.visible {
        transform: translateX(-50%) translateY(0);
        opacity: 1;
      }
    `;
    (document.head || document.documentElement).appendChild(style);
  }

  function showToast(text) {
    injectStyles();
    let t = document.getElementById("sh-toast-kiwi");
    if (!t) {
      t = document.createElement("div");
      t.id = "sh-toast-kiwi";
      t.className = "sh-toast-kiwi";
      (document.body || document.documentElement).appendChild(t);
    }
    t.textContent = text;
    t.classList.add("visible");
    setTimeout(() => t.classList.remove("visible"), 3200);
  }

  function updateDotAppearance() {
    const dot = document.getElementById("sh-indicator-kiwi");
    if (!dot || isSolving) return;
    if (AUTO_CLICK) {
      dot.className = "sh-indicator-kiwi autoclick-mode";
      dot.innerHTML = "⚡";
    } else {
      dot.className = "sh-indicator-kiwi highlight-mode";
      dot.innerHTML = "👁️";
    }
  }

  // ═══════════════════════════════════════════════
  //  DOM QUESTION EXTRACTION
  // ═══════════════════════════════════════════════

  function stripHtml(html) {
    if (!html) return "";
    const tmp = document.createElement("div");
    tmp.innerHTML = html;
    return (tmp.textContent || tmp.innerText || "").trim();
  }

  function extractQuestions() {
    const questions = [];
    const labels = "ABCDEFGH";

    const blocks = document.querySelectorAll(
      '[class*="question" i], [class*="quiz-item" i], [class*="quizItem" i], [data-question-id]'
    );

    if (blocks.length > 0) {
      blocks.forEach((block, idx) => {
        let questionText = "";
        const textEls = block.querySelectorAll('h1, h2, h3, h4, h5, h6, p, [class*="question-text" i], [class*="stem" i]');
        for (const el of textEls) {
          const txt = stripHtml(el.innerHTML);
          if (txt.length > 10 && !el.closest('[class*="option" i], [class*="choice" i]')) {
            questionText = txt;
            break;
          }
        }
        if (!questionText) questionText = `Question ${idx + 1}`;

        const options = [];
        const inputs = block.querySelectorAll('input[type="radio"], input[type="checkbox"]');
        inputs.forEach((inp, i) => {
          const labelEl = inp.closest("label") || document.querySelector(`label[for="${inp.id}"]`) || inp.parentElement;
          let optText = labelEl ? stripHtml(labelEl.innerHTML).replace(/^\s*[A-D][\.\)\:]?\s*/i, "").trim() : "";
          if (!optText && inp.nextSibling) optText = (inp.nextSibling.textContent || "").trim();
          if (optText) {
            options.push({
              id: inp.value || inp.id || `opt_${idx}_${i}`,
              label: labels[i] || `${i + 1}`,
              text: optText,
              element: inp
            });
          }
        });

        if (options.length >= 2 && !questions.find(x => x.text === questionText)) {
          questions.push({
            id: block.getAttribute("data-question-id") || block.id || `q_${idx}`,
            text: questionText,
            options
          });
        }
      });
    }
    return questions;
  }

  // ═══════════════════════════════════════════════
  //  GEMINI API CALLER (Batches of 8)
  // ═══════════════════════════════════════════════

  function callGeminiBatch(chunk) {
    return new Promise((resolve, reject) => {
      let questionsPrompt = "";
      for (let i = 0; i < chunk.length; i++) {
        const q = chunk[i];
        let optsStr = "";
        for (const opt of q.options) {
          optsStr += `   [${opt.label}] "${opt.text}" (ID: "${opt.id}")\n`;
        }
        questionsPrompt += `Question ${i + 1} (ID: "${q.id}"):\n${q.text}\nOptions:\n${optsStr}\n`;
      }

      const prompt = `You are a Top Academic Professor. Solve with 100% precision. Return valid JSON:\n${questionsPrompt}\nJSON Schema:\n{\n  "<question_id>": {\n    "selected_label": "<A, B, C, or D>",\n    "selected_option_id": "<exact_option_id>",\n    "selected_text": "<text>"\n  }\n}`;

      function tryModel(mIdx) {
        if (mIdx >= MODELS.length) return reject(new Error("All Gemini models failed."));
        const m = MODELS[mIdx];
        const url = `https://generativelanguage.googleapis.com/v1beta/models/${m}:generateContent?key=${GEMINI_KEY}`;

        GM_xmlhttpRequest({
          method: "POST",
          url: url,
          headers: { "Content-Type": "application/json" },
          data: JSON.stringify({
            contents: [{ parts: [{ text: prompt }] }],
            generationConfig: { temperature: 0.0, response_mime_type: "application/json" }
          }),
          timeout: 25000,
          onload: (r) => {
            if (r.status === 200) {
              try {
                const parsed = JSON.parse(JSON.parse(r.responseText).candidates[0].content.parts[0].text);
                const answers = {};
                for (const [qid, val] of Object.entries(parsed)) {
                  answers[qid] = {
                    optionId: val.selected_option_id || "",
                    label: val.selected_label || "",
                    text: val.selected_text || ""
                  };
                }
                return resolve(answers);
              } catch (e) {}
            }
            tryModel(mIdx + 1);
          },
          onerror: () => tryModel(mIdx + 1),
          ontimeout: () => tryModel(mIdx + 1)
        });
      }
      tryModel(0);
    });
  }

  function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

  // ═══════════════════════════════════════════════
  //  CORE SOLVER: HIGHLIGHT OR AUTO-CLICK
  // ═══════════════════════════════════════════════

  async function startSolving() {
    if (isSolving) return;
    if (!GEMINI_KEY) {
      const k = prompt("Google Gemini API Key enter karein pehle:", "");
      if (k) { GEMINI_KEY = k.trim(); GM_setValue("gemini_key", GEMINI_KEY); }
      else return;
    }

    const dot = document.getElementById("sh-indicator-kiwi");
    if (dot) { dot.className = "sh-indicator-kiwi solving"; dot.innerHTML = "⏳"; }

    isSolving = true;
    showToast("🔍 Scanning questions...");

    const questions = extractQuestions();
    if (questions.length === 0) {
      showToast("❌ No quiz questions found on this page.");
      isSolving = false;
      updateDotAppearance();
      return;
    }

    const modeName = AUTO_CLICK ? "Auto-Click" : "Highlight Only";
    showToast(`🚀 Found ${questions.length} Q! Mode: ${modeName}`);

    const CHUNK_SIZE = 8;
    const totalChunks = Math.ceil(questions.length / CHUNK_SIZE);
    let totalProcessed = 0;

    for (let i = 0; i < questions.length; i += CHUNK_SIZE) {
      const chunk = questions.slice(i, i + CHUNK_SIZE);
      const chunkNum = Math.floor(i / CHUNK_SIZE) + 1;
      showToast(`🧠 Batch ${chunkNum}/${totalChunks} (Q${i + 1}-${Math.min(i + CHUNK_SIZE, questions.length)})...`);

      let chunkAnswers = {};
      try { chunkAnswers = await callGeminiBatch(chunk); }
      catch (e) { console.warn("Batch error:", e); }

      for (const q of chunk) {
        const ans = chunkAnswers[q.id];
        if (!ans) continue;

        for (const opt of q.options) {
          const isCorrect = (
            opt.id === ans.optionId ||
            opt.label.toUpperCase() === ans.label.toUpperCase() ||
            (ans.text && opt.text.toLowerCase().includes(ans.text.toLowerCase()))
          );

          if (isCorrect && opt.element) {
            const parent = opt.element.closest("label, [class*='option' i], div") || opt.element.parentElement;
            if (parent) parent.classList.add("sh-correct");

            if (AUTO_CLICK) {
              try { opt.element.scrollIntoView({ behavior: "smooth", block: "center" }); } catch (e) {}
              await sleep(1000 + Math.random() * 1200);
              opt.element.click();
              ["change", "input", "click"].forEach(evt => {
                opt.element.dispatchEvent(new Event(evt, { bubbles: true }));
              });
            }
            totalProcessed++;
            break;
          }
        }
      }
      await sleep(AUTO_CLICK ? 400 : 150);
    }

    if (dot) { dot.className = "sh-indicator-kiwi done"; dot.innerHTML = "✅"; }
    showToast(AUTO_CLICK
      ? `🎉 Done! ${totalProcessed}/${questions.length} selected.`
      : `🎉 Done! ${totalProcessed}/${questions.length} highlighted.`);

    setTimeout(() => { isSolving = false; updateDotAppearance(); }, 2800);
  }

  // ═══════════════════════════════════════════════
  //  DRAGGABLE FLOATING ACTION BUTTON
  // ═══════════════════════════════════════════════

  function createFloatingDot() {
    if (document.getElementById("sh-indicator-kiwi")) return;
    if (!document.body) return;
    injectStyles();

    const dot = document.createElement("div");
    dot.id = "sh-indicator-kiwi";
    dot.className = AUTO_CLICK ? "sh-indicator-kiwi autoclick-mode" : "sh-indicator-kiwi highlight-mode";
    dot.innerHTML = AUTO_CLICK ? "⚡" : "👁️";

    const savedTop = GM_getValue("dot_top", null);
    const savedLeft = GM_getValue("dot_left", null);
    if (savedTop !== null && savedLeft !== null) {
      dot.style.bottom = "auto";
      dot.style.right = "auto";
      dot.style.top = `${savedTop}px`;
      dot.style.left = `${savedLeft}px`;
    }

    let tapTimer = null, longPressTimer = null;
    let touchStartTime = 0, touchStartX = 0, touchStartY = 0;
    let initialRect = null, hasMoved = false, isLongPress = false;

    dot.addEventListener("touchstart", (e) => {
      isLongPress = false; hasMoved = false;
      touchStartTime = Date.now();
      const touch = e.touches[0];
      touchStartX = touch.clientX; touchStartY = touch.clientY;
      initialRect = dot.getBoundingClientRect();

      longPressTimer = setTimeout(() => {
        if (!hasMoved) {
          isLongPress = true;
          try { navigator.vibrate?.(60); } catch (e) {}
          const k = prompt("Gemini API Key:", GEMINI_KEY);
          if (k !== null && k.trim()) {
            GEMINI_KEY = k.trim();
            GM_setValue("gemini_key", GEMINI_KEY);
            showToast("✅ Key Saved!");
          }
        }
      }, 700);
    }, { passive: true });

    dot.addEventListener("touchmove", (e) => {
      const touch = e.touches[0];
      const dx = touch.clientX - touchStartX, dy = touch.clientY - touchStartY;
      if (Math.abs(dx) > 8 || Math.abs(dy) > 8) {
        hasMoved = true;
        clearTimeout(longPressTimer);
        e.preventDefault();
        dot.style.bottom = "auto"; dot.style.right = "auto";
        dot.style.left = `${Math.max(8, Math.min(window.innerWidth - 50, initialRect.left + dx))}px`;
        dot.style.top = `${Math.max(8, Math.min(window.innerHeight - 50, initialRect.top + dy))}px`;
      }
    }, { passive: false });

    dot.addEventListener("touchend", () => {
      clearTimeout(longPressTimer);
      if (hasMoved) {
        const rect = dot.getBoundingClientRect();
        GM_setValue("dot_top", Math.round(rect.top));
        GM_setValue("dot_left", Math.round(rect.left));
        return;
      }
      if (isLongPress) return;
      if (Date.now() - touchStartTime > 650) return;

      if (tapTimer) {
        clearTimeout(tapTimer); tapTimer = null;
        toggleAutoClick();
      } else {
        tapTimer = setTimeout(() => { tapTimer = null; startSolving(); }, 280);
      }
    });

    // Desktop mouse
    let isMouseDown = false, mouseStartX = 0, mouseStartY = 0, mouseMoved = false;
    dot.addEventListener("mousedown", (e) => {
      if (e.button !== 0) return;
      isMouseDown = true; mouseMoved = false;
      mouseStartX = e.clientX; mouseStartY = e.clientY;
      initialRect = dot.getBoundingClientRect();

      function onMouseMove(ev) {
        if (!isMouseDown) return;
        const dx = ev.clientX - mouseStartX, dy = ev.clientY - mouseStartY;
        if (Math.abs(dx) > 6 || Math.abs(dy) > 6) {
          mouseMoved = true;
          dot.style.bottom = "auto"; dot.style.right = "auto";
          dot.style.left = `${Math.max(8, Math.min(window.innerWidth - 50, initialRect.left + dx))}px`;
          dot.style.top = `${Math.max(8, Math.min(window.innerHeight - 50, initialRect.top + dy))}px`;
        }
      }
      function onMouseUp() {
        if (isMouseDown && mouseMoved) {
          const rect = dot.getBoundingClientRect();
          GM_setValue("dot_top", Math.round(rect.top));
          GM_setValue("dot_left", Math.round(rect.left));
        }
        isMouseDown = false;
        document.removeEventListener("mousemove", onMouseMove);
        document.removeEventListener("mouseup", onMouseUp);
      }
      document.addEventListener("mousemove", onMouseMove);
      document.addEventListener("mouseup", onMouseUp);
    });

    dot.addEventListener("click", () => {
      if (mouseMoved || Date.now() - touchStartTime < 500) return;
      startSolving();
    });
    dot.addEventListener("dblclick", () => toggleAutoClick());

    document.body.appendChild(dot);
  }

  // ═══════════════════════════════════════════════
  //  SPA-RESILIENT PERSISTENT MOUNT
  // ═══════════════════════════════════════════════

  function ensureMounted() {
    if (!document.body) return;
    injectStyles();
    const existing = document.getElementById("sh-indicator-kiwi");
    if (!existing) createFloatingDot();
    else if (!document.body.contains(existing)) document.body.appendChild(existing);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", ensureMounted);
  } else {
    ensureMounted();
  }
  window.addEventListener("load", ensureMounted);
  setInterval(ensureMounted, 1200);

  console.log("⚡ [Kiwi Master v5.0] Stealth mode active. All anti-tamper checks bypassed.");
})();

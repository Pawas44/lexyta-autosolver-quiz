// ==UserScript==
// @name         Lexyta Kiwi Mobile Master
// @namespace    https://lms.lexyta.com
// @version      4.2
// @description  All-in-One Kiwi Mobile Fix: Desktop Environment Spoof + Complete Proctoring Neutralizer + AI Solver with Auto-Click ON/OFF Toggle + Draggable Floating UI
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
  //  LAYER 1: DESKTOP SPOOFING (Fixes Kiwi Mobile Quirks & Blocks)
  // ═══════════════════════════════════════════════════════════════════
  // Makes Kiwi Browser on Android report as a High-End Windows 10 PC.
  // This bypasses any "Mobile device not supported" or mobile layout bugs!

  const DESKTOP_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36";

  try {
    Object.defineProperty(navigator, "userAgent", { get: () => DESKTOP_UA, configurable: true });
    Object.defineProperty(navigator, "appVersion", { get: () => DESKTOP_UA.replace("Mozilla/", ""), configurable: true });
    Object.defineProperty(navigator, "platform", { get: () => "Win32", configurable: true });
    Object.defineProperty(navigator, "maxTouchPoints", { get: () => 0, configurable: true });
  } catch (e) {}

  // ═══════════════════════════════════════════════════════════════════
  //  LAYER 2: PROCTORING & FULLSCREEN NEUTRALIZER (Fixes Kiwi Crash)
  // ═══════════════════════════════════════════════════════════════════
  // Lexyta checks fullscreen and fires fullscreen_exits on mobile because
  // Android doesn't have native desktop fullscreen. We lock it to ALWAYS TRUE.

  // 1. Lock Fullscreen getters to return document element (always in fullscreen)
  Object.defineProperty(document, "fullscreenElement", { get: () => document.documentElement, configurable: true });
  Object.defineProperty(document, "webkitFullscreenElement", { get: () => document.documentElement, configurable: true });
  Object.defineProperty(document, "fullscreen", { get: () => true, configurable: true });
  Object.defineProperty(document, "webkitIsFullScreen", { get: () => true, configurable: true });

  // 2. Fullscreen methods = no-op (never throws error)
  Element.prototype.requestFullscreen = () => Promise.resolve();
  Element.prototype.webkitRequestFullscreen = () => Promise.resolve();
  Document.prototype.exitFullscreen = () => Promise.resolve();
  Document.prototype.webkitExitFullscreen = () => Promise.resolve();

  // 3. Visibility lockdown (tab switch & minimize protection)
  Object.defineProperty(document, "visibilityState", { get: () => "visible", configurable: true });
  Object.defineProperty(document, "hidden", { get: () => false, configurable: true });
  Document.prototype.hasFocus = () => true;

  // 4. Drop proctoring event listeners before Lexyta registers them
  const BLOCKED_EVENTS = new Set([
    "visibilitychange", "webkitvisibilitychange", "pagehide",
    "blur", "focus", "mouseleave", "mouseout",
    "fullscreenchange", "webkitfullscreenchange",
    "copy", "cut", "paste", "contextmenu"
  ]);

  const _origAddEventListener = EventTarget.prototype.addEventListener;
  EventTarget.prototype.addEventListener = function (type, listener, options) {
    if (BLOCKED_EVENTS.has(type) && (!listener || !listener._allowedByPawas)) {
      return; // Silently drop Lexyta's tracking listener
    }
    return _origAddEventListener.call(this, type, listener, options);
  };

  // Re-enable right click & keyboard shortcuts
  window.addEventListener("contextmenu", (e) => e.stopPropagation(), true);

  // 5. Intercept Socket.IO & HTTP Proctoring Flushes
  const _origFetch = window.fetch;
  window.fetch = function (url, opts) {
    const u = typeof url === "string" ? url : url?.url || "";
    if (u.includes("proctor") || u.includes("heartbeat")) {
      return Promise.resolve(new Response(JSON.stringify({ success: true }), { status: 200 }));
    }
    return _origFetch.apply(this, arguments);
  };

  console.log("🛡️ [Kiwi Master v4.2] Desktop spoof & anti-proctoring armed.");

  // ═══════════════════════════════════════════════════════════════════
  //  LAYER 3: AI QUIZ SOLVER & AUTO-CLICK / HIGHLIGHT MODES
  // ═══════════════════════════════════════════════════════════════════

  let GEMINI_KEY = GM_getValue("gemini_key", "");
  let AUTO_CLICK = GM_getValue("auto_click", false); // Default: false (Safe Highlight Only)
  let isSolving = false;

  const MODELS = [
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite",
    "gemini-3.8-flash",
    "gemini-flash-latest"
  ];

  // Tampermonkey Menu Commands
  GM_registerMenuCommand("🔑 Set Gemini API Key", () => {
    const k = prompt("Google Gemini API Key enter karein:", GEMINI_KEY);
    if (k !== null) {
      GEMINI_KEY = k.trim();
      GM_setValue("gemini_key", GEMINI_KEY);
      showToast("✅ API Key Saved!");
    }
  });

  GM_registerMenuCommand(
    AUTO_CLICK ? "⚡ Mode: Auto-Click is [ON] (Click to turn OFF)" : "👁️ Mode: Highlight Only [OFF] (Click to turn ON Auto-Click)",
    () => {
      toggleAutoClick();
    }
  );

  GM_registerMenuCommand("🚀 Solve Current Quiz Now", () => {
    startSolving();
  });

  function toggleAutoClick() {
    AUTO_CLICK = !AUTO_CLICK;
    GM_setValue("auto_click", AUTO_CLICK);
    updateDotAppearance();
    if (AUTO_CLICK) {
      showToast("🟢 Auto-Click: ON (Bot will select answers on screen)");
    } else {
      showToast("🟡 Highlight Only: ON (Auto-Click OFF - You tap manually)");
    }
  }

  // Inject Styles
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
      .sh-indicator-kiwi:active {
        transform: scale(1.2);
      }
      /* Highlight Only Mode (Subtle Blue & 👁️ - Auto-Click OFF) */
      .sh-indicator-kiwi.highlight-mode {
        background: #1e1e2e !important;
        border: 2.5px solid #89b4fa !important;
        color: #89b4fa !important;
      }
      /* Auto-Click Mode (Subtle Emerald Green & ⚡ - Auto-Click ON) */
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
      dot.title = "Mode: Auto-Click ON (Double-tap to turn OFF | Drag to move)";
    } else {
      dot.className = "sh-indicator-kiwi highlight-mode";
      dot.innerHTML = "👁️";
      dot.title = "Mode: Highlight Only (Double-tap to turn ON Auto-Click | Drag to move)";
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
        if (mIdx >= MODELS.length) {
          return reject(new Error("Gemini AI models failed."));
        }
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

  function sleep(ms) {
    return new Promise(r => setTimeout(r, ms));
  }

  // ═══════════════════════════════════════════════
  //  CORE SOLVER: HIGHLIGHT OR AUTO-CLICK
  // ═══════════════════════════════════════════════

  async function startSolving() {
    if (isSolving) return;
    if (!GEMINI_KEY) {
      const k = prompt("Google Gemini API Key enter karein pehle:", "");
      if (k) {
        GEMINI_KEY = k.trim();
        GM_setValue("gemini_key", GEMINI_KEY);
      } else {
        return;
      }
    }

    const dot = document.getElementById("sh-indicator-kiwi");
    if (dot) {
      dot.className = "sh-indicator-kiwi solving";
      dot.innerHTML = "⏳";
    }

    isSolving = true;
    showToast("🔍 Scanning questions on Kiwi...");

    const questions = extractQuestions();
    if (questions.length === 0) {
      showToast("❌ No quiz questions found on this page.");
      isSolving = false;
      updateDotAppearance();
      return;
    }

    const modeName = AUTO_CLICK ? "Auto-Click ON" : "Highlight Only";
    showToast(`🚀 Found ${questions.length} questions! Mode: ${modeName}...`);

    const CHUNK_SIZE = 8;
    const totalChunks = Math.ceil(questions.length / CHUNK_SIZE);
    let totalProcessed = 0;

    for (let i = 0; i < questions.length; i += CHUNK_SIZE) {
      const chunk = questions.slice(i, i + CHUNK_SIZE);
      const chunkNum = Math.floor(i / CHUNK_SIZE) + 1;
      showToast(`🧠 Solving batch ${chunkNum}/${totalChunks} (Q${i + 1}-Q${Math.min(i + CHUNK_SIZE, questions.length)})...`);

      let chunkAnswers = {};
      try {
        chunkAnswers = await callGeminiBatch(chunk);
      } catch (e) {
        console.warn("Batch solve error:", e);
      }

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
              // Smoothly scroll to question on screen
              try {
                opt.element.scrollIntoView({ behavior: "smooth", block: "center" });
              } catch (e) {}

              // Natural human reading delay (1.0 - 2.2 seconds per question)
              await sleep(1000 + Math.random() * 1200);

              // Click option & dispatch events
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

      // Safe inter-batch breather
      await sleep(AUTO_CLICK ? 400 : 150);
    }

    if (dot) {
      dot.className = "sh-indicator-kiwi done";
      dot.innerHTML = "✅";
    }

    if (AUTO_CLICK) {
      showToast(`🎉 Done! ${totalProcessed}/${questions.length} answers selected on screen.`);
    } else {
      showToast(`🎉 Done! ${totalProcessed}/${questions.length} answers highlighted. (Tap manually)`);
    }

    setTimeout(() => {
      isSolving = false;
      updateDotAppearance();
    }, 2800);
  }

  // ═══════════════════════════════════════════════
  //  DRAGGABLE & GESTURE-CONTROLLED FLOATING DOT
  // ═══════════════════════════════════════════════
  // - Single Tap:  Start Solving (using current mode)
  // - Double Tap:  Toggle Auto-Click ON / OFF
  // - Long Press:  API Key Dialog
  // - Touch Drag:  Freely move the dot anywhere on screen!

  function createFloatingDot() {
    if (document.getElementById("sh-indicator-kiwi")) return;
    if (!document.body) return;

    injectStyles();

    const dot = document.createElement("div");
    dot.id = "sh-indicator-kiwi";
    dot.className = AUTO_CLICK ? "sh-indicator-kiwi autoclick-mode" : "sh-indicator-kiwi highlight-mode";
    dot.innerHTML = AUTO_CLICK ? "⚡" : "👁️";
    dot.title = AUTO_CLICK ? "Mode: Auto-Click ON (Double-tap to turn OFF | Drag to move)" : "Mode: Highlight Only (Double-tap to turn ON Auto-Click | Drag to move)";

    // Restore saved drag position if available
    const savedTop = GM_getValue("dot_top", null);
    const savedLeft = GM_getValue("dot_left", null);
    if (savedTop !== null && savedLeft !== null) {
      dot.style.bottom = "auto";
      dot.style.right = "auto";
      dot.style.top = `${savedTop}px`;
      dot.style.left = `${savedLeft}px`;
    }

    let tapTimer = null;
    let longPressTimer = null;
    let touchStartTime = 0;
    let touchStartX = 0, touchStartY = 0;
    let initialRect = null;
    let hasMoved = false;
    let isLongPress = false;

    // --- TOUCH EVENTS (Mobile) ---
    dot.addEventListener("touchstart", (e) => {
      isLongPress = false;
      hasMoved = false;
      touchStartTime = Date.now();
      const touch = e.touches[0];
      touchStartX = touch.clientX;
      touchStartY = touch.clientY;
      initialRect = dot.getBoundingClientRect();

      longPressTimer = setTimeout(() => {
        if (!hasMoved) {
          isLongPress = true;
          try { if (navigator.vibrate) navigator.vibrate(60); } catch (e) {}
          const k = prompt("Gemini API Key update karein (cancel to keep):", GEMINI_KEY);
          if (k !== null && k.trim()) {
            GEMINI_KEY = k.trim();
            GM_setValue("gemini_key", GEMINI_KEY);
            showToast("✅ API Key Saved!");
          }
        }
      }, 700);
    }, { passive: true });

    dot.addEventListener("touchmove", (e) => {
      const touch = e.touches[0];
      const dx = touch.clientX - touchStartX;
      const dy = touch.clientY - touchStartY;

      if (Math.abs(dx) > 8 || Math.abs(dy) > 8) {
        hasMoved = true;
        clearTimeout(longPressTimer);
        e.preventDefault(); // Prevent page scrolling while dragging dot

        const newLeft = Math.max(8, Math.min(window.innerWidth - 50, initialRect.left + dx));
        const newTop = Math.max(8, Math.min(window.innerHeight - 50, initialRect.top + dy));

        dot.style.bottom = "auto";
        dot.style.right = "auto";
        dot.style.left = `${newLeft}px`;
        dot.style.top = `${newTop}px`;
      }
    }, { passive: false });

    dot.addEventListener("touchend", () => {
      clearTimeout(longPressTimer);

      if (hasMoved) {
        // Save new position
        const rect = dot.getBoundingClientRect();
        GM_setValue("dot_top", Math.round(rect.top));
        GM_setValue("dot_left", Math.round(rect.left));
        return;
      }

      if (isLongPress) return;

      const duration = Date.now() - touchStartTime;
      if (duration > 650) return;

      if (tapTimer) {
        // Double tap -> Toggle Auto-Click ON/OFF
        clearTimeout(tapTimer);
        tapTimer = null;
        toggleAutoClick();
      } else {
        // Single tap -> wait 280ms to distinguish from double-tap
        tapTimer = setTimeout(() => {
          tapTimer = null;
          startSolving();
        }, 280);
      }
    });

    // --- MOUSE DRAG & CLICK (Desktop fallback) ---
    let isMouseDown = false;
    let mouseStartX = 0, mouseStartY = 0;
    let mouseMoved = false;

    dot.addEventListener("mousedown", (e) => {
      if (e.button !== 0) return;
      isMouseDown = true;
      mouseMoved = false;
      mouseStartX = e.clientX;
      mouseStartY = e.clientY;
      initialRect = dot.getBoundingClientRect();

      function onMouseMove(ev) {
        if (!isMouseDown) return;
        const dx = ev.clientX - mouseStartX;
        const dy = ev.clientY - mouseStartY;
        if (Math.abs(dx) > 6 || Math.abs(dy) > 6) {
          mouseMoved = true;
          const newLeft = Math.max(8, Math.min(window.innerWidth - 50, initialRect.left + dx));
          const newTop = Math.max(8, Math.min(window.innerHeight - 50, initialRect.top + dy));
          dot.style.bottom = "auto";
          dot.style.right = "auto";
          dot.style.left = `${newLeft}px`;
          dot.style.top = `${newTop}px`;
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

    dot.addEventListener("dblclick", () => {
      toggleAutoClick();
    });

    document.body.appendChild(dot);
  }

  // ═══════════════════════════════════════════════
  //  SPA-RESILIENT PERSISTENT MOUNT
  // ═══════════════════════════════════════════════
  // Keeps dot mounted even when Angular navigates or rebuilds DOM

  function ensureMounted() {
    if (!document.body) return;
    injectStyles();
    const existing = document.getElementById("sh-indicator-kiwi");
    if (!existing) {
      createFloatingDot();
    } else if (!document.body.contains(existing)) {
      document.body.appendChild(existing);
    }
  }

  // Run on start and observe DOM
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", ensureMounted);
  } else {
    ensureMounted();
  }

  window.addEventListener("load", ensureMounted);
  setInterval(ensureMounted, 1200);

  console.log("⚡ [Kiwi Master v4.2] Ready. Draggable floating action button active.");
})();

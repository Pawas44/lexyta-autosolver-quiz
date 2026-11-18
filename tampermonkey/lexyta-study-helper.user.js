// ==UserScript==
// @name         Lexyta Study Helper
// @namespace    https://lms.lexyta.com
// @version      2.0
// @description  AI-powered quiz answer highlighter for Lexyta LMS — Ctrl+Shift+S to solve
// @author       Pawas
// @match        https://lms.lexyta.com/*
// @grant        GM_xmlhttpRequest
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_registerMenuCommand
// @connect      generativelanguage.googleapis.com
// @run-at       document-idle
// @noframes     true
// ==/UserScript==

(function () {
  "use strict";

  // ═══════════════════════════════════════════════
  //  CONFIGURATION
  // ═══════════════════════════════════════════════

  // Gemini API Key — set via Tampermonkey menu or hardcode here
  let GEMINI_KEY = GM_getValue("gemini_key", "");

  // Highlight style: "subtle" or "bold"
  const HIGHLIGHT_STYLE = GM_getValue("highlight_style", "subtle");

  // Auto-solve when quiz page detected?
  const AUTO_SOLVE = GM_getValue("auto_solve", false);

  // Gemini models (fallback chain)
  const MODELS = [
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite",
    "gemini-3.8-flash",
    "gemini-flash-latest",
  ];

  let isSolving = false;
  let solvedAnswers = {};

  // ═══════════════════════════════════════════════
  //  TAMPERMONKEY MENU COMMANDS
  // ═══════════════════════════════════════════════

  GM_registerMenuCommand("🔑 Set Gemini API Key", () => {
    const key = prompt("Enter your Google Gemini API Key:", GEMINI_KEY);
    if (key !== null) {
      GEMINI_KEY = key.trim();
      GM_setValue("gemini_key", GEMINI_KEY);
      showToast("✅ API Key saved!");
    }
  });

  GM_registerMenuCommand("🎯 Solve Quiz Now (Ctrl+Shift+S)", () => {
    solveCurrentPage();
  });

  GM_registerMenuCommand("🖱️ Auto-Select Answers (Ctrl+Shift+A)", () => {
    if (Object.keys(solvedAnswers).length > 0) {
      autoSelectAnswers();
    } else {
      showToast("⚠️ Pehle Ctrl+Shift+S se solve karo!");
    }
  });

  GM_registerMenuCommand("🧹 Clear Highlights (Ctrl+Shift+C)", () => {
    clearHighlights();
  });

  GM_registerMenuCommand("⚙️ Toggle Highlight Style (subtle/bold)", () => {
    const current = GM_getValue("highlight_style", "subtle");
    const next = current === "subtle" ? "bold" : "subtle";
    GM_setValue("highlight_style", next);
    showToast(`Highlight style: ${next} (reload page to apply)`);
  });

  GM_registerMenuCommand("🔄 Toggle Auto-Solve", () => {
    const current = GM_getValue("auto_solve", false);
    GM_setValue("auto_solve", !current);
    showToast(`Auto-solve: ${!current ? "ON" : "OFF"}`);
  });

  // ═══════════════════════════════════════════════
  //  INJECT STEALTH CSS
  // ═══════════════════════════════════════════════

  const css = document.createElement("style");
  css.textContent = `
    /* Subtle mode — looks like a focus indicator */
    .sh-correct {
      border-left: 2.5px solid rgba(66, 133, 244, 0.45) !important;
      transition: border-left-color 0.3s ease !important;
    }
    .sh-correct:hover {
      border-left-color: rgba(66, 133, 244, 0.65) !important;
    }

    /* Bold mode — faint green tint */
    .sh-correct-bold {
      background-color: rgba(52, 168, 83, 0.07) !important;
      border-left: 2px solid rgba(52, 168, 83, 0.35) !important;
    }
    .sh-correct-bold:hover {
      background-color: rgba(52, 168, 83, 0.12) !important;
    }

    /* Tiny corner indicator */
    .sh-indicator {
      position: fixed;
      bottom: 8px;
      right: 8px;
      width: 8px;
      height: 8px;
      border-radius: 50%;
      z-index: 999999;
      pointer-events: none;
      transition: opacity 0.5s ease;
    }
    .sh-indicator.solving {
      background: rgba(251, 188, 4, 0.5);
      animation: sh-pulse 1.5s ease-in-out infinite;
    }
    .sh-indicator.done {
      background: rgba(52, 168, 83, 0.5);
    }
    @keyframes sh-pulse {
      0%, 100% { opacity: 0.4; }
      50% { opacity: 0.8; }
    }

    /* Toast */
    .sh-toast {
      position: fixed;
      bottom: 20px;
      left: 50%;
      transform: translateX(-50%) translateY(100px);
      background: rgba(32, 33, 36, 0.9);
      color: #e8eaed;
      padding: 8px 16px;
      border-radius: 8px;
      font-size: 13px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      z-index: 999999;
      pointer-events: none;
      opacity: 0;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      max-width: 420px;
      text-align: center;
    }
    .sh-toast.visible {
      transform: translateX(-50%) translateY(0);
      opacity: 1;
    }

    /* Settings panel */
    .sh-panel {
      position: fixed;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%) scale(0.95);
      background: #1e1e2e;
      color: #cdd6f4;
      border-radius: 16px;
      padding: 24px;
      z-index: 999999;
      width: 380px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.5);
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      opacity: 0;
      transition: all 0.25s ease;
      display: none;
    }
    .sh-panel.open {
      display: block;
      opacity: 1;
      transform: translate(-50%, -50%) scale(1);
    }
    .sh-panel h3 {
      margin: 0 0 16px;
      font-size: 16px;
      color: #89b4fa;
    }
    .sh-panel label {
      display: block;
      margin: 8px 0 4px;
      font-size: 12px;
      color: #a6adc8;
    }
    .sh-panel input[type="text"],
    .sh-panel input[type="password"] {
      width: 100%;
      padding: 8px 12px;
      border: 1px solid #45475a;
      border-radius: 8px;
      background: #313244;
      color: #cdd6f4;
      font-size: 13px;
      outline: none;
      box-sizing: border-box;
    }
    .sh-panel input:focus {
      border-color: #89b4fa;
    }
    .sh-panel .sh-btn {
      display: inline-block;
      padding: 8px 16px;
      border-radius: 8px;
      border: none;
      cursor: pointer;
      font-size: 13px;
      margin: 4px 4px 0 0;
    }
    .sh-btn-primary {
      background: #89b4fa;
      color: #1e1e2e;
    }
    .sh-btn-secondary {
      background: #45475a;
      color: #cdd6f4;
    }
    .sh-panel .sh-status {
      margin-top: 12px;
      padding: 8px;
      border-radius: 8px;
      font-size: 12px;
      background: #313244;
    }
    .sh-backdrop {
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0,0,0,0.5);
      z-index: 999998;
      display: none;
    }
    .sh-backdrop.open { display: block; }
  `;
  document.head.appendChild(css);

  // ═══════════════════════════════════════════════
  //  DOM QUESTION EXTRACTOR
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

    // === Strategy 1: Question containers with class names ===
    const blocks = document.querySelectorAll(
      '[class*="question" i], [class*="quiz-item" i], [class*="quizItem" i], [data-question-id]'
    );

    if (blocks.length > 0) {
      blocks.forEach((block, idx) => {
        const q = extractFromBlock(block, idx, labels);
        if (q && q.options.length >= 2) {
          // Dedupe check
          if (!questions.find((x) => x.text === q.text)) {
            questions.push(q);
          }
        }
      });
    }

    // === Strategy 2: Radio button groups ===
    if (questions.length === 0) {
      const radios = document.querySelectorAll('input[type="radio"]');
      const groups = {};
      radios.forEach((r) => {
        const name = r.name || "default";
        if (!groups[name]) groups[name] = [];
        groups[name].push(r);
      });

      Object.values(groups).forEach((inputs, idx) => {
        if (inputs.length >= 2) {
          const q = extractFromRadioGroup(inputs, idx, labels);
          if (q) questions.push(q);
        }
      });
    }

    // === Strategy 3: MUI / Card based ===
    if (questions.length === 0) {
      const cards = document.querySelectorAll(
        '.MuiCard-root, .MuiPaper-root, .ant-card, [class*="card" i]'
      );
      cards.forEach((card, idx) => {
        const inputs = card.querySelectorAll('input[type="radio"], input[type="checkbox"]');
        if (inputs.length >= 2) {
          const q = extractFromBlock(card, idx, labels);
          if (q && q.options.length >= 2) {
            questions.push(q);
          }
        }
      });
    }

    return questions;
  }

  function extractFromBlock(block, idx, labels) {
    // Question text
    let questionText = "";
    const textCandidates = block.querySelectorAll(
      'h1, h2, h3, h4, h5, h6, p, [class*="question-text" i], [class*="questionText" i], [class*="stem" i], [class*="question-body" i]'
    );
    for (const el of textCandidates) {
      const txt = stripHtml(el.innerHTML);
      if (txt.length > 10 && !el.closest('[class*="option" i], [class*="choice" i]')) {
        questionText = txt;
        break;
      }
    }
    if (!questionText) questionText = `Question ${idx + 1}`;

    // Options
    const options = [];
    const inputs = block.querySelectorAll('input[type="radio"], input[type="checkbox"]');

    if (inputs.length >= 2) {
      inputs.forEach((input, i) => {
        const optId = input.value || input.id || `opt_${idx}_${i}`;
        let optText = "";
        const labelEl =
          input.closest("label") ||
          document.querySelector(`label[for="${input.id}"]`) ||
          input.parentElement;
        if (labelEl) {
          optText = stripHtml(labelEl.innerHTML).replace(/^\s*[A-D][\.\)\:]?\s*/i, "").trim();
        }
        if (!optText) {
          const sib = input.nextElementSibling || input.nextSibling;
          if (sib) optText = (sib.textContent || "").trim();
        }
        if (optText) {
          options.push({
            id: optId,
            label: labels[i] || `${i + 1}`,
            text: optText,
            element: input,
          });
        }
      });
    }

    // Fallback: clickable option divs
    if (options.length === 0) {
      const optDivs = block.querySelectorAll('[class*="option" i], [class*="choice" i], [class*="answer-item" i]');
      optDivs.forEach((div, i) => {
        const txt = stripHtml(div.innerHTML).replace(/^\s*[A-D][\.\)\:]?\s*/i, "").trim();
        if (txt) {
          const innerInput = div.querySelector("input");
          options.push({
            id: div.getAttribute("data-option-id") || div.getAttribute("data-id") || (innerInput ? innerInput.value : `opt_${idx}_${i}`),
            label: labels[i] || `${i + 1}`,
            text: txt,
            element: innerInput || div,
          });
        }
      });
    }

    const questionId =
      block.getAttribute("data-question-id") ||
      block.getAttribute("data-id") ||
      block.id ||
      `q_${idx}`;

    return { id: questionId, text: questionText, options };
  }

  function extractFromRadioGroup(inputs, idx, labels) {
    const options = [];
    let commonParent = inputs[0].closest("fieldset, [role='radiogroup'], form, div");

    inputs.forEach((input, i) => {
      const labelEl = input.closest("label") || document.querySelector(`label[for="${input.id}"]`);
      let text = labelEl ? stripHtml(labelEl.innerHTML) : (input.nextSibling?.textContent || "").trim();
      text = text.replace(/^\s*[A-D][\.\)\:]?\s*/i, "").trim();
      options.push({
        id: input.value || `opt_${idx}_${i}`,
        label: labels[i] || `${i + 1}`,
        text,
        element: input,
      });
    });

    let questionText = "";
    if (commonParent) {
      const legend = commonParent.querySelector("legend, h3, h4, h5, p:first-child");
      if (legend) questionText = stripHtml(legend.innerHTML);
    }
    if (!questionText) questionText = `Question ${idx + 1}`;

    return { id: `q_${idx}`, text: questionText, options };
  }

  // ═══════════════════════════════════════════════
  //  GEMINI API CALLER (via GM_xmlhttpRequest — bypasses CORS)
  // ═══════════════════════════════════════════════

  function callGemini(questionsData) {
    return new Promise((resolve, reject) => {
      if (!GEMINI_KEY) {
        reject(new Error("API Key not set. Right-click Tampermonkey icon → Set Gemini API Key"));
        return;
      }

      let questionsPrompt = "";
      for (let i = 0; i < questionsData.length; i++) {
        const q = questionsData[i];
        let optsStr = "";
        for (const opt of q.options) {
          optsStr += `   [${opt.label}] Text: "${opt.text}" | ID: "${opt.id}"\n`;
        }
        questionsPrompt += `Question ${i + 1} (ID: "${q.id}"):\n${q.text}\nOptions:\n${optsStr}\n`;
      }

      const prompt = `You are a Distinguished University Professor and Top Academic Scholar.
Solve the following academic college exam questions with 100% precision.

${questionsPrompt}
Instructions:
1. First, in "reasoning", systematically evaluate the options, eliminate incorrect choices, and prove the correct academic answer.
2. In "selected_label", output ONLY the letter of the correct option: "A", "B", "C", or "D".
3. In "selected_option_id", copy the exact ID of the chosen option.
4. Return strictly valid JSON where keys are Question IDs:
{
  "<question_id>": {
    "reasoning": "<step-by-step academic proof>",
    "selected_label": "<A, B, C, or D>",
    "selected_option_id": "<exact_option_id>",
    "selected_text": "<text of correct option>"
  }
}`;

      // Try models in fallback order
      tryModel(0, prompt, questionsData, resolve, reject);
    });
  }

  function tryModel(modelIdx, prompt, questionsData, resolve, reject) {
    if (modelIdx >= MODELS.length) {
      reject(new Error("All Gemini models failed. Check your API key."));
      return;
    }

    const model = MODELS[modelIdx];
    const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${GEMINI_KEY}`;

    GM_xmlhttpRequest({
      method: "POST",
      url: url,
      headers: { "Content-Type": "application/json" },
      data: JSON.stringify({
        contents: [{ parts: [{ text: prompt }] }],
        generationConfig: {
          temperature: 0.0,
          response_mime_type: "application/json",
        },
      }),
      timeout: 30000,
      onload: function (resp) {
        if (resp.status === 200) {
          try {
            const data = JSON.parse(resp.responseText);
            const rawText = data.candidates?.[0]?.content?.parts?.[0]?.text;
            if (rawText) {
              const parsed = JSON.parse(rawText);
              const answers = {};
              for (const [qId, val] of Object.entries(parsed)) {
                if (typeof val === "object") {
                  answers[qId] = {
                    label: val.selected_label || "",
                    optionId: val.selected_option_id || "",
                    text: val.selected_text || "",
                    reasoning: val.reasoning || "",
                  };
                }
              }
              resolve(answers);
              return;
            }
          } catch (e) {
            // Parse error, try next model
          }
        }
        // Try next model
        tryModel(modelIdx + 1, prompt, questionsData, resolve, reject);
      },
      onerror: function () {
        tryModel(modelIdx + 1, prompt, questionsData, resolve, reject);
      },
      ontimeout: function () {
        tryModel(modelIdx + 1, prompt, questionsData, resolve, reject);
      },
    });
  }

  // ═══════════════════════════════════════════════
  //  ANSWER HIGHLIGHTER
  // ═══════════════════════════════════════════════

  function highlightAnswers(questions, answers) {
    let highlightCount = 0;
    for (const q of questions) {
      const answer = answers[q.id];
      if (!answer) continue;

      for (const opt of q.options) {
        const isCorrect =
          opt.id === answer.optionId ||
          opt.label.toUpperCase() === (answer.label || "").toUpperCase() ||
          (answer.text && opt.text.toLowerCase().includes(answer.text.toLowerCase())) ||
          (answer.text && answer.text.toLowerCase().includes(opt.text.toLowerCase()));

        if (isCorrect && opt.element) {
          const target =
            opt.element.closest("label, [class*='option' i], [class*='choice' i], div") ||
            opt.element.parentElement ||
            opt.element;

          const className = HIGHLIGHT_STYLE === "bold" ? "sh-correct-bold" : "sh-correct";
          target.classList.add(className);

          if (answer.reasoning) {
            target.setAttribute("title", answer.reasoning.substring(0, 200));
          }
          highlightCount++;
        }
      }
    }
    return highlightCount;
  }

  function clearHighlights() {
    document.querySelectorAll(".sh-correct, .sh-correct-bold").forEach((el) => {
      el.classList.remove("sh-correct", "sh-correct-bold");
      el.removeAttribute("title");
    });
    const indicator = document.getElementById("sh-indicator");
    if (indicator) indicator.remove();
    showToast("🧹 Highlights cleared");
  }

  // ═══════════════════════════════════════════════
  //  AUTO-SELECT (CLICK CORRECT ANSWERS)
  // ═══════════════════════════════════════════════

  async function autoSelectAnswers() {
    const questions = extractQuestions();
    if (Object.keys(solvedAnswers).length === 0) {
      showToast("⚠️ Pehle solve karo (Ctrl+Shift+S)");
      return;
    }

    showToast("🖱️ Auto-selecting answers...");

    for (const q of questions) {
      const answer = solvedAnswers[q.id];
      if (!answer) continue;

      for (const opt of q.options) {
        const isCorrect =
          opt.id === answer.optionId ||
          opt.label.toUpperCase() === (answer.label || "").toUpperCase() ||
          (answer.text && opt.text.toLowerCase().includes(answer.text.toLowerCase()));

        if (isCorrect && opt.element) {
          // Human-like delay
          await sleep(600 + Math.random() * 2000);

          if (opt.element.tagName === "INPUT") {
            opt.element.click();
          } else {
            const input = opt.element.querySelector("input");
            if (input) input.click();
            else opt.element.click();
          }

          // Trigger framework events
          ["change", "input", "click"].forEach((evt) => {
            opt.element.dispatchEvent(new Event(evt, { bubbles: true }));
          });
        }
      }
      await sleep(800 + Math.random() * 2500);
    }
    showToast("✅ Answers selected!");
  }

  function sleep(ms) {
    return new Promise((r) => setTimeout(r, ms));
  }

  // ═══════════════════════════════════════════════
  //  MAIN SOLVE FLOW
  // ═══════════════════════════════════════════════

  async function solveCurrentPage() {
    if (isSolving) return;
    if (!GEMINI_KEY) {
      showSettingsPanel();
      return;
    }

    isSolving = true;
    clearExistingHighlights();
    showIndicator("solving");

    try {
      const questions = extractQuestions();

      if (questions.length === 0) {
        showToast("❌ No quiz questions found on this page");
        hideIndicator();
        isSolving = false;
        return;
      }

      showToast(`🔍 Found ${questions.length} questions. Sending to AI...`);

      // Prepare clean data for API
      const cleanQ = questions.map((q) => ({
        id: q.id,
        text: q.text,
        options: q.options.map((o) => ({ id: o.id, label: o.label, text: o.text })),
      }));

      const answers = await callGemini(cleanQ);
      solvedAnswers = answers;

      const count = highlightAnswers(questions, answers);
      showIndicator("done");
      showToast(`✅ ${count}/${questions.length} answers highlighted! Hover for reasoning.`);
    } catch (err) {
      showToast("❌ " + err.message);
      hideIndicator();
    }

    isSolving = false;
  }

  function clearExistingHighlights() {
    document.querySelectorAll(".sh-correct, .sh-correct-bold").forEach((el) => {
      el.classList.remove("sh-correct", "sh-correct-bold");
      el.removeAttribute("title");
    });
  }

  // ═══════════════════════════════════════════════
  //  UI HELPERS
  // ═══════════════════════════════════════════════

  function showToast(text) {
    let toast = document.getElementById("sh-toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "sh-toast";
      toast.className = "sh-toast";
      document.body.appendChild(toast);
    }
    toast.textContent = text;
    toast.classList.add("visible");
    setTimeout(() => {
      toast.classList.remove("visible");
    }, 3500);
  }

  function showIndicator(state) {
    let el = document.getElementById("sh-indicator");
    if (!el) {
      el = document.createElement("div");
      el.id = "sh-indicator";
      el.className = "sh-indicator";
      document.body.appendChild(el);
    }
    el.className = "sh-indicator " + state;
    if (state === "done") {
      setTimeout(() => {
        el.style.opacity = "0";
        setTimeout(() => el.remove(), 500);
      }, 4000);
    }
  }

  function hideIndicator() {
    const el = document.getElementById("sh-indicator");
    if (el) el.remove();
  }

  // ═══════════════════════════════════════════════
  //  SETTINGS PANEL (in-page popup)
  // ═══════════════════════════════════════════════

  function showSettingsPanel() {
    // Remove existing
    document.getElementById("sh-panel-backdrop")?.remove();
    document.getElementById("sh-panel")?.remove();

    const backdrop = document.createElement("div");
    backdrop.id = "sh-panel-backdrop";
    backdrop.className = "sh-backdrop open";

    const panel = document.createElement("div");
    panel.id = "sh-panel";
    panel.className = "sh-panel";
    panel.innerHTML = `
      <h3>🎓 Lexyta Study Helper — Setup</h3>
      <label>Google Gemini API Key:</label>
      <input type="password" id="sh-key-input" placeholder="AIza... ya AQ.Ab..." value="${GEMINI_KEY}" />
      <p style="font-size:11px;color:#6c7086;margin:4px 0 12px;">
        Free API key banao: <a href="https://aistudio.google.com/apikey" target="_blank" style="color:#89b4fa;">aistudio.google.com/apikey</a>
      </p>
      <div>
        <button class="sh-btn sh-btn-primary" id="sh-save-btn">💾 Save & Solve</button>
        <button class="sh-btn sh-btn-secondary" id="sh-close-btn">Close</button>
      </div>
      <div class="sh-status">
        <b>Keyboard Shortcuts:</b><br>
        <code>Ctrl+Shift+S</code> → Solve quiz<br>
        <code>Ctrl+Shift+A</code> → Auto-click answers<br>
        <code>Ctrl+Shift+C</code> → Clear highlights<br>
        <code>Ctrl+Shift+X</code> → Open this panel
      </div>
    `;

    document.body.appendChild(backdrop);
    document.body.appendChild(panel);

    // Animate open
    requestAnimationFrame(() => panel.classList.add("open"));

    // Events
    backdrop.addEventListener("click", closeSettingsPanel);
    document.getElementById("sh-close-btn").addEventListener("click", closeSettingsPanel);
    document.getElementById("sh-save-btn").addEventListener("click", () => {
      const key = document.getElementById("sh-key-input").value.trim();
      if (key) {
        GEMINI_KEY = key;
        GM_setValue("gemini_key", GEMINI_KEY);
        closeSettingsPanel();
        showToast("✅ API Key saved! Solving...");
        setTimeout(() => solveCurrentPage(), 500);
      } else {
        showToast("⚠️ API Key khali hai!");
      }
    });
  }

  function closeSettingsPanel() {
    const panel = document.getElementById("sh-panel");
    const backdrop = document.getElementById("sh-panel-backdrop");
    if (panel) {
      panel.classList.remove("open");
      setTimeout(() => panel.remove(), 250);
    }
    if (backdrop) {
      backdrop.classList.remove("open");
      setTimeout(() => backdrop.remove(), 250);
    }
  }

  // ═══════════════════════════════════════════════
  //  KEYBOARD SHORTCUTS
  // ═══════════════════════════════════════════════

  document.addEventListener("keydown", (e) => {
    // Ctrl+Shift+S → Solve
    if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === "s") {
      e.preventDefault();
      e.stopPropagation();
      solveCurrentPage();
    }
    // Ctrl+Shift+C → Clear
    if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === "c") {
      e.preventDefault();
      clearHighlights();
    }
    // Ctrl+Shift+A → Auto-select
    if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === "a") {
      e.preventDefault();
      autoSelectAnswers();
    }
    // Ctrl+Shift+X → Settings
    if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === "x") {
      e.preventDefault();
      showSettingsPanel();
    }
  }, true);

  // ═══════════════════════════════════════════════
  //  AUTO-SOLVE ON QUIZ PAGE DETECTION
  // ═══════════════════════════════════════════════

  function isQuizPage() {
    const url = window.location.href.toLowerCase();
    return url.includes("quiz") || url.includes("assignment") || url.includes("attempt");
  }

  // SPA navigation watcher
  let lastUrl = window.location.href;
  const urlObserver = new MutationObserver(() => {
    if (window.location.href !== lastUrl) {
      lastUrl = window.location.href;
      solvedAnswers = {};
      clearExistingHighlights();
      if (AUTO_SOLVE && isQuizPage() && GEMINI_KEY) {
        setTimeout(() => solveCurrentPage(), 2500);
      }
    }
  });
  urlObserver.observe(document.body, { childList: true, subtree: true });

  // Initial auto-solve
  if (AUTO_SOLVE && isQuizPage() && GEMINI_KEY) {
    setTimeout(() => solveCurrentPage(), 3000);
  }

  console.log("📚 Study Helper loaded. Ctrl+Shift+S to solve, Ctrl+Shift+X for settings.");
})();

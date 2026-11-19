/**
 * Content Script — Lexyta Study Helper Chrome Extension
 * Author: Pawas
 * Handles DOM question extraction, stealth progressive highlighting, and auto-pilot selection.
 */

(function () {
  "use strict";

  let config = {
    geminiKey: "",
    enabled: true,
    autoSolve: false,
    highlightStyle: "subtle"
  };

  let isSolving = false;
  let solvedAnswers = {};

  // Fetch initial config from background
  function syncConfig() {
    chrome.runtime.sendMessage({ type: "GET_CONFIG" }, (resp) => {
      if (resp) {
        config = Object.assign(config, resp);
        if (config.autoSolve && isQuizPage()) {
          setTimeout(solveCurrentPage, 2500);
        }
      }
    });
  }
  syncConfig();

  // Listen for popup triggers & config updates
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.type === "CONFIG_UPDATED") {
      syncConfig();
      sendResponse({ success: true });
      return;
    }

    if (msg.type === "TRIGGER_SOLVE") {
      solveCurrentPage();
      sendResponse({ status: "solving" });
      return;
    }

    if (msg.type === "TRIGGER_AUTOSELECT") {
      if (Object.keys(solvedAnswers).length > 0) {
        autoSelectAnswers();
        sendResponse({ status: "selecting" });
      } else {
        sendResponse({ status: "no_answers" });
      }
      return;
    }

    if (msg.type === "TRIGGER_CLEAR") {
      clearHighlights();
      sendResponse({ status: "cleared" });
      return;
    }
  });

  function isQuizPage() {
    const url = window.location.href.toLowerCase();
    return url.includes("quiz") || url.includes("assignment") || url.includes("attempt") || url.includes("exam");
  }

  function showToast(text) {
    let t = document.getElementById("sh-toast-ext");
    if (!t) {
      t = document.createElement("div");
      t.id = "sh-toast-ext";
      t.className = "sh-toast-ext";
      (document.body || document.documentElement).appendChild(t);
    }
    t.textContent = text;
    t.classList.add("visible");
    setTimeout(() => t.classList.remove("visible"), 3200);
  }

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

  function clearHighlights() {
    document.querySelectorAll(".sh-correct, .sh-correct-bold").forEach(el => {
      el.classList.remove("sh-correct", "sh-correct-bold");
    });
  }

  async function solveCurrentPage() {
    if (isSolving) return;

    if (!config.geminiKey) {
      showToast("⚠️ Extension popup me Gemini API Key set karein!");
      return;
    }

    const dot = document.getElementById("sh-ext-dot");
    if (dot) { dot.className = "sh-ext-dot solving"; dot.innerHTML = "⏳"; }

    isSolving = true;
    showToast("🔍 Scanning questions...");

    const questions = extractQuestions();
    if (questions.length === 0) {
      showToast("❌ No quiz questions found on this page.");
      isSolving = false;
      if (dot) { dot.className = "sh-ext-dot"; dot.innerHTML = "🎯"; }
      return;
    }

    showToast(`🧠 Solving ${questions.length} questions via Gemini...`);

    chrome.runtime.sendMessage({
      type: "SOLVE_QUESTIONS",
      questions,
      geminiKey: config.geminiKey
    }, (resp) => {
      isSolving = false;

      if (!resp || !resp.success) {
        showToast(`❌ Error: ${resp?.error || "Gemini API failed"}`);
        if (dot) { dot.className = "sh-ext-dot"; dot.innerHTML = "🎯"; }
        return;
      }

      solvedAnswers = resp.answers || {};
      const highlighted = highlightAnswers(questions, solvedAnswers);

      if (dot) { dot.className = "sh-ext-dot done"; dot.innerHTML = "✅"; }
      showToast(`🎉 Done! ${highlighted}/${questions.length} answers highlighted.`);

      setTimeout(() => {
        if (dot) { dot.className = "sh-ext-dot"; dot.innerHTML = "🎯"; }
      }, 3000);
    });
  }

  function highlightAnswers(questions, answers) {
    let count = 0;
    const className = config.highlightStyle === "bold" ? "sh-correct-bold" : "sh-correct";

    for (const q of questions) {
      const ans = answers[q.id];
      if (!ans) continue;

      for (const opt of q.options) {
        const isCorrect = (
          opt.id === ans.selected_option_id ||
          opt.label.toUpperCase() === (ans.selected_label || "").toUpperCase() ||
          (ans.selected_text && opt.text.toLowerCase().includes(ans.selected_text.toLowerCase()))
        );

        if (isCorrect && opt.element) {
          const parent = opt.element.closest("label, [class*='option' i], div") || opt.element.parentElement;
          if (parent) {
            parent.classList.add(className);
            if (ans.reasoning) parent.title = ans.reasoning;
          }
          count++;
          break;
        }
      }
    }
    return count;
  }

  async function autoSelectAnswers() {
    if (Object.keys(solvedAnswers).length === 0) {
      showToast("⚠️ Pehle Solve karein!");
      return;
    }

    const questions = extractQuestions();
    let clicked = 0;

    for (const q of questions) {
      const ans = solvedAnswers[q.id];
      if (!ans) continue;

      for (const opt of q.options) {
        const isCorrect = (
          opt.id === ans.selected_option_id ||
          opt.label.toUpperCase() === (ans.selected_label || "").toUpperCase() ||
          (ans.selected_text && opt.text.toLowerCase().includes(ans.selected_text.toLowerCase()))
        );

        if (isCorrect && opt.element) {
          try { opt.element.scrollIntoView({ behavior: "smooth", block: "center" }); } catch (e) {}
          await new Promise(r => setTimeout(r, 600 + Math.random() * 800));

          opt.element.click();
          ["change", "input", "click"].forEach(evt => {
            opt.element.dispatchEvent(new Event(evt, { bubbles: true }));
          });
          clicked++;
          break;
        }
      }
    }

    showToast(`✅ Selected ${clicked} answers on screen.`);
  }

  // Keyboard shortcuts
  document.addEventListener("keydown", (e) => {
    // Ctrl+Shift+S -> Solve
    if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === "s") {
      e.preventDefault();
      solveCurrentPage();
    }
    // Ctrl+Shift+A -> Auto-select
    if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === "a") {
      e.preventDefault();
      autoSelectAnswers();
    }
    // Ctrl+Shift+C -> Clear
    if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === "c") {
      e.preventDefault();
      clearHighlights();
    }
  });

  // Floating Corner Button
  function createFloatingDot() {
    if (document.getElementById("sh-ext-dot") || !document.body) return;

    const dot = document.createElement("div");
    dot.id = "sh-ext-dot";
    dot.className = "sh-ext-dot";
    dot.innerHTML = "🎯";
    dot.title = "Tap to solve (Ctrl+Shift+S)";

    dot.addEventListener("click", () => {
      solveCurrentPage();
    });

    document.body.appendChild(dot);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", createFloatingDot);
  } else {
    createFloatingDot();
  }
  setInterval(createFloatingDot, 1500);

  console.log("📚 [Study Helper Extension] Active on Lexyta LMS.");
})();

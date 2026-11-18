/**
 * Popup Script — Chrome Extension Settings & Controls
 */

document.addEventListener("DOMContentLoaded", () => {
  const apiKeyEl = document.getElementById("apiKey");
  const enabledEl = document.getElementById("enabled");
  const autoSolveEl = document.getElementById("autoSolve");
  const boldStyleEl = document.getElementById("boldStyle");
  const solveBtn = document.getElementById("solveBtn");
  const autoSelectBtn = document.getElementById("autoSelectBtn");
  const clearBtn = document.getElementById("clearBtn");
  const statusEl = document.getElementById("status");

  // Load saved config
  chrome.runtime.sendMessage({ type: "GET_CONFIG" }, (config) => {
    if (config) {
      apiKeyEl.value = config.geminiKey || "";
      enabledEl.checked = config.enabled !== false;
      autoSolveEl.checked = !!config.autoSolve;
      boldStyleEl.checked = config.highlightStyle === "bold";
    }
  });

  function showStatus(text, type) {
    statusEl.textContent = text;
    statusEl.className = `status show ${type}`;
    setTimeout(() => { statusEl.className = "status"; }, 3000);
  }

  // Save config on any change
  function saveConfig() {
    const config = {
      geminiKey: apiKeyEl.value.trim(),
      enabled: enabledEl.checked,
      autoSolve: autoSolveEl.checked,
      highlightStyle: boldStyleEl.checked ? "bold" : "subtle",
    };
    chrome.runtime.sendMessage({ type: "SAVE_CONFIG", config }, () => {
      // Notify content script
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (tabs[0]) {
          chrome.tabs.sendMessage(tabs[0].id, { type: "CONFIG_UPDATED" });
        }
      });
    });
  }

  apiKeyEl.addEventListener("change", saveConfig);
  enabledEl.addEventListener("change", saveConfig);
  autoSolveEl.addEventListener("change", saveConfig);
  boldStyleEl.addEventListener("change", saveConfig);

  // Solve button
  solveBtn.addEventListener("click", () => {
    saveConfig();
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]) {
        chrome.tabs.sendMessage(tabs[0].id, { type: "TRIGGER_SOLVE" }, (resp) => {
          if (resp) {
            showStatus("🎯 Solving quiz...", "ok");
          } else {
            showStatus("⚠️ Not on Lexyta page", "err");
          }
        });
      }
    });
  });

  // Auto-select button
  autoSelectBtn.addEventListener("click", () => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]) {
        chrome.tabs.sendMessage(tabs[0].id, { type: "TRIGGER_AUTOSELECT" }, (resp) => {
          if (resp?.status === "selecting") {
            showStatus("🖱️ Auto-selecting answers...", "ok");
          } else if (resp?.status === "no_answers") {
            showStatus("⚠️ Solve first, then auto-select", "err");
          }
        });
      }
    });
  });

  // Clear button
  clearBtn.addEventListener("click", () => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]) {
        chrome.tabs.sendMessage(tabs[0].id, { type: "TRIGGER_CLEAR" }, () => {
          showStatus("🧹 Highlights cleared", "ok");
        });
      }
    });
  });
});

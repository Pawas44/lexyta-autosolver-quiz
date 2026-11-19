/**
 * Background Service Worker — Lexyta Study Helper
 * Handles Gemini API calls from content script (bypasses CORS)
 * and manages extension state.
 * Supports up to 100+ questions via Smart Batching.
 */

const DEFAULT_CONFIG = {
  geminiKey: "",
  enabled: true,
  autoSolve: false,
  highlightStyle: "subtle",
  hotkey: "ctrl+shift+s"
};

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "SOLVE_QUESTIONS") {
    solveWithGemini(msg.questions, msg.geminiKey)
      .then(answers => sendResponse({ success: true, answers }))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true;
  }

  if (msg.type === "GET_CONFIG") {
    chrome.storage.local.get(DEFAULT_CONFIG, (config) => {
      sendResponse(config);
    });
    return true;
  }

  if (msg.type === "SAVE_CONFIG") {
    chrome.storage.local.set(msg.config, () => {
      sendResponse({ success: true });
    });
    return true;
  }
});

async function solveWithGemini(questions, apiKey) {
  if (!apiKey) {
    throw new Error("Gemini API Key not configured. Open extension popup to set it.");
  }

  // If questions > 10, solve in chunks of 8
  const CHUNK_SIZE = 8;
  const allAnswers = {};

  for (let i = 0; i < questions.length; i += CHUNK_SIZE) {
    const chunk = questions.slice(i, i + CHUNK_SIZE);
    const chunkAnswers = await solveBatch(chunk, apiKey);
    Object.assign(allAnswers, chunkAnswers);
    if (i + CHUNK_SIZE < questions.length) {
      await new Promise(r => setTimeout(r, 300));
    }
  }

  return allAnswers;
}

async function solveBatch(chunk, apiKey) {
  const MODELS = [
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite",
    "gemini-3.8-flash",
    "gemini-flash-latest"
  ];

  let questionsPrompt = "";
  for (let i = 0; i < chunk.length; i++) {
    const q = chunk[i];
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

  for (const model of MODELS) {
    try {
      const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`;
      const resp = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          contents: [{ parts: [{ text: prompt }] }],
          generationConfig: {
            temperature: 0.0,
            response_mime_type: "application/json"
          }
        })
      });

      if (resp.ok) {
        const data = await resp.json();
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
                reasoning: val.reasoning || ""
              };
            }
          }
          return answers;
        }
      }
    } catch (e) {
      console.warn(`[StudyHelper] Model ${model} failed:`, e.message);
    }
  }

  throw new Error("Gemini AI models failed. Please verify your API key.");
}

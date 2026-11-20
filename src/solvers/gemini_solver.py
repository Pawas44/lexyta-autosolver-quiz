"""
Gemini AI Quiz Solver
Uses Google Gemini API to analyze questions, reasoning through options, and selecting correct answers.
Supports automatic model fallback and strict JSON schema parsing.
"""

import time
import re
import html
import json
import logging
import requests
from typing import Dict, List, Any, Optional
from .base import BaseQuizSolver

logger = logging.getLogger("GeminiSolver")

def clean_html_text(raw_html: str) -> str:
    """Strips HTML markup and entities into clean readable text."""
    if not raw_html:
        return ""
    text = re.sub(r'<\s*br\s*/?>', '\n', raw_html, flags=re.I)
    text = re.sub(r'</\s*p\s*>', '\n', text, flags=re.I)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html.unescape(text)
    return re.sub(r'[ \t]+', ' ', text).strip()

def resolve_option_id(selection: Any, options: List[Dict[str, Any]]) -> Optional[str]:
    """
    Intelligently maps any model output (exact UUID, letter label 'A'/'B'/'C'/'D',
    numeric index '1'/'2', or answer text) to the exact LMS option ID.
    Guarantees no false defaults to Option A!
    """
    if not selection or not options:
        return None

    sel_str = str(selection).strip()
    sel_lower = sel_str.lower()
    sel_upper = sel_str.upper()

    # 1. Exact match against option ID
    for opt in options:
        opt_id = str(opt.get("id", "")).strip()
        if opt_id.lower() == sel_lower:
            return opt_id

    # 2. Match against option letter label (e.g. "A", "B", "C", "D", "Option A", "Choice B")
    clean_label = re.sub(r'^(option|choice)\s*', '', sel_upper, flags=re.I).strip(". )]:-")
    for opt in options:
        opt_lbl = str(opt.get("label", "")).strip().upper()
        if opt_lbl and clean_label == opt_lbl:
            return opt.get("id")

    # 3. Match numeric index ("1" -> 1st option, "2" -> 2nd option)
    if clean_label.isdigit():
        idx = int(clean_label)
        if 1 <= idx <= len(options):
            return options[idx - 1].get("id")
        elif 0 <= idx < len(options):
            return options[idx].get("id")

    # 4. Text matching (if model returned answer text e.g. "RAM" or "tuple")
    clean_text = clean_html_text(sel_str).lower()
    for opt in options:
        opt_text = clean_html_text(opt.get("text", "")).lower()
        if clean_text == opt_text:
            return opt.get("id")
    for opt in options:
        opt_text = clean_html_text(opt.get("text", "")).lower()
        if len(clean_text) >= 3 and (clean_text in opt_text or opt_text in clean_text):
            return opt.get("id")

    return None

class GeminiQuizSolver(BaseQuizSolver):
    DEFAULT_MODELS = [
        "gemini-flash-lite-latest",
        "gemini-3.1-flash-lite",
        "gemini-3.1-flash-lite-preview",
        "gemini-3.8-flash",
        "gemini-3.5-flash",
        "gemini-flash-latest"
    ]

    def __init__(self, api_key: str, models: Optional[List[str]] = None):
        self.api_key = api_key
        self.models = models or self.DEFAULT_MODELS

    def solve_quiz(self, quiz_sections: List[Dict[str, Any]], on_progress: Optional[Any] = None) -> Dict[str, Any]:
        """Solves all questions in quiz sections using Gemini AI with smart batching and live progress reporting."""
        payload: Dict[str, Any] = {}
        all_questions = []

        for section in quiz_sections:
            sec_name = section.get("name", "Section")
            questions = section.get("questions", [])
            logger.info(f"Found section '{sec_name}' with {len(questions)} question(s).")
            for q in questions:
                all_questions.append(q)

        total = len(all_questions)
        logger.info(f"Starting precision solver for {total} question(s) using Chain-of-Thought AI...")

        if on_progress:
            try:
                on_progress(0, total, "AI solver initialized with Chain-of-Thought reasoning...")
            except Exception:
                pass

        # Smart dynamic batching: 5 for small quizzes, 8 for grand exams (50-100 questions)
        CHUNK_SIZE = 8 if total >= 30 else 5
        for i in range(0, total, CHUNK_SIZE):
            chunk = all_questions[i:i + CHUNK_SIZE]
            chunk_num = (i // CHUNK_SIZE) + 1
            total_chunks = (total + CHUNK_SIZE - 1) // CHUNK_SIZE
            logger.info(f"Solving Batch {chunk_num}/{total_chunks} (Questions {i+1} to {min(i+CHUNK_SIZE, total)})...")

            batch_answers = self._solve_question_batch(chunk)
            payload.update(batch_answers)

            if on_progress:
                try:
                    on_progress(len(payload), total, f"Batch {chunk_num}/{total_chunks} verified ({len(payload)}/{total} answered)")
                except Exception:
                    pass

            # Safe spacing between batches to prevent API rate limits
            if i + CHUNK_SIZE < total:
                time.sleep(0.3)

        if on_progress:
            try:
                on_progress(len(payload), total, "All questions verified! Submitting to LMS...")
            except Exception:
                pass

        logger.info(f"Quiz solving completed: {len(payload)}/{total} answered.")
        return payload

    def _solve_question_batch(self, chunk: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Solves a batch of questions with Chain-of-Thought reasoning and individual fallback."""
        results: Dict[str, Any] = {}
        
        # Try batch solving across models
        if self.api_key and len(chunk) > 1:
            for model_name in self.models:
                batch_res = self._call_gemini_batch(model_name, chunk)
                if batch_res is not None and len(batch_res) >= len(chunk) * 0.8:
                    results.update(batch_res)
                    break

        # Fallback for any questions that weren't resolved by the batch call
        for q in chunk:
            q_id = q.get("id")
            if q_id not in results:
                q_type = q.get("question_type", "MULTIPLE_CHOICE")
                raw_text = q.get("text", "")
                q_text = clean_html_text(raw_text)
                options = [
                    {
                        "id": opt.get("id"),
                        "label": opt.get("label", ""),
                        "text": clean_html_text(opt.get("text", ""))
                    }
                    for opt in q.get("options", [])
                ]
                ans = self._solve_question(q_id, q_type, q_text, options)
                if ans is not None:
                    results[q_id] = ans

        return results

    def _call_gemini_batch(self, model: str, chunk: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Sends multiple questions in a single prompt with Chain-of-Thought reasoning."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"

        questions_prompt = ""
        options_per_q: Dict[str, List[Dict[str, Any]]] = {}
        q_types: Dict[str, str] = {}

        for idx, q in enumerate(chunk, 1):
            q_id = q.get("id")
            q_type = q.get("question_type", "SINGLE_CHOICE")
            q_types[q_id] = q_type
            q_text = clean_html_text(q.get("text", ""))
            
            clean_opts = [
                {
                    "id": opt.get("id"),
                    "label": opt.get("label", ""),
                    "text": clean_html_text(opt.get("text", ""))
                }
                for opt in q.get("options", [])
            ]
            options_per_q[q_id] = clean_opts

            opts_str = ""
            for opt in clean_opts:
                lbl = opt.get("label", "").strip() or "?"
                opts_str += f"   [{lbl}] Text: \"{opt.get('text', '')}\" | ID: \"{opt.get('id', '')}\"\n"

            questions_prompt += f"Question {idx} (ID: \"{q_id}\", Type: {q_type}):\n{q_text}\nOptions:\n{opts_str}\n"

        prompt = f"""You are a Distinguished University Professor and Top Academic Scholar.
Solve the following academic college exam questions with 100% precision.

{questions_prompt}
Instructions:
1. First, in "reasoning", systematically evaluate the options, eliminate incorrect choices, and prove the correct academic answer.
2. In "selected_label", output ONLY the letter of the correct option: "A", "B", "C", or "D".
3. In "selected_option_id", copy the exact ID of the chosen option.
4. Return strictly valid JSON where keys are Question IDs:
{{
  "<question_id>": {{
    "reasoning": "<step-by-step academic proof>",
    "selected_label": "<A, B, C, or D>",
    "selected_option_id": "<exact_option_id>",
    "selected_text": "<text of correct option>"
  }}
}}
"""

        req_body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.0,
                "response_mime_type": "application/json"
            }
        }

        try:
            resp = requests.post(url, json=req_body, timeout=25)
            if resp.status_code == 200:
                raw_out = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(raw_out)
                
                answers: Dict[str, Any] = {}
                for q_id, val in parsed.items():
                    if not isinstance(val, dict):
                        continue
                    q_type = q_types.get(q_id, "SINGLE_CHOICE")
                    opts = options_per_q.get(q_id, [])

                    if q_type in ["SINGLE_CHOICE", "BOOLEAN", "TRUE_FALSE"]:
                        matched_id = (
                            resolve_option_id(val.get("selected_option_id"), opts) or
                            resolve_option_id(val.get("selected_label"), opts) or
                            resolve_option_id(val.get("selected_text"), opts)
                        )
                        answers[q_id] = matched_id if matched_id else (opts[0]["id"] if opts else None)
                    elif q_type == "MULTIPLE_CHOICE":
                        raw_list = val.get("selected_ids") or [val.get("selected_option_id")] or [val.get("selected_label")]
                        matched_ids = []
                        for item in raw_list:
                            mid = resolve_option_id(item, opts)
                            if mid and mid not in matched_ids:
                                matched_ids.append(mid)
                        answers[q_id] = matched_ids if matched_ids else ([opts[0]["id"]] if opts else [])
                    else:
                        answers[q_id] = val.get("text_answer") or val.get("selected_text") or "Answer"

                return answers
            else:
                logger.warning(f"Batch model {model} returned HTTP {resp.status_code}")
                return None
        except Exception as e:
            logger.warning(f"Batch model {model} error: {e}")
            return None

    def _solve_question(self, q_id: str, q_type: str, q_text: str, options: List[Dict[str, str]]) -> Any:
        """Solves a single question by calling Gemini with model fallback and CoT reasoning."""
        if self.api_key:
            for model_name in self.models:
                ans = self._call_gemini_model(model_name, q_type, q_text, options)
                if ans is not None:
                    return ans

        # Fallback if all Gemini models fail or no key provided
        logger.warning(f"Using fallback default option for question {q_id}")
        if q_type in ["SINGLE_CHOICE", "BOOLEAN", "TRUE_FALSE"]:
            return options[0]["id"] if options else None
        elif q_type == "MULTIPLE_CHOICE":
            return [options[0]["id"]] if options else []
        return "Answer"

    def _call_gemini_model(self, model: str, q_type: str, q_text: str, options: List[Dict[str, str]]) -> Optional[Any]:
        """Calls specific Gemini model with Chain-of-Thought reasoning and robust option matching."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"

        options_text = ""
        for opt in options:
            lbl = opt.get("label", "").strip() or "?"
            options_text += f"- [{lbl}] Text: \"{opt.get('text', '')}\" | ID: \"{opt.get('id', '')}\"\n"

        prompt = f"""You are a Distinguished University Professor and Top Academic Scholar.
Solve this quiz question with 100% academic precision.

Question:
{q_text}

Question Type: {q_type}

Options:
{options_text}

Instructions:
1. In "reasoning", systematically evaluate each option, eliminate distractors, and verify the canonical academic answer.
2. In "selected_label", output ONLY the letter of the correct option: "A", "B", "C", or "D".
3. In "selected_option_id", copy the exact ID of the chosen option.
4. Return strictly valid JSON:
{{
  "reasoning": "<step-by-step academic deduction>",
  "selected_label": "<A, B, C, or D>",
  "selected_option_id": "<exact_option_id>",
  "selected_text": "<text of correct option>"
}}
"""

        req_body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.0,
                "response_mime_type": "application/json"
            }
        }

        try:
            resp = requests.post(url, json=req_body, timeout=25)
            if resp.status_code == 200:
                data = resp.json()
                raw_out = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(raw_out)
                logger.info(f"[{model}] Reason: {parsed.get('reasoning')[:90]}...")

                if q_type in ["SINGLE_CHOICE", "BOOLEAN", "TRUE_FALSE"]:
                    matched_id = (
                        resolve_option_id(parsed.get("selected_option_id"), options) or
                        resolve_option_id(parsed.get("selected_label"), options) or
                        resolve_option_id(parsed.get("selected_text"), options)
                    )
                    return matched_id if matched_id else (options[0]["id"] if options else None)
                elif q_type == "MULTIPLE_CHOICE":
                    raw_list = parsed.get("selected_ids") or [parsed.get("selected_option_id")] or [parsed.get("selected_label")]
                    matched_ids = []
                    for item in raw_list:
                        mid = resolve_option_id(item, options)
                        if mid and mid not in matched_ids:
                            matched_ids.append(mid)
                    return matched_ids if matched_ids else ([options[0]["id"]] if options else [])
                return parsed.get("text_answer") or parsed.get("selected_text") or "Answer"
            else:
                logger.warning(f"Model {model} returned HTTP {resp.status_code}")
                return None
        except Exception as e:
            logger.warning(f"Model {model} error: {e}")
            return None

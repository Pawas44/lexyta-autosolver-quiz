"""
Gemini AI Quiz Solver
Uses Google Gemini API to analyze questions, reasoning through options, and selecting correct answers.
Supports automatic model fallback and strict JSON schema parsing.
"""

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

class GeminiQuizSolver(BaseQuizSolver):
    DEFAULT_MODELS = [
        "gemini-3.1-flash-lite",
        "gemini-3.8-flash",
        "gemini-flash-latest",
        "gemini-2.5-flash-lite"
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
        logger.info(f"Starting solver for {total} question(s) using high-speed chunked batching...")

        if on_progress:
            try:
                on_progress(0, total, "AI solver initialized...")
            except Exception:
                pass

        # Process in chunks of 10 questions to solve rapidly and avoid 15 RPM rate limits
        CHUNK_SIZE = 10
        for i in range(0, total, CHUNK_SIZE):
            chunk = all_questions[i:i + CHUNK_SIZE]
            chunk_num = (i // CHUNK_SIZE) + 1
            total_chunks = (total + CHUNK_SIZE - 1) // CHUNK_SIZE
            logger.info(f"Solving Batch {chunk_num}/{total_chunks} (Questions {i+1} to {min(i+CHUNK_SIZE, total)})...")

            batch_answers = self._solve_question_batch(chunk)
            payload.update(batch_answers)

            if on_progress:
                try:
                    on_progress(len(payload), total, f"Batch {chunk_num}/{total_chunks} solved ({len(payload)}/{total} answered)")
                except Exception:
                    pass

        if on_progress:
            try:
                on_progress(len(payload), total, "All questions answered! Preparing submission...")
            except Exception:
                pass

        logger.info(f"Quiz solving completed: {len(payload)}/{total} answered.")
        return payload

    def _solve_question_batch(self, chunk: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Solves a batch of questions in a single Gemini API call with individual fallback."""
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
        """Sends multiple questions in a single prompt for ultra-fast solving."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"

        questions_prompt = ""
        valid_options_per_q: Dict[str, List[str]] = {}
        q_types: Dict[str, str] = {}

        for idx, q in enumerate(chunk, 1):
            q_id = q.get("id")
            q_type = q.get("question_type", "SINGLE_CHOICE")
            q_types[q_id] = q_type
            q_text = clean_html_text(q.get("text", ""))
            
            opts_str = ""
            valid_opts = []
            for opt in q.get("options", []):
                opt_id = opt.get("id")
                valid_opts.append(opt_id)
                opts_str += f"   - ID: \"{opt_id}\" | {opt.get('label', '')}: {clean_html_text(opt.get('text', ''))}\n"
            valid_options_per_q[q_id] = valid_opts

            questions_prompt += f"Question {idx} (ID: \"{q_id}\", Type: {q_type}):\n{q_text}\nOptions:\n{opts_str}\n"

        prompt = f"""You are an expert college professor and academic exam solver.
Solve the following academic quiz questions accurately.

{questions_prompt}
Instructions:
1. Select the correct option for each question based on college curriculum.
2. Return strictly valid JSON where keys are Question IDs:
{{
  "<question_id>": {{
    "selected_ids": ["<exact_option_id>"],
    "text_answer": null
  }}
}}
"""

        req_body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "response_mime_type": "application/json"
            }
        }

        try:
            resp = requests.post(url, json=req_body, timeout=20)
            if resp.status_code == 200:
                raw_out = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(raw_out)
                
                answers: Dict[str, Any] = {}
                for q_id, val in parsed.items():
                    if not isinstance(val, dict):
                        continue
                    q_type = q_types.get(q_id, "SINGLE_CHOICE")
                    valid_opts = valid_options_per_q.get(q_id, [])
                    sel_ids = [oid for oid in val.get("selected_ids", []) if oid in valid_opts]

                    if q_type in ["SINGLE_CHOICE", "BOOLEAN", "TRUE_FALSE"]:
                        answers[q_id] = sel_ids[0] if sel_ids else (valid_opts[0] if valid_opts else None)
                    elif q_type == "MULTIPLE_CHOICE":
                        answers[q_id] = sel_ids if sel_ids else ([valid_opts[0]] if valid_opts else [])
                    else:
                        answers[q_id] = val.get("text_answer") or "Answer"

                return answers
            else:
                logger.warning(f"Batch model {model} returned HTTP {resp.status_code}")
                return None
        except Exception as e:
            logger.warning(f"Batch model {model} error: {e}")
            return None

    def _solve_question(self, q_id: str, q_type: str, q_text: str, options: List[Dict[str, str]]) -> Any:
        """Solves a single question by calling Gemini with model fallback."""
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
        """Calls specific Gemini model."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"

        options_text = ""
        valid_ids = []
        for opt in options:
            valid_ids.append(opt["id"])
            options_text += f"- ID: \"{opt['id']}\" | Label: {opt['label']} | Text: {opt['text']}\n"

        prompt = f"""You are an expert college professor and academic exam solver.
Solve this quiz question accurately:

Question:
{q_text}

Question Type: {q_type}

Options:
{options_text}

Instructions:
1. Identify the correct answer option based on academic curriculum.
2. Return strictly valid JSON:
{{
  "selected_ids": ["<exact_option_id>"],
  "text_answer": "<string or null>",
  "explanation": "<brief rationale>"
}}
"""

        req_body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "response_mime_type": "application/json"
            }
        }

        try:
            resp = requests.post(url, json=req_body, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                raw_out = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(raw_out)
                logger.info(f"[{model}] Reason: {parsed.get('explanation')}")

                selected_ids = [oid for oid in parsed.get("selected_ids", []) if oid in valid_ids]
                if q_type in ["SINGLE_CHOICE", "BOOLEAN", "TRUE_FALSE"]:
                    return selected_ids[0] if selected_ids else (valid_ids[0] if valid_ids else None)
                elif q_type == "MULTIPLE_CHOICE":
                    return selected_ids if selected_ids else ([valid_ids[0]] if valid_ids else [])
                return parsed.get("text_answer") or "Answer"
            else:
                logger.warning(f"Model {model} returned HTTP {resp.status_code}")
                return None
        except Exception as e:
            logger.warning(f"Model {model} error: {e}")
            return None

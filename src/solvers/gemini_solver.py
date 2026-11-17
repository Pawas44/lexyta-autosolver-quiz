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

    def solve_quiz(self, quiz_sections: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Solves all questions in quiz sections using Gemini AI."""
        payload: Dict[str, Any] = {}
        total = 0

        for section in quiz_sections:
            sec_name = section.get("name", "Section")
            questions = section.get("questions", [])
            logger.info(f"Solving section '{sec_name}' ({len(questions)} questions)...")

            for q in questions:
                total += 1
                q_id = q.get("id")
                q_type = q.get("question_type", "MULTIPLE_CHOICE")
                raw_text = q.get("text", "")
                q_text = clean_html_text(raw_text)
                options = q.get("options", [])

                clean_options = [
                    {
                        "id": opt.get("id"),
                        "label": opt.get("label", ""),
                        "text": clean_html_text(opt.get("text", ""))
                    }
                    for opt in options
                ]

                logger.info(f"[Q{total}] ({q_type}) {q_text[:70]}...")
                answer = self._solve_question(q_id, q_type, q_text, clean_options)
                if answer is not None:
                    payload[q_id] = answer

        logger.info(f"Quiz solving completed: {len(payload)}/{total} answered.")
        return payload

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

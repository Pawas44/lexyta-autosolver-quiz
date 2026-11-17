"""
GitHub-backed Cloud State Persistence
Uses a JSON file in the private GitHub repo as a persistent state store.
Reads state on startup via raw URL, writes updates via GitHub API.
Survives Render free-tier restarts without any database.
"""

import os
import json
import base64
import logging
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger("GitHubSync")

# Config from environment variables (set on Render dashboard)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "Pawas44/lexyta-autosolver-autoinformer")
STATE_FILE_PATH = "data/cloud_state.json"


class GitHubStateSync:
    """Syncs bot state (users, solved quizzes, notified items) to a GitHub-hosted JSON file."""

    def __init__(self, token: str = "", repo: str = "", file_path: str = STATE_FILE_PATH):
        self.token = token or GITHUB_TOKEN
        self.repo = repo or GITHUB_REPO
        self.file_path = file_path
        self._sha: Optional[str] = None  # GitHub file SHA (needed for updates)
        self._api_base = f"https://api.github.com/repos/{self.repo}/contents/{self.file_path}"
        self._headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "LexytaBot"
        }

    def fetch_state(self) -> Dict[str, Any]:
        """Fetch the latest state from GitHub."""
        if not self.token:
            logger.warning("No GITHUB_TOKEN set. Cloud state sync disabled.")
            return {}

        try:
            resp = requests.get(self._api_base, headers=self._headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                self._sha = data.get("sha")
                content = base64.b64decode(data["content"]).decode("utf-8")
                state = json.loads(content)
                logger.info(f"Cloud state loaded from GitHub: {len(state.get('users', {}))} users")
                return state
            elif resp.status_code == 404:
                logger.info("No cloud state file found on GitHub. Will create on first save.")
                return {}
            else:
                logger.error(f"GitHub API error {resp.status_code}: {resp.text[:200]}")
                return {}
        except Exception as e:
            logger.error(f"Failed to fetch cloud state: {e}")
            return {}

    def save_state(self, state: Dict[str, Any], message: str = "chore: sync bot state [skip ci]") -> bool:
        """Push updated state to GitHub."""
        if not self.token:
            return False

        try:
            content_bytes = json.dumps(state, indent=2).encode("utf-8")
            content_b64 = base64.b64encode(content_bytes).decode("utf-8")

            payload: Dict[str, Any] = {
                "message": message,
                "content": content_b64,
                "branch": "main"
            }
            if self._sha:
                payload["sha"] = self._sha

            resp = requests.put(self._api_base, headers=self._headers, json=payload, timeout=20)
            if resp.status_code in [200, 201]:
                self._sha = resp.json().get("content", {}).get("sha")
                logger.info("Cloud state saved to GitHub successfully.")
                return True
            else:
                logger.error(f"GitHub save failed {resp.status_code}: {resp.text[:200]}")
                return False
        except Exception as e:
            logger.error(f"Failed to save cloud state: {e}")
            return False

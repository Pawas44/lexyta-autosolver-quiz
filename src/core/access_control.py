"""
Access Control & Whitelist Manager
Restricts bot usage to Telegram Chat IDs listed in a GitHub-hosted text file (allowed_chats.txt).
Polls/caches the raw GitHub file with a 30-second TTL so updates take effect live without restarting the server.
"""

import os
import time
import logging
import requests
from typing import Set, Optional

logger = logging.getLogger("AccessControl")

DEFAULT_RAW_URL = "https://raw.githubusercontent.com/Pawas44/lexyta-autosolver-quiz/main/allowed_chats.txt"
LOCAL_FILE = "allowed_chats.txt"
CACHE_TTL_SECONDS = 30


class AccessController:
    """Manages whitelisted Telegram Chat IDs fetched from GitHub raw file or local file."""

    def __init__(self, raw_url: Optional[str] = None, local_file: str = LOCAL_FILE, admin_chat_id: int = 8224782152):
        self.raw_url = raw_url or os.getenv("ALLOWED_CHATS_URL", DEFAULT_RAW_URL)
        self.local_file = local_file
        self.admin_chat_id = admin_chat_id
        self._cached_ids: Set[int] = set()
        self._last_fetch_time: float = 0.0

        # Initial load from local file
        self._load_from_local()

    def _parse_lines(self, content: str) -> Set[int]:
        """Parses chat IDs from plain text lines, ignoring comments and blanks."""
        ids: Set[int] = set()
        if self.admin_chat_id:
            ids.add(int(self.admin_chat_id))

        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Remove inline comments if any (e.g. "8224782152 # Admin")
            cleaned = line.split("#")[0].strip()
            try:
                ids.add(int(cleaned))
            except ValueError:
                pass
        return ids

    def _load_from_local(self):
        """Loads allowed IDs from local file if present."""
        if os.path.exists(self.local_file):
            try:
                with open(self.local_file, "r", encoding="utf-8") as f:
                    content = f.read()
                self._cached_ids = self._parse_lines(content)
                logger.info(f"Loaded {len(self._cached_ids)} allowed chat IDs from local {self.local_file}")
            except Exception as e:
                logger.warning(f"Could not read local {self.local_file}: {e}")

    def refresh(self, force: bool = False) -> Set[int]:
        """Fetches latest allowed chat IDs from GitHub raw URL if TTL expired or force=True."""
        now = time.time()
        if not force and (now - self._last_fetch_time) < CACHE_TTL_SECONDS:
            return self._cached_ids

        # Fetch from remote GitHub raw URL
        try:
            resp = requests.get(self.raw_url, timeout=10)
            if resp.status_code == 200:
                self._cached_ids = self._parse_lines(resp.text)
                self._last_fetch_time = now
                logger.debug(f"Refreshed whitelist from GitHub: {len(self._cached_ids)} active IDs")
                return self._cached_ids
            else:
                logger.warning(f"GitHub whitelist fetch returned HTTP {resp.status_code}. Using cached IDs.")
        except Exception as e:
            logger.warning(f"Failed to fetch whitelist from {self.raw_url}: {e}. Using cached IDs.")

        # Fallback to local file if remote failed and cache is empty
        if not self._cached_ids:
            self._load_from_local()

        self._last_fetch_time = now
        return self._cached_ids

    def is_allowed(self, chat_id: int) -> bool:
        """Checks if a Telegram chat ID is authorized."""
        allowed_set = self.refresh()
        try:
            cid = int(chat_id)
            return cid in allowed_set or cid == self.admin_chat_id
        except (ValueError, TypeError):
            return False

    def get_allowed_ids(self) -> Set[int]:
        """Returns the current set of allowed chat IDs."""
        return set(self.refresh())

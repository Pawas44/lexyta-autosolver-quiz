"""
Lexyta Olympiad API Client
Handles authentication, access code joining, attempt lifecycle, and submissions
for Grand Quizzes and Olympiad assessments (olympiad.lexyta.com).
"""

import re
import logging
import requests
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse, parse_qs
from .exceptions import LMSAuthError, LMSNetworkError, LMSQuizError

logger = logging.getLogger("OlympiadAPI")


def parse_olympiad_input(raw_input: str) -> Dict[str, Optional[str]]:
    """
    Parses any Olympiad URL or text input into structured components:
    - slug
    - access_code
    - invitation_code (token)
    - key (student key)

    Examples supported:
    - https://olympiad.lexyta.com/8uicOlC454?access_code=QsjLttvz
    - https://olympiad.lexyta.com/8uicOlC454?invitation_code=TOKEN123
    - https://olympiad.lexyta.com/8uicOlC454 key=MYKEY
    - 8uicOlC454 access_code=QsjLttvz
    """
    result: Dict[str, Optional[str]] = {
        "slug": None,
        "access_code": None,
        "invitation_code": None,
        "key": None,
    }

    text = raw_input.strip()

    # Check for direct key= or access_code= in string
    key_match = re.search(r'\bkey=([a-zA-Z0-9_-]+)', text, re.I)
    if key_match:
        result["key"] = key_match.group(1).strip()

    ac_match = re.search(r'\baccess_code=([a-zA-Z0-9_-]+)', text, re.I)
    if ac_match:
        result["access_code"] = ac_match.group(1).strip()

    inv_match = re.search(r'\b(?:invitation_code|auth_token|token)=([a-zA-Z0-9_-]+)', text, re.I)
    if inv_match:
        result["invitation_code"] = inv_match.group(1).strip()

    # If it's a URL
    if "olympiad.lexyta.com" in text or "http" in text or "/" in text:
        # Extract the URL portion
        url_match = re.search(r'https?://[^\s]+', text)
        target_url = url_match.group(0) if url_match else text
        parsed = urlparse(target_url)

        # Path: /8uicOlC454 or /8uicOlC454/
        path_parts = [p for p in parsed.path.split("/") if p]
        if path_parts:
            # Slug is usually the first path component
            result["slug"] = path_parts[0]

        # Query parameters
        qs = parse_qs(parsed.query)
        if "access_code" in qs and not result["access_code"]:
            result["access_code"] = qs["access_code"][0]
        if "invitation_code" in qs and not result["invitation_code"]:
            result["invitation_code"] = qs["invitation_code"][0]
        if "token" in qs and not result["invitation_code"]:
            result["invitation_code"] = qs["token"][0]
        if "key" in qs and not result["key"]:
            result["key"] = qs["key"][0]
    else:
        # Standalone slug or token
        tokens = text.split()
        if tokens:
            result["slug"] = tokens[0]

    return result


class OlympiadAPIClient:
    BASE_URL = "https://olympiad.lexyta.com/api"

    def __init__(self, email: str, session: Optional[requests.Session] = None):
        self.email = email
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Origin": "https://olympiad.lexyta.com",
            "Referer": "https://olympiad.lexyta.com/",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json"
        })
        self.current_slug: Optional[str] = None
        self.student_profile: Optional[Dict[str, Any]] = None

    def _sync_csrf(self):
        """Syncs the CSRF token from session cookies into request headers."""
        xsrf = self.session.cookies.get("X-XSRF-TOKEN")
        if xsrf:
            self.session.headers["X-CSRF-TOKEN"] = xsrf

    def get_base_info(self, slug: str) -> Optional[Dict[str, Any]]:
        """Fetches public basic metadata for an Olympiad (has_access_code, has_student_keys, name)."""
        url = f"{self.BASE_URL}/olympiads/{slug}/base"
        try:
            resp = self.session.get(url, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            logger.warning(f"Failed to fetch base info for {slug}: HTTP {resp.status_code}")
            return None
        except requests.RequestException as e:
            raise LMSNetworkError(f"Network error getting Olympiad base info: {e}")

    def get_details(self, slug: str) -> Optional[Dict[str, Any]]:
        """Fetches full Olympiad details (start/end dates, description, status)."""
        url = f"{self.BASE_URL}/olympiads/{slug}"
        try:
            resp = self.session.get(url, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            logger.warning(f"Failed to fetch details for {slug}: HTTP {resp.status_code}")
            return None
        except requests.RequestException as e:
            raise LMSNetworkError(f"Network error getting Olympiad details: {e}")

    def join_by_access_code(self, slug: str, access_code: str) -> bool:
        """
        Submits access code + student email to trigger the verification magic link email.
        Returns True if server accepted code and sent the email.
        """
        url = f"{self.BASE_URL}/olympiads/{slug}/join"
        payload = {
            "access_code": access_code,
            "email": self.email
        }
        try:
            resp = self.session.post(url, json=payload, timeout=20)
            self._sync_csrf()
            if resp.status_code == 200:
                logger.info(f"Access code accepted for {self.email} on {slug}. Verification email sent.")
                return True
            logger.warning(f"Join by access code failed: HTTP {resp.status_code} - {resp.text}")
            return False
        except requests.RequestException as e:
            raise LMSNetworkError(f"Network error joining Olympiad: {e}")

    def auth_with_token(self, slug: str, token: str) -> bool:
        """
        Exchanges the email invitation token for a session on Olympiad platform.
        Sets session cookies and initializes CSRF.
        """
        self.current_slug = slug
        url = f"{self.BASE_URL}/olympiads/{slug}/me/auth"
        headers = {"auth-token": token}
        try:
            resp = self.session.get(url, headers=headers, timeout=20)
            if resp.status_code == 200:
                self._sync_csrf()
                logger.info(f"Olympiad auth successful for {slug} with token.")
                # Hydrate profile
                self.get_me(slug)
                return True
            logger.warning(f"Token auth failed: HTTP {resp.status_code} - {resp.text}")
            return False
        except requests.RequestException as e:
            raise LMSNetworkError(f"Network error authenticating with token: {e}")

    def auth_with_key(self, slug: str, key: str) -> bool:
        """Authenticates directly using an organizer-provided personal student key."""
        self.current_slug = slug
        url = f"{self.BASE_URL}/olympiads/{slug}/auth/key"
        payload = {"key": key}
        try:
            resp = self.session.post(url, json=payload, timeout=20)
            if resp.status_code == 200:
                self._sync_csrf()
                logger.info(f"Olympiad auth successful for {slug} with student key.")
                self.get_me(slug)
                return True
            logger.warning(f"Student key auth failed: HTTP {resp.status_code} - {resp.text}")
            return False
        except requests.RequestException as e:
            raise LMSNetworkError(f"Network error authenticating with key: {e}")

    def get_me(self, slug: str) -> Optional[Dict[str, Any]]:
        """Retrieves authenticated participant profile for the Olympiad."""
        self._sync_csrf()
        url = f"{self.BASE_URL}/olympiads/{slug}/me"
        try:
            resp = self.session.get(url, timeout=15)
            if resp.status_code == 200:
                self.student_profile = resp.json()
                return self.student_profile
            return None
        except requests.RequestException:
            return None

    def get_assignment(self, slug: str) -> Optional[Dict[str, Any]]:
        """
        Fetches the complete exam assignment structure including all sections,
        questions, point weights, and multiple choice options.
        """
        self._sync_csrf()
        url = f"{self.BASE_URL}/olympiads/{slug}/assignment"
        try:
            resp = self.session.get(url, timeout=25)
            if resp.status_code == 200:
                return resp.json()
            logger.error(f"Failed to get assignment for {slug}: HTTP {resp.status_code} - {resp.text}")
            return None
        except requests.RequestException as e:
            raise LMSQuizError(f"Network error fetching Olympiad assignment: {e}")

    def start_attempt(self, slug: str) -> Optional[Dict[str, Any]]:
        """Starts a new assessment attempt for the student (or resumes existing in-progress attempt)."""
        self._sync_csrf()
        url = f"{self.BASE_URL}/olympiads/{slug}/me/attempt/start"
        try:
            resp = self.session.post(url, json={}, timeout=20)
            if resp.status_code in [200, 201]:
                return resp.json()
            logger.warning(f"Failed to start Olympiad attempt: HTTP {resp.status_code} - {resp.text}")
            return None
        except requests.RequestException as e:
            raise LMSQuizError(f"Network error starting Olympiad attempt: {e}")

    def get_attempt_answers(self, slug: str) -> Optional[Dict[str, Any]]:
        """Retrieves any previously saved answers for the current attempt."""
        self._sync_csrf()
        url = f"{self.BASE_URL}/olympiads/{slug}/me/attempt/answers"
        try:
            resp = self.session.get(url, timeout=20)
            if resp.status_code == 200:
                return resp.json()
            return {}
        except requests.RequestException:
            return {}

    def submit_attempt(self, slug: str, answers: Dict[str, Any]) -> bool:
        """
        Submits the complete answers dictionary for grading.
        Payload format: { [question_id]: option_id }
        """
        self._sync_csrf()
        url = f"{self.BASE_URL}/olympiads/{slug}/me/attempt/submit"
        try:
            resp = self.session.post(url, json=answers, timeout=30)
            if resp.status_code in [200, 201, 204]:
                logger.info(f"Olympiad {slug} answers submitted successfully!")
                return True
            logger.error(f"Olympiad submission failed: HTTP {resp.status_code} - {resp.text}")
            return False
        except requests.RequestException as e:
            raise LMSQuizError(f"Network error submitting Olympiad answers: {e}")

    def get_latest_attempt(self, slug: str) -> Optional[Dict[str, Any]]:
        """Retrieves the latest attempt status, score, and grade details."""
        self._sync_csrf()
        url = f"{self.BASE_URL}/olympiads/{slug}/me/attempt/latest"
        try:
            resp = self.session.get(url, timeout=20)
            if resp.status_code == 200:
                return resp.json()
            return None
        except requests.RequestException:
            return None

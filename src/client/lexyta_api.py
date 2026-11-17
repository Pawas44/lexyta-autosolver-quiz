"""
LMS Lexyta API Client
Handles authentication, sessions, CSRF headers, and course/quiz interactions.
"""

import requests
import logging
from typing import Dict, List, Optional, Any
from .exceptions import LMSAuthError, LMSNetworkError, LMSQuizError

logger = logging.getLogger("LexytaAPI")

class LexytaAPIClient:
    BASE_URL = "https://lms.lexyta.com/api"

    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Origin": "https://lms.lexyta.com",
            "Referer": "https://lms.lexyta.com/signin",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json"
        })
        self.user_profile: Optional[Dict[str, Any]] = None

    def _sync_csrf(self):
        """Syncs the CSRF token from session cookies into request headers."""
        xsrf = self.session.cookies.get("X-XSRF-TOKEN")
        if xsrf:
            self.session.headers["X-CSRF-TOKEN"] = xsrf

    def signin(self) -> bool:
        """Performs authentication to Lexyta LMS."""
        login_url = f"{self.BASE_URL}/signin"
        payload = {
            "email": self.email,
            "password": self.password
        }
        try:
            logger.info(f"Signing in as {self.email}...")
            resp = self.session.post(login_url, json=payload, timeout=20)
            if resp.status_code == 200:
                self._sync_csrf()
                logger.info("Sign-in successful! Session initialized.")
                self.get_profile()
                return True
            elif resp.status_code == 400:
                raise LMSAuthError(f"Invalid credentials for {self.email}: {resp.text}")
            else:
                raise LMSAuthError(f"Login failed with HTTP {resp.status_code}: {resp.text}")
        except requests.RequestException as e:
            raise LMSNetworkError(f"Network error during signin: {e}")

    def ensure_authenticated(self) -> bool:
        """Validates current session or re-authenticates."""
        profile = self.get_profile()
        if profile and "id" in profile:
            return True
        logger.info("Session expired or inactive. Authenticating...")
        return self.signin()

    def get_profile(self) -> Optional[Dict[str, Any]]:
        """Fetches student profile data."""
        self._sync_csrf()
        try:
            resp = self.session.get(f"{self.BASE_URL}/profile", timeout=15)
            if resp.status_code == 200:
                self.user_profile = resp.json()
                return self.user_profile
            return None
        except Exception:
            return None

    def get_enrolled_programs(self) -> List[Dict[str, Any]]:
        """Fetches all enrolled academic programs."""
        self._sync_csrf()
        url = f"{self.BASE_URL}/programs/enrolled?page=1&limit=50"
        try:
            resp = self.session.get(url, timeout=20)
            if resp.status_code == 200:
                return resp.json().get("items", [])
            return []
        except requests.RequestException as e:
            raise LMSNetworkError(f"Error fetching enrolled programs: {e}")

    def get_program_classes(self, program_id: str) -> List[Dict[str, Any]]:
        """Fetches all subjects/classes in a program."""
        self._sync_csrf()
        url = f"{self.BASE_URL}/programs/{program_id}/classes?page=1&limit=50"
        try:
            resp = self.session.get(url, timeout=20)
            if resp.status_code == 200:
                return resp.json().get("items", [])
            return []
        except requests.RequestException as e:
            raise LMSNetworkError(f"Error fetching classes for program {program_id}: {e}")

    def get_class_assignments(self, class_id: str) -> List[Dict[str, Any]]:
        """Fetches assignments and quizzes for a subject."""
        self._sync_csrf()
        url = f"{self.BASE_URL}/classes/{class_id}/student/assignments?page=1&limit=50"
        try:
            resp = self.session.get(url, timeout=20)
            if resp.status_code == 200:
                return resp.json().get("items", [])
            return []
        except requests.RequestException as e:
            raise LMSNetworkError(f"Error fetching assignments for class {class_id}: {e}")

    def get_assignment_details(self, class_id: str, assignment_id: str) -> Optional[Dict[str, Any]]:
        """Fetches detailed assignment info (descriptions, attached PDFs, etc.)."""
        self._sync_csrf()
        url = f"{self.BASE_URL}/assignments/classes/{class_id}/assignments/{assignment_id}"
        try:
            resp = self.session.get(url, timeout=20)
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            logger.warning(f"Failed to fetch details for assignment {assignment_id}: {e}")
            return None

    def start_quiz_attempt(self, class_id: str, assignment_id: str) -> Optional[Dict[str, Any]]:
        """Starts a new quiz attempt."""
        self._sync_csrf()
        url = f"{self.BASE_URL}/classes/{class_id}/student/assignments/{assignment_id}/attempts/start"
        try:
            resp = self.session.post(url, json={}, timeout=20)
            if resp.status_code in [200, 201]:
                return resp.json()
            logger.warning(f"Could not start quiz attempt: HTTP {resp.status_code} - {resp.text}")
            return None
        except Exception as e:
            raise LMSQuizError(f"Exception starting quiz attempt {assignment_id}: {e}")

    def get_quiz_questions(self, class_id: str, assignment_id: str) -> Optional[List[Dict[str, Any]]]:
        """Fetches sections, questions, and multiple choice options for a quiz."""
        self._sync_csrf()
        url = f"{self.BASE_URL}/classes/{class_id}/student/assignments/{assignment_id}/quiz/view"
        try:
            resp = self.session.get(url, timeout=25)
            if resp.status_code == 200:
                return resp.json()
            logger.error(f"Failed to fetch quiz questions: HTTP {resp.status_code} - {resp.text}")
            return None
        except Exception as e:
            raise LMSQuizError(f"Exception fetching quiz view: {e}")

    def submit_quiz_answers(self, class_id: str, assignment_id: str, answers: Dict[str, Any]) -> bool:
        """Submits formatted answer payload for a quiz attempt."""
        self._sync_csrf()
        url = f"{self.BASE_URL}/classes/{class_id}/student/assignments/{assignment_id}/attempts/submit"
        try:
            resp = self.session.post(url, json=answers, timeout=25)
            if resp.status_code in [200, 201, 204]:
                return True
            logger.error(f"Quiz submission rejected: HTTP {resp.status_code} - {resp.text}")
            return False
        except Exception as e:
            raise LMSQuizError(f"Exception submitting quiz answers: {e}")

    def get_latest_attempt(self, class_id: str, assignment_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves result of the latest attempt."""
        self._sync_csrf()
        url = f"{self.BASE_URL}/classes/{class_id}/student/assignments/{assignment_id}/attempts/latest"
        try:
            resp = self.session.get(url, timeout=20)
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception:
            return None

    def get_class_resources(self, class_id: str) -> List[Dict[str, Any]]:
        """Fetches resources attached to a class (e.g. Course outlines, Lesson Delivery Plans, Timetables)."""
        self._sync_csrf()
        url = f"{self.BASE_URL}/classes/{class_id}/resources?page=1&limit=50"
        try:
            resp = self.session.get(url, timeout=20)
            if resp.status_code == 200:
                return resp.json().get("items", [])
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch resources for class {class_id}: {e}")
            return []

    def get_course_topics(self, course_id: str) -> List[Dict[str, Any]]:
        """Fetches syllabus topics and attached PPTs/notes for a course."""
        self._sync_csrf()
        url = f"{self.BASE_URL}/syllables/{course_id}/topics"
        try:
            resp = self.session.get(url, timeout=20)
            if resp.status_code == 200:
                return resp.json().get("items", [])
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch syllabus topics for course {course_id}: {e}")
            return []

    def get_file_download_url(self, file_id: str) -> Optional[str]:
        """Resolves a pre-signed S3 download URL from LMS file storage."""
        self._sync_csrf()
        url = f"{self.BASE_URL}/files/download/{file_id}"
        try:
            resp = self.session.get(url, timeout=20)
            if resp.status_code == 200:
                s3_url = resp.json()
                if isinstance(s3_url, str) and s3_url.startswith("http"):
                    return s3_url
            logger.warning(f"Could not get download URL for file {file_id}: HTTP {resp.status_code}")
            return None
        except Exception as e:
            logger.error(f"Error fetching download URL for file {file_id}: {e}")
            return None

    def download_file_bytes(self, url_or_file_id: str) -> Optional[bytes]:
        """Downloads file content as raw bytes given a pre-signed URL or a LMS file ID."""
        target_url = url_or_file_id
        if not target_url.startswith("http"):
            resolved = self.get_file_download_url(url_or_file_id)
            if not resolved:
                return None
            target_url = resolved

        try:
            # S3 pre-signed URLs don't need LMS session cookies/headers
            r = requests.get(target_url, stream=True, timeout=45)
            if r.status_code == 200:
                return r.content
            logger.warning(f"Failed to download file from S3: HTTP {r.status_code}")
            return None
        except Exception as e:
            logger.error(f"Network error downloading file: {e}")
            return None

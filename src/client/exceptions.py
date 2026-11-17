"""
Core Exceptions for Lexyta LMS Client.
"""

class LMSException(Exception):
    """Base exception for all LMS related errors."""
    pass

class LMSAuthError(LMSException):
    """Raised when authentication fails or session expires."""
    pass

class LMSNetworkError(LMSException):
    """Raised when network connection fails."""
    pass

class LMSQuizError(LMSException):
    """Raised when quiz operation (start/fetch/submit) fails."""
    pass

"""
Abstract Base Notifier Interface.
"""

from abc import ABC, abstractmethod

class BaseNotifier(ABC):
    @abstractmethod
    def send(self, message: str) -> bool:
        """Sends the notification. Returns True if successfully dispatched."""
        pass

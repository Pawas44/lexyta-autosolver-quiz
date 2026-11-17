"""
Abstract Base Class for Quiz Solvers.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any

class BaseQuizSolver(ABC):
    @abstractmethod
    def solve_quiz(self, quiz_sections: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Solves all questions in given quiz sections.
        Returns a dict mapping question_id -> answers:
          - MULTIPLE_CHOICE: [option_id, ...]
          - SINGLE_CHOICE / BOOLEAN: option_id
          - SHORT_ANSWER / LONG_ANSWER: text
        """
        pass

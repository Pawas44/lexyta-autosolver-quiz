"""
Unit test for Gemini AI Quiz Solver.
"""

import unittest
from src.core.config import AppConfig
from src.solvers.gemini_solver import GeminiQuizSolver

class TestGeminiSolver(unittest.TestCase):
    def setUp(self):
        self.config = AppConfig.load()
        self.solver = GeminiQuizSolver(self.config.gemini_api_key, self.config.gemini_models)

    def test_solve_single_choice(self):
        sample_sections = [
            {
                "name": "General Science",
                "questions": [
                    {
                        "id": "q_water",
                        "question_type": "SINGLE_CHOICE",
                        "text": "<p>What is the chemical formula for water?</p>",
                        "options": [
                            {"id": "opt_co2", "label": "A", "text": "CO2"},
                            {"id": "opt_h2o", "label": "B", "text": "H2O"},
                            {"id": "opt_o2", "label": "C", "text": "O2"},
                            {"id": "opt_nacl", "label": "D", "text": "NaCl"}
                        ]
                    }
                ]
            }
        ]
        result = self.solver.solve_quiz(sample_sections)
        self.assertEqual(result.get("q_water"), "opt_h2o", "Gemini should identify H2O as water")

if __name__ == "__main__":
    unittest.main()

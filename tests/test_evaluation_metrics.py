import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from app.evaluation import runner


class TextMetricTests(unittest.TestCase):
    def test_normalize_removes_accents_case_and_punctuation(self):
        self.assertEqual(runner.normalize("  ÁRBOL, café! 42—OK "), "arbol cafe 42 ok")

    def test_token_f1_uses_normalized_tokens_and_multiplicity(self):
        self.assertEqual(runner.token_f1("El número es 3,5", "el numero es 3 5"), 1.0)
        self.assertEqual(runner.token_f1("gato gato perro", "gato perro perro"), 2 / 3)

    def test_token_f1_handles_empty_and_disjoint_text(self):
        self.assertEqual(runner.token_f1("", "   "), 1.0)
        self.assertEqual(runner.token_f1("respuesta", "referencia"), 0.0)
        self.assertEqual(runner.token_f1("respuesta", ""), 0.0)


class AbstentionMetricTests(unittest.IsolatedAsyncioTestCase):
    async def test_abstention_rates_are_computed_with_model_calls_mocked(self):
        cases = [
            {"id": "A1", "question": "respondible acertada", "should_abstain": False,
             "reference_answer": "3.14", "evidence_terms": ["3.14"]},
            {"id": "A2", "question": "respondible omitida", "should_abstain": False,
             "reference_answer": "dos", "evidence_terms": ["dos"]},
            {"id": "U1", "question": "sin respuesta y abstiene", "should_abstain": True,
             "reference_answer": "", "evidence_terms": []},
            {"id": "U2", "question": "sin respuesta e inventa", "should_abstain": True,
             "reference_answer": "", "evidence_terms": []},
        ]
        responses = {
            "respondible acertada": {
                "answer": "3.14", "abstained": False,
                "citations": [{"id": "S1", "source": "demo.md", "page": 1, "text": "El valor es 3.14."}],
            },
            "respondible omitida": {"answer": "No lo sé", "abstained": True, "citations": []},
            "sin respuesta y abstiene": {"answer": "No lo sé", "abstained": True, "citations": []},
            "sin respuesta e inventa": {
                "answer": "Hay una respuesta inventada", "abstained": False,
                "citations": [{"id": "S1", "source": "demo.md", "page": 1, "text": "Texto no relacionado."}],
            },
        }

        class FakeStore:
            def search(self, question, limit):
                return []

        async def fake_answer_question(question, passages):
            return responses[question]

        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            dataset = temp_dir / "dataset.jsonl"
            dataset.write_text("\n".join(json.dumps(case) for case in cases), encoding="utf-8")
            with (
                patch.object(runner, "get_store", return_value=FakeStore()),
                patch.object(runner, "answer_question", new=AsyncMock(side_effect=fake_answer_question)),
                patch.object(runner, "judge_faithfulness", new=AsyncMock(side_effect=AssertionError("judge must stay off"))),
                patch.object(runner, "DEFAULT_REPORTS", temp_dir / "reports"),
            ):
                report = await runner.run_evaluation(dataset, use_judge=False)

        self.assertEqual(report["accuracy_rate"], 0.5)
        self.assertEqual(report["correct_abstention_rate"], 0.5)
        self.assertEqual(report["unsupported_answer_rate_on_unanswerable"], 0.5)
        self.assertEqual(report["false_abstention_rate_on_answerable"], 0.5)
        self.assertEqual([row["correct"] for row in report["results"]], [True, False, True, False])
        self.assertEqual(report["faithfulness_judged_count"], 0)


if __name__ == "__main__":
    unittest.main()

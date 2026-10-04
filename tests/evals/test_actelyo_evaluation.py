import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("actelyo_evaluation", REPO / "evals" / "actelyo-law-harness" / "run.py")
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)

class EvaluationTests(unittest.TestCase):
    def test_blocking_removes_defective_delivery_but_does_not_create_legal_success(self):
        case = {"id": "fixture", "rubric": {"risk_required": True}}
        analysis = {"summary": "fixture", "open_questions": [], "risks": [
            {"clause": {"document_id": "contract", "quote": "Cette clause de test existe dans le contrat."},
             "issue": "fixture", "severity": "high", "analysis": "fixture", "proposal": "fixture",
             "limitations": [], "citations": [{"evidence_id": "unknown", "quote": "citation invented for test"}]}]}
        checks = evaluation.diagnostics(analysis, [{"id": "contract", "text": "Cette clause de test existe dans le contrat."}], {})
        self.assertTrue(checks["citation_defect"])
        raw = {"case_id": "fixture", "arm": "grounded_model", "analysis": analysis,
               "status": "draft", "checks": checks, "mechanical_proxy_pass": False, "seconds": 1}
        blocked = {**raw, "arm": "harness", "status": "blocked_validation"}
        self.assertFalse(evaluation.mechanical_proxy(case, blocked, checks))
        result = evaluation.summarize([raw, blocked], [case])
        self.assertEqual(result["harness"]["generated_citation_defect_responses"], 1)
        self.assertEqual(result["harness"]["delivered_citation_defect_responses"], 0)
        self.assertEqual(result["harness"]["delivered_responses_denominator"], 0)
        self.assertEqual(result["harness"]["delivery_coverage"], 0)
        self.assertIsNone(result["harness"]["substantive_legal_success_rate"])
        self.assertIsNone(result["harness"]["overall_hallucination_rate"])
        self.assertEqual(result["grounded_model"]["delivered_citation_defect_responses"], 1)

    def test_adjudication_requires_complete_boolean_criteria_and_reports_partial_denominators(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            evaluation.write_json(folder / "manifest.json", {"dataset_sha256": "fixture-hash"})
            evaluation.write_json(folder / "dataset.snapshot.json", {"cases": [
                {"id": "fixture", "rubric": {"human_criteria": ["criterion one", "criterion two"]}}]})
            evaluation.write_json(folder / "blind-key.json", [
                {"answer_id": "a", "case_id": "fixture", "arm": "harness", "repeat": 1},
                {"answer_id": "b", "case_id": "fixture", "arm": "grounded_model", "repeat": 1}])
            annotations = folder / "annotations.json"
            evaluation.write_json(annotations, [
                {"answer_id": "a", "reviewer": "fixture jurist", "qualified_legal_reviewer": True,
                 "criteria_met": [True, None], "hallucination_found": False}])
            evaluation.adjudicate(folder, annotations)
            data = json.loads((folder / "human-results.json").read_text())
            self.assertIsNone(data["results"]["harness"]["success_rate_among_reviewed"])
            evaluation.write_json(annotations, [
                {"answer_id": "a", "reviewer": "fixture jurist", "qualified_legal_reviewer": True,
                 "criteria_met": [True, False], "hallucination_found": True}])
            evaluation.adjudicate(folder, annotations)
            data = json.loads((folder / "human-results.json").read_text())
            self.assertEqual(data["results"]["harness"]["success_rate_among_reviewed"], 0)
            self.assertEqual(data["results"]["harness"]["hallucination_rate_among_reviewed"], 1)
            self.assertTrue(data["results"]["harness"]["complete"])
            self.assertFalse(data["results"]["grounded_model"]["complete"])
            self.assertIsNone(data["results"]["grounded_model"]["hallucination_rate_among_reviewed"])

if __name__ == "__main__":
    unittest.main()


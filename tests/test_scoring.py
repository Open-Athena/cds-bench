"""Strict answer-format and comparison rules, without inference or solvers."""

import unittest

from cds_bench.scoring import score, score_result


class ScoringTests(unittest.TestCase):
    def test_marker_is_required_on_its_own_line(self):
        case = {"answer": "42", "output_format": "scalar"}
        for response in ("42", "Final answer: 42", "final answer:\n42"):
            with self.subTest(response=response):
                self.assertFalse(score(case, response)["format_ok"])
        self.assertTrue(score(case, "Explanation.\nFinal answer:\n42")["passed"])

    def test_last_marker_selects_the_final_answer(self):
        case = {"answer": "42", "output_format": "scalar"}
        response = "Final answer:\n17\nReconsidering.\nFinal answer:\n42"
        self.assertTrue(score(case, response)["passed"])

    def test_sequence_spacing_but_not_case_or_extra_residues(self):
        case = {"answer": "MKA", "output_format": "scalar"}
        self.assertTrue(score(case, "Final answer:\nM K\nA")["passed"])
        for answer in ("mka", "MKAA", "MKA\nexplanation"):
            with self.subTest(answer=answer):
                self.assertFalse(score(case, "Final answer:\n" + answer)["passed"])

    def test_numeric_values_are_exact_and_finite(self):
        case = {"answer": "1.8500", "output_format": "scalar"}
        self.assertTrue(score(case, "Final answer:\n1.85")["passed"])
        for answer in ("1.8501", "NaN", "Infinity"):
            with self.subTest(answer=answer):
                self.assertFalse(score(case, "Final answer:\n" + answer)["passed"])

    def test_json_key_order_and_numeric_spelling(self):
        case = {"answer": '{"n":1,"xs":[1,2]}', "output_format": "json"}
        self.assertTrue(score(case, 'Final answer:\n{"xs": [1, 2], "n": 1.0}')["passed"])

    def test_json_types_values_fields_and_list_order(self):
        case = {"answer": '{"n":1,"xs":[1,2]}', "output_format": "json"}
        for answer in (
            '{"n":true,"xs":[1,2]}',
            '{"n":"1","xs":[1,2]}',
            '{"n":1,"xs":[2,1]}',
            '{"n":1,"xs":[1,2,2]}',
            '{"n":1,"xs":[1,2],"extra":0}',
            '{"xs":[1,2]}',
        ):
            with self.subTest(answer=answer):
                self.assertFalse(score(case, "Final answer:\n" + answer)["passed"])

    def test_invalid_json_and_duplicate_keys_fail(self):
        case = {"answer": '{"n":1}', "output_format": "json"}
        for answer in ('{"n":1,"n":1}', '{"n":NaN}', "{'n': 1}", '```json\n{"n":1}\n```'):
            with self.subTest(answer=answer):
                self.assertFalse(score(case, "Final answer:\n" + answer)["format_ok"])

    def test_scalar_list_order_and_impossible(self):
        case = {"answer": "[1,2]", "output_format": "scalar"}
        self.assertTrue(score(case, "Final answer:\n[1, 2]")["passed"])
        self.assertFalse(score(case, "Final answer:\n[2,1]")["passed"])
        case["answer"] = "IMPOSSIBLE"
        self.assertTrue(score(case, "Final answer:\nIMPOSSIBLE")["passed"])

    def test_truncation_fails_even_with_the_correct_answer(self):
        case = {"answer": "42", "output_format": "scalar"}
        result = score_result(case, "Final answer:\n42", "length")
        self.assertFalse(result["passed"])
        self.assertTrue(result["truncated"])
        self.assertTrue(score_result(case, "Final answer:\n42", "stop")["passed"])


if __name__ == "__main__":
    unittest.main()

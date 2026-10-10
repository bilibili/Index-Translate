import hashlib
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("runner", Path(__file__).resolve().parents[1] / "run.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

class RunnerTest(unittest.TestCase):
    def test_equal_band_weights_and_missing_band(self):
        groups = {b: {"segale_comet": v, "scored_cases": n, "cases": n}
                  for b, v, n in zip(runner.BANDS, [0.2, 0.4, 0.6, 0.8, 1.0], [24, 24, 12, 12, 12])}
        summary = {"groups": {"length_band": groups}}
        self.assertAlmostEqual(runner.five_band_macro(summary)["value"], 0.6)
        groups["64k"]["segale_comet"] = None
        groups["64k"]["scored_cases"] = 0
        result = runner.five_band_macro(summary)
        self.assertIsNone(result["value"])
        self.assertEqual(result["coverage"]["64k"],
                         {"scored": 0, "scored_with_comet": 0, "total": 12})

    def test_raw_translation_and_unknown_metadata(self):
        text = "  First.\nSecond.\u2028Third.  "
        original = {"case_id": "x", "mt": text}
        row = runner.prepare_generations([original])[0]
        self.assertEqual(row["mt"], text)
        self.assertEqual(row["output_sha256"], hashlib.sha256(text.encode()).hexdigest())
        self.assertIsNone(row["finish_reason"])
        self.assertIsNone(row["cap_hit"])
        self.assertNotIn("output_sha256", original)
        supplied = dict(original, output_sha256="invalid")
        self.assertEqual(runner.prepare_generations([supplied])[0]["output_sha256"], "invalid")

if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from survey_methods import survey_mean, survey_wls


class TestSurveyMethods(unittest.TestCase):
    def setUp(self) -> None:
        self.data = pd.DataFrame(
            {
                "stratum": [1, 1, 1, 1, 2, 2, 2, 2],
                "psu": [1, 1, 2, 2, 1, 1, 2, 2],
                "weight": [1.0, 2.0, 1.0, 2.0, 1.5, 1.0, 1.5, 1.0],
                "outcome": [1.0, 2.0, 3.0, 4.0, 2.0, 3.0, 4.0, 5.0],
                "const": 1.0,
                "x": [0.0, 1.0, 2.0, 3.0, 0.0, 1.0, 2.0, 3.0],
            }
        )

    def test_weighted_mean_matches_direct_calculation(self) -> None:
        result = survey_mean(
            self.data, "outcome", "weight", "stratum", "psu"
        )
        expected = np.average(self.data["outcome"], weights=self.data["weight"])
        self.assertAlmostEqual(result.estimate, expected)
        self.assertGreater(result.standard_error, 0)
        self.assertEqual(result.unweighted_n, len(self.data))

    def test_domain_keeps_design_and_changes_target(self) -> None:
        domain = self.data["x"] >= 2
        result = survey_mean(
            self.data, "outcome", "weight", "stratum", "psu", domain
        )
        expected = np.average(
            self.data.loc[domain, "outcome"],
            weights=self.data.loc[domain, "weight"],
        )
        self.assertAlmostEqual(result.estimate, expected)
        self.assertEqual(result.unweighted_n, int(domain.sum()))

    def test_survey_wls_recovers_linear_relationship(self) -> None:
        model_data = self.data.copy()
        model_data["outcome"] = 2.0 + 3.0 * model_data["x"]
        result = survey_wls(
            model_data,
            "outcome",
            ["const", "x"],
            "weight",
            "stratum",
            "psu",
        )
        self.assertAlmostEqual(result.coefficients["const"], 2.0)
        self.assertAlmostEqual(result.coefficients["x"], 3.0)
        self.assertTrue((result.standard_errors >= 0).all())

    def test_nonpositive_weights_are_excluded(self) -> None:
        altered = self.data.copy()
        altered.loc[0, "weight"] = 0
        result = survey_mean(
            altered, "outcome", "weight", "stratum", "psu"
        )
        self.assertEqual(result.unweighted_n, len(altered) - 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)

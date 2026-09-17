from __future__ import annotations

import sys
import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from survey_methods import survey_mean, survey_wls


class TestSurveyMethods(unittest.TestCase):
    def test_independent_r_survey_reference(self) -> None:
        fixture = pd.read_csv(ROOT / "tests/fixtures/survey_fixture.csv")
        reference = json.loads((ROOT / "tests/fixtures/survey_reference.json").read_text())
        for case, expected in reference["cases"].items():
            with self.subTest(case=case):
                data = fixture.copy()
                if case == "missing_predictor":
                    data.loc[0, "x"] = np.nan
                domain = data.x.ge(1) if case == "sparse_domain" else pd.Series(True, index=data.index)
                result = survey_mean(data, "outcome", "weight", "stratum", "psu", domain)
                self.assertAlmostEqual(result.estimate, expected["mean"], places=10)
                self.assertAlmostEqual(result.standard_error, expected["se"], places=10)
                self.assertEqual(result.design_df, expected["mean_df"])
                self.assertAlmostEqual(result.lower_95, expected["lower_95"], places=9)
                self.assertAlmostEqual(result.upper_95, expected["upper_95"], places=9)
                model = survey_wls(data, "outcome", ["const", "x"], "weight", "stratum", "psu", domain)
                np.testing.assert_allclose(model.coefficients, expected["coefficients"], rtol=1e-10, atol=1e-10)
                np.testing.assert_allclose(model.covariance, expected["covariance"], rtol=1e-10, atol=1e-10)
                self.assertEqual(model.residual_df, expected["residual_df"])

    def test_lonely_stratum_and_singular_model_fail_explicitly(self) -> None:
        lonely = self.data.drop(index=[2, 3])
        with self.assertRaisesRegex(ValueError, "Single-PSU"):
            survey_mean(lonely, "outcome", "weight", "stratum", "psu")
        singular = self.data.assign(duplicate=self.data.x)
        with self.assertRaisesRegex(ValueError, "rank deficient"):
            survey_wls(singular, "outcome", ["const", "x", "duplicate"], "weight", "stratum", "psu")

    def test_zero_domain_degrees_of_freedom_does_not_fabricate_interval(self) -> None:
        result = survey_mean(self.data, "outcome", "weight", "stratum", "psu", self.data.x.ge(2))
        self.assertEqual(result.design_df, 0)
        self.assertTrue(np.isnan(result.lower_95))
        self.assertGreater(result.standard_error, 0)

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

"""Aggregate executed report; no participant-level results are published."""
import platform
import numpy as np
import pandas as pd
import scipy
from survey_methods import survey_mean


def table(frame):
    columns = list(frame.columns)
    def cell(value):
        if pd.isna(value):
            return "Not estimable"
        return f"{value:.3f}" if isinstance(value, (float, np.floating)) else str(value).replace("|", "/")
    return "\n".join([
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
        *["| " + " | ".join(map(cell, row)) + " |" for row in frame.itertuples(index=False, name=None)],
    ])


def write_report(frame, masks, estimates, regressions, flow, output):
    # Compare observed outcome distributions by income-response status without
    # pretending this identifies a missing-at-random mechanism.
    rows = []
    for name, domain in [
        ("All eligible adults", masks["analytic"]),
        ("Income observed", masks["regression"]),
        ("Income missing", masks["analytic"] & frame.INDFMPIR.isna()),
    ]:
        for outcome in ["fiber_g_per_1000_kcal", "sodium_mg_per_1000_kcal"]:
            result = survey_mean(frame, outcome, "WTDR2D", "SDMVSTRA", "SDMVPSU", domain)
            rows.append(dict(group=name, outcome=outcome, estimate=result.estimate,
                             lower_95=result.lower_95, upper_95=result.upper_95,
                             unweighted_n=result.unweighted_n, design_df=result.design_df))
    selection = pd.DataFrame(rows)
    selection.to_csv(output / "income_response_comparison.csv", index=False, float_format="%.4f", lineterminator="\n")

    # Deliberately simple pattern-mixture stress test, not inferential imputation.
    from run_analysis import regression_estimates
    scenarios = []
    medians = frame.loc[masks["regression"]].groupby(["age_group", "sex"], observed=True).INDFMPIR.median()
    missing = masks["analytic"] & frame.INDFMPIR.isna()
    for delta in [-1., 0., 1.]:
        completed = frame.copy()
        baseline = [medians.loc[(age, sex)] for age, sex in zip(frame.loc[missing, "age_group"], frame.loc[missing, "sex"])]
        completed.loc[missing, "INDFMPIR"] = np.clip(np.asarray(baseline) + delta, 0, 5)
        result = regression_estimates(completed, masks["analytic"])
        income = result[result.term.str.startswith("Family income")]
        for row in income.itertuples():
            scenarios.append(dict(scenario=f"Missing income: cell median {delta:+.0f}",
                                  outcome=row.outcome, income_coefficient=row.estimate,
                                  unweighted_n=row.unweighted_n))
    sensitivity = pd.DataFrame(scenarios)
    sensitivity.to_csv(output / "income_sensitivity_scenarios.csv", index=False, float_format="%.4f", lineterminator="\n")
    text = "\n\n".join([
        "# Executed nutritional-epidemiology report",
        "## Question and population",
        "How do two-day fiber and sodium densities vary by age, sex, and family income-to-poverty ratio? This analysis uses public-use NHANES 2017–2018 adults aged 20+, excludes those identified as pregnant, and requires two reliable recalls and positive WTDR2D weights. It is a cross-sectional portfolio analysis, not clinical guidance.",
        "## Cohort flow", table(flow),
        "## Descriptive estimates",
        "Weighted ratio means; Taylor-linearized SEs; t-based 95% intervals using domain design degrees of freedom. Sample counts are unweighted.",
        "![Fiber density, age-domain point estimates with 95% intervals](../assets/fiber-density-by-age.svg)",
        "![Sodium density, age-domain point estimates with 95% intervals](../assets/sodium-density-by-age.svg)",
        table(estimates[["group", "measure", "estimate", "lower_95", "upper_95", "unweighted_n", "design_df"]]),
        "## Adjusted associations",
        "![Mutually adjusted nutrient-density associations with 95% intervals](../assets/adjusted-associations.svg)",
        "[All coefficients, sample counts, and regression residual df](regression_coefficients.csv). These are descriptive associations, not causal effects. Group-interval overlap is not a test of a between-group contrast.",
        "## Income nonresponse: observed-data comparison", table(selection),
        "Comparing measured outcomes in income responders and nonresponders exposes selection but cannot establish why income is missing or remove bias.",
        "## Missing-income assumption stress test", table(sensitivity),
        "For missing income, each scenario assigns the unweighted observed median within age-by-sex cells, then shifts it by -1, 0, or +1 ratio unit and clips to the released 0–5 range. All original eligible adults enter these scenario regressions. The complete-case estimate remains primary. These are deliberately coarse, post-audit sensitivity scenarios, not prespecified substantive hypotheses, multiple imputation, or proof of robustness to all missing-not-at-random mechanisms. Only coefficient estimates are shown: ordinary model SEs would ignore imputation uncertainty and should not be interpreted as valid inferential intervals here.",
        "## Verification and limitations",
        "Means, SEs, and regression covariance are checked against R survey 4.5 on a committed fixture, including sparse domains and missing predictors. Single-PSU strata and singular designs fail explicitly; zero inferential df yields no interval. [Methods and benchmark protocol](../docs/methods.md).",
        "Two recalls do not recover usual intake. Recall error, residual confounding, influential weights, and nonresponse remain. The audit did not fit a usual-intake model or a missingness model, and this single-cycle analysis is not a definitive population study.",
        "## Reproduction",
        "Run `python scripts/run_analysis.py` after installing `requirements.txt`. Only aggregate outputs are committed. [Source URLs and SHA-256 checksums](../data/source-manifest.json) are verified before analysis.",
        f"Executed with Python {platform.python_version_tuple()[0]}.{platform.python_version_tuple()[1]}, NumPy {np.__version__}, pandas {pd.__version__}, SciPy {scipy.__version__}.",
    ])
    (output / "report.md").write_text(text + "\n", encoding="utf-8", newline="\n")

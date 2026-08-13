"""Download public NHANES files and reproduce the portfolio analysis."""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from survey_methods import survey_mean, survey_wls

DATA_DIR = ROOT / "data" / "raw"
OUTPUT_DIR = ROOT / "outputs"
ASSET_DIR = ROOT / "assets"

SOURCES = {
    "DEMO_J.XPT": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/DEMO_J.XPT",
    "DR1TOT_J.XPT": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/DR1TOT_J.XPT",
    "DR2TOT_J.XPT": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/DR2TOT_J.XPT",
}


def download_file(filename: str, url: str) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    destination = DATA_DIR / filename
    if destination.exists():
        return destination
    request = urllib.request.Request(
        url, headers={"User-Agent": "mjeans-nhanes-portfolio/1.0"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        destination.write_bytes(response.read())
    return destination


def read_source(filename: str, columns: list[str]) -> pd.DataFrame:
    path = download_file(filename, SOURCES[filename])
    frame = pd.read_sas(path, format="xport", encoding="utf-8")
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise KeyError(f"{filename} is missing expected fields: {missing}")
    return frame[columns].copy()


def build_analysis_frame() -> pd.DataFrame:
    demo = read_source(
        "DEMO_J.XPT",
        [
            "SEQN",
            "RIDAGEYR",
            "RIAGENDR",
            "RIDEXPRG",
            "INDFMPIR",
            "SDMVSTRA",
            "SDMVPSU",
        ],
    )
    day1 = read_source(
        "DR1TOT_J.XPT",
        [
            "SEQN",
            "WTDR2D",
            "DR1DRSTZ",
            "DR1TKCAL",
            "DR1TFIBE",
            "DR1TSODI",
        ],
    )
    day2 = read_source(
        "DR2TOT_J.XPT",
        [
            "SEQN",
            "DR2DRSTZ",
            "DR2TKCAL",
            "DR2TFIBE",
            "DR2TSODI",
        ],
    )
    frame = demo.merge(day1, on="SEQN", how="left").merge(
        day2, on="SEQN", how="left"
    )
    frame["mean_energy_kcal"] = frame[["DR1TKCAL", "DR2TKCAL"]].mean(
        axis=1, skipna=False
    )
    frame["mean_fiber_g"] = frame[["DR1TFIBE", "DR2TFIBE"]].mean(
        axis=1, skipna=False
    )
    frame["mean_sodium_mg"] = frame[["DR1TSODI", "DR2TSODI"]].mean(
        axis=1, skipna=False
    )
    frame["fiber_g_per_1000_kcal"] = (
        frame["mean_fiber_g"] / frame["mean_energy_kcal"] * 1000
    )
    frame["sodium_mg_per_1000_kcal"] = (
        frame["mean_sodium_mg"] / frame["mean_energy_kcal"] * 1000
    )
    frame["age_group"] = pd.cut(
        frame["RIDAGEYR"],
        bins=[20, 40, 60, np.inf],
        labels=["20-39", "40-59", "60+"],
        right=False,
    )
    frame["sex"] = frame["RIAGENDR"].map({1.0: "Male", 2.0: "Female"})
    return frame


def eligibility_masks(frame: pd.DataFrame) -> dict[str, pd.Series]:
    positive_weight = frame["WTDR2D"].fillna(0) > 0
    reliable = (frame["DR1DRSTZ"] == 1) & (frame["DR2DRSTZ"] == 1)
    adult = frame["RIDAGEYR"] >= 20
    nonpregnant = frame["RIDEXPRG"].ne(1) | frame["RIDEXPRG"].isna()
    nutrient_complete = (
        frame[
            [
                "DR1TKCAL",
                "DR2TKCAL",
                "DR1TFIBE",
                "DR2TFIBE",
                "DR1TSODI",
                "DR2TSODI",
            ]
        ]
        .notna()
        .all(axis=1)
        & (frame["DR1TKCAL"] > 0)
        & (frame["DR2TKCAL"] > 0)
    )
    analytic = (
        positive_weight & reliable & adult & nonpregnant & nutrient_complete
    )
    return {
        "positive_weight": positive_weight,
        "reliable": reliable,
        "adult": adult,
        "nonpregnant": nonpregnant,
        "nutrient_complete": nutrient_complete,
        "analytic": analytic,
        "regression": analytic & frame["INDFMPIR"].notna(),
    }


def cohort_flow(frame: pd.DataFrame, masks: dict[str, pd.Series]) -> pd.DataFrame:
    cumulative = pd.Series(True, index=frame.index)
    rows = [("Merged demographic participants", int(cumulative.sum()))]
    steps = [
        ("Positive two-day dietary weight", "positive_weight"),
        ("Two reliable dietary recalls", "reliable"),
        ("Age 20 years or older", "adult"),
        ("Not identified as pregnant", "nonpregnant"),
        ("Complete energy, fiber, and sodium", "nutrient_complete"),
    ]
    for label, key in steps:
        cumulative &= masks[key]
        rows.append((label, int(cumulative.sum())))
    rows.append(
        (
            "Complete income-to-poverty ratio for regression",
            int(masks["regression"].sum()),
        )
    )
    return pd.DataFrame(rows, columns=["stage", "participants"])


def descriptive_estimates(
    frame: pd.DataFrame, analytic: pd.Series
) -> pd.DataFrame:
    groups: list[tuple[str, str, pd.Series]] = [
        ("Overall", "All adults", analytic)
    ]
    for label in ["Male", "Female"]:
        groups.append(("Sex", label, analytic & frame["sex"].eq(label)))
    for label in ["20-39", "40-59", "60+"]:
        groups.append(
            ("Age group", label, analytic & frame["age_group"].eq(label))
        )

    measures = {
        "Fiber (g per 1,000 kcal)": "fiber_g_per_1000_kcal",
        "Sodium (mg per 1,000 kcal)": "sodium_mg_per_1000_kcal",
    }
    rows: list[dict[str, object]] = []
    for group_type, group, domain in groups:
        for measure, outcome in measures.items():
            result = survey_mean(
                frame,
                outcome,
                "WTDR2D",
                "SDMVSTRA",
                "SDMVPSU",
                domain,
            )
            rows.append(
                {
                    "group_type": group_type,
                    "group": group,
                    "measure": measure,
                    "estimate": result.estimate,
                    "standard_error": result.standard_error,
                    "lower_95": result.lower_95,
                    "upper_95": result.upper_95,
                    "unweighted_n": result.unweighted_n,
                    "effective_n": result.effective_n,
                }
            )
    return pd.DataFrame(rows)


def regression_estimates(
    frame: pd.DataFrame, regression_domain: pd.Series
) -> pd.DataFrame:
    model_frame = frame.copy()
    model_frame["intercept"] = 1.0
    model_frame["age_40_59"] = frame["age_group"].eq("40-59").astype(float)
    model_frame["age_60_plus"] = frame["age_group"].eq("60+").astype(float)
    model_frame["female"] = frame["sex"].eq("Female").astype(float)
    predictors = [
        "intercept",
        "age_40_59",
        "age_60_plus",
        "female",
        "INDFMPIR",
    ]
    labels = {
        "intercept": "Intercept: male, age 20-39, income ratio 0",
        "age_40_59": "Age 40-59 vs 20-39",
        "age_60_plus": "Age 60+ vs 20-39",
        "female": "Female vs male",
        "INDFMPIR": "Family income-to-poverty ratio (per unit)",
    }
    outcomes = {
        "Fiber (g per 1,000 kcal)": "fiber_g_per_1000_kcal",
        "Sodium (mg per 1,000 kcal)": "sodium_mg_per_1000_kcal",
    }
    rows: list[dict[str, object]] = []
    for outcome_label, outcome in outcomes.items():
        model = survey_wls(
            model_frame,
            outcome,
            predictors,
            "WTDR2D",
            "SDMVSTRA",
            "SDMVPSU",
            regression_domain,
        )
        for predictor in predictors:
            estimate = float(model.coefficients[predictor])
            standard_error = float(model.standard_errors[predictor])
            rows.append(
                {
                    "outcome": outcome_label,
                    "term": labels[predictor],
                    "estimate": estimate,
                    "standard_error": standard_error,
                    "lower_95": estimate - 1.96 * standard_error,
                    "upper_95": estimate + 1.96 * standard_error,
                    "unweighted_n": model.unweighted_n,
                }
            )
    return pd.DataFrame(rows)


def write_fiber_svg(estimates: pd.DataFrame) -> None:
    age = estimates.loc[
        (estimates["group_type"] == "Age group")
        & (estimates["measure"] == "Fiber (g per 1,000 kcal)")
    ].copy()
    age["group"] = pd.Categorical(
        age["group"], categories=["20-39", "40-59", "60+"], ordered=True
    )
    age = age.sort_values("group")
    width, height = 900, 470
    left, top, chart_width, chart_height = 110, 105, 720, 260
    maximum = max(18.0, float(age["upper_95"].max()) * 1.15)
    colors = ["#0f766e", "#2563eb", "#ea580c"]
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        '<text x="40" y="52" font-family="Arial, sans-serif" font-size="28" font-weight="700" fill="#0f172a">Survey-weighted fiber density by age group</text>',
        '<text x="40" y="82" font-family="Arial, sans-serif" font-size="16" fill="#475569">NHANES 2017–2018 adults; two-day dietary recall; 95% design-based confidence intervals</text>',
    ]
    for tick in range(0, int(maximum) + 1, 5):
        y = top + chart_height - (tick / maximum) * chart_height
        lines.extend(
            [
                f'<line x1="{left}" y1="{y:.1f}" x2="{left + chart_width}" y2="{y:.1f}" stroke="#cbd5e1" stroke-width="1"/>',
                f'<text x="{left - 18}" y="{y + 5:.1f}" text-anchor="end" font-family="Arial, sans-serif" font-size="14" fill="#475569">{tick}</text>',
            ]
        )
    bar_width = 120
    spacing = chart_width / len(age)
    for index, (_, row) in enumerate(age.iterrows()):
        center = left + spacing * (index + 0.5)
        bar_height = float(row["estimate"]) / maximum * chart_height
        y = top + chart_height - bar_height
        low_y = top + chart_height - float(row["lower_95"]) / maximum * chart_height
        high_y = top + chart_height - float(row["upper_95"]) / maximum * chart_height
        lines.extend(
            [
                f'<rect x="{center - bar_width / 2:.1f}" y="{y:.1f}" width="{bar_width}" height="{bar_height:.1f}" rx="6" fill="{colors[index]}"/>',
                f'<line x1="{center:.1f}" y1="{high_y:.1f}" x2="{center:.1f}" y2="{low_y:.1f}" stroke="#0f172a" stroke-width="3"/>',
                f'<line x1="{center - 12:.1f}" y1="{high_y:.1f}" x2="{center + 12:.1f}" y2="{high_y:.1f}" stroke="#0f172a" stroke-width="3"/>',
                f'<line x1="{center - 12:.1f}" y1="{low_y:.1f}" x2="{center + 12:.1f}" y2="{low_y:.1f}" stroke="#0f172a" stroke-width="3"/>',
                f'<text x="{center:.1f}" y="{y - 14:.1f}" text-anchor="middle" font-family="Arial, sans-serif" font-size="16" font-weight="700" fill="#0f172a">{row["estimate"]:.1f}</text>',
                f'<text x="{center:.1f}" y="{top + chart_height + 34:.1f}" text-anchor="middle" font-family="Arial, sans-serif" font-size="17" fill="#0f172a">{row["group"]}</text>',
            ]
        )
    lines.extend(
        [
            '<text x="22" y="240" transform="rotate(-90 22 240)" text-anchor="middle" font-family="Arial, sans-serif" font-size="15" fill="#475569">Grams per 1,000 kcal</text>',
            '<text x="450" y="445" text-anchor="middle" font-family="Arial, sans-serif" font-size="13" fill="#64748b">Source: CDC/NCHS NHANES 2017–2018 public-use files</text>',
            "</svg>",
        ]
    )
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    (ASSET_DIR / "fiber-density-by-age.svg").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )


def write_summary(
    estimates: pd.DataFrame,
    regressions: pd.DataFrame,
    flow: pd.DataFrame,
) -> None:
    def find_estimate(measure: str, group_type: str, group: str) -> pd.Series:
        return estimates.loc[
            (estimates["measure"] == measure)
            & (estimates["group_type"] == group_type)
            & (estimates["group"] == group)
        ].iloc[0]

    fiber = find_estimate(
        "Fiber (g per 1,000 kcal)", "Overall", "All adults"
    )
    sodium = find_estimate(
        "Sodium (mg per 1,000 kcal)", "Overall", "All adults"
    )
    analytic_n = int(
        flow.loc[
            flow["stage"] == "Complete energy, fiber, and sodium",
            "participants",
        ].iloc[0]
    )
    regression_n = int(
        flow.loc[
            flow["stage"]
            == "Complete income-to-poverty ratio for regression",
            "participants",
        ].iloc[0]
    )
    income_fiber = regressions.loc[
        (regressions["outcome"] == "Fiber (g per 1,000 kcal)")
        & (
            regressions["term"]
            == "Family income-to-poverty ratio (per unit)"
        )
    ].iloc[0]
    summary = f"""# Generated analysis summary

These estimates use NHANES 2017–2018 two-day dietary weights and Taylor-linearized standard errors.

- **Analytic cohort:** {analytic_n:,} adults contributed complete two-day energy, fiber, and sodium data; {regression_n:,} also had a reported family income-to-poverty ratio.
- **Fiber density:** {fiber["estimate"]:.2f} g per 1,000 kcal (95% CI {fiber["lower_95"]:.2f} to {fiber["upper_95"]:.2f}).
- **Sodium density:** {sodium["estimate"]:.1f} mg per 1,000 kcal (95% CI {sodium["lower_95"]:.1f} to {sodium["upper_95"]:.1f}).
- **Adjusted income association with fiber density:** {income_fiber["estimate"]:.2f} g per 1,000 kcal per one-unit increase in income-to-poverty ratio (95% CI {income_fiber["lower_95"]:.2f} to {income_fiber["upper_95"]:.2f}), adjusted for age group and sex.

The regression result is a descriptive cross-sectional association, not a causal effect. Two recalls do not recover long-term usual intake, and dietary measurement error remains.
"""
    (OUTPUT_DIR / "summary.md").write_text(
        summary, encoding="utf-8", newline="\n"
    )


def main() -> None:
    frame = build_analysis_frame()
    masks = eligibility_masks(frame)
    flow = cohort_flow(frame, masks)
    estimates = descriptive_estimates(frame, masks["analytic"])
    regressions = regression_estimates(frame, masks["regression"])

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    flow.to_csv(
        OUTPUT_DIR / "analytic_cohort_flow.csv",
        index=False,
        lineterminator="\n",
    )
    estimates.to_csv(
        OUTPUT_DIR / "nutrient_density_by_group.csv",
        index=False,
        float_format="%.4f",
        lineterminator="\n",
    )
    regressions.to_csv(
        OUTPUT_DIR / "regression_coefficients.csv",
        index=False,
        float_format="%.4f",
        lineterminator="\n",
    )
    write_fiber_svg(estimates)
    write_summary(estimates, regressions, flow)


if __name__ == "__main__":
    main()

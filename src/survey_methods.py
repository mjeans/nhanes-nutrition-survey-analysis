"""Small, inspectable design-based estimators for portfolio use."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Iterable

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SurveyEstimate:
    estimate: float
    standard_error: float
    lower_95: float
    upper_95: float
    unweighted_n: int
    effective_n: float


@dataclass(frozen=True)
class SurveyRegression:
    coefficients: pd.Series
    covariance: pd.DataFrame
    standard_errors: pd.Series
    unweighted_n: int


def _design_frame(
    data: pd.DataFrame,
    weight: str,
    strata: str,
    psu: str,
) -> pd.DataFrame:
    frame = data.copy()
    required = [weight, strata, psu]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise KeyError(f"Missing design columns: {', '.join(missing)}")
    mask = (
        frame[required].notna().all(axis=1)
        & np.isfinite(frame[weight])
        & (frame[weight] > 0)
    )
    frame = frame.loc[mask].copy()
    if frame.empty:
        raise ValueError("No positive-weight observations remain.")
    return frame


def _taylor_variance(
    frame: pd.DataFrame,
    linearized_columns: Iterable[str],
    strata: str,
    psu: str,
) -> np.ndarray:
    columns = list(linearized_columns)
    psu_totals = (
        frame.groupby([strata, psu], observed=True, sort=True)[columns]
        .sum()
        .reset_index()
    )
    variance = np.zeros((len(columns), len(columns)), dtype=float)
    usable_strata = 0
    for _, stratum in psu_totals.groupby(strata, observed=True, sort=True):
        values = stratum[columns].to_numpy(dtype=float)
        m_h = len(values)
        if m_h < 2:
            continue
        usable_strata += 1
        centered = values - values.mean(axis=0, keepdims=True)
        variance += (m_h / (m_h - 1.0)) * centered.T @ centered
    if usable_strata == 0:
        raise ValueError("At least one stratum with two PSUs is required.")
    return variance


def survey_mean(
    data: pd.DataFrame,
    outcome: str,
    weight: str,
    strata: str,
    psu: str,
    domain: pd.Series | None = None,
) -> SurveyEstimate:
    """Estimate a domain mean and Taylor-linearized standard error."""

    frame = _design_frame(data, weight, strata, psu)
    if outcome not in frame.columns:
        raise KeyError(f"Missing outcome column: {outcome}")

    eligible = frame[outcome].notna() & np.isfinite(frame[outcome])
    if domain is not None:
        eligible &= domain.reindex(frame.index, fill_value=False).astype(bool)

    effective_weight = frame[weight].where(eligible, 0.0)
    total_weight = float(effective_weight.sum())
    if total_weight <= 0:
        raise ValueError("The requested domain has no positive-weight observations.")

    outcome_values = frame[outcome].where(eligible, 0.0)
    estimate = float((effective_weight * outcome_values).sum() / total_weight)
    frame["_linearized"] = (
        effective_weight * (outcome_values - estimate) / total_weight
    )
    variance = float(
        _taylor_variance(frame, ["_linearized"], strata, psu)[0, 0]
    )
    standard_error = sqrt(max(variance, 0.0))
    domain_weights = effective_weight.loc[eligible]
    effective_n = float(
        domain_weights.sum() ** 2 / np.square(domain_weights).sum()
    )
    return SurveyEstimate(
        estimate=estimate,
        standard_error=standard_error,
        lower_95=estimate - 1.96 * standard_error,
        upper_95=estimate + 1.96 * standard_error,
        unweighted_n=int(eligible.sum()),
        effective_n=effective_n,
    )


def survey_wls(
    data: pd.DataFrame,
    outcome: str,
    predictors: list[str],
    weight: str,
    strata: str,
    psu: str,
    domain: pd.Series | None = None,
) -> SurveyRegression:
    """Fit survey-weighted least squares with linearized design covariance."""

    frame = _design_frame(data, weight, strata, psu)
    needed = [outcome, *predictors]
    missing = [column for column in needed if column not in frame.columns]
    if missing:
        raise KeyError(f"Missing model columns: {', '.join(missing)}")

    eligible = frame[needed].notna().all(axis=1)
    finite = np.isfinite(frame[needed].to_numpy(dtype=float)).all(axis=1)
    eligible &= pd.Series(finite, index=frame.index)
    if domain is not None:
        eligible &= domain.reindex(frame.index, fill_value=False).astype(bool)

    model = frame.loc[eligible]
    if len(model) <= len(predictors):
        raise ValueError("Not enough complete observations to fit the model.")
    x = model[predictors].to_numpy(dtype=float)
    y = model[outcome].to_numpy(dtype=float)
    w = model[weight].to_numpy(dtype=float)
    xtwx = x.T @ (w[:, None] * x)
    bread = np.linalg.pinv(xtwx)
    beta = bread @ (x.T @ (w * y))
    residual = y - x @ beta

    score_columns = [f"_score_{index}" for index in range(len(predictors))]
    for column in score_columns:
        frame[column] = 0.0
    frame.loc[eligible, score_columns] = w[:, None] * x * residual[:, None]
    score_variance = _taylor_variance(frame, score_columns, strata, psu)
    covariance = bread @ score_variance @ bread

    coefficients = pd.Series(beta, index=predictors, name="estimate")
    covariance_frame = pd.DataFrame(
        covariance, index=predictors, columns=predictors
    )
    standard_errors = pd.Series(
        np.sqrt(np.clip(np.diag(covariance), 0.0, None)),
        index=predictors,
        name="standard_error",
    )
    return SurveyRegression(
        coefficients=coefficients,
        covariance=covariance_frame,
        standard_errors=standard_errors,
        unweighted_n=int(eligible.sum()),
    )

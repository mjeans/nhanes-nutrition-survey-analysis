# Methods and limitations

## Target population and estimands

The target population is U.S. civilian noninstitutionalized adults aged 20 years or older represented by NHANES 2017–2018 participants with two reliable 24-hour dietary recalls and a positive two-day dietary weight. Participants identified as pregnant at the mobile examination are excluded because energy and nutrient requirements differ during pregnancy.

For each participant, day 1 and day 2 energy, dietary fiber, and sodium are averaged. Nutrient density is then defined as:

```text
fiber density = mean fiber grams / mean energy kcal × 1,000
sodium density = mean sodium milligrams / mean energy kcal × 1,000
```

The primary descriptive estimands are survey-weighted mean nutrient densities overall and within prespecified age and sex domains.

## Survey design

The analysis uses:

- `WTDR2D`, the two-day dietary sample weight;
- `SDMVSTRA`, the released masked stratum;
- `SDMVPSU`, the released masked primary sampling unit.

Weighted means are ratio estimators. Their standard errors use a with-replacement Taylor linearization based on PSU-level totals within strata. Domain membership enters through an indicator, so PSUs with eligible survey participants but no members of a given domain contribute a zero linearized total rather than disappearing from the design.

The effective sample size reported with descriptive estimates is the Kish weight-only quantity, `(sum w)^2 / sum(w^2)`. It is a descriptive diagnostic and does not replace the design-based standard error.

## Regression

Two survey-weighted linear regressions are fitted:

1. fiber density as the outcome;
2. sodium density as the outcome.

Predictors are age group (20–39 reference), sex (male reference), and continuous family income-to-poverty ratio. Coefficients are weighted least-squares associations. Covariance matrices use stratum- and PSU-level linearized estimating functions.

Regression is limited to complete records for the listed variables. The cohort-flow output exposes the number lost because family income-to-poverty ratio is missing. No imputation is performed because the purpose is to demonstrate a transparent reference analysis rather than claim a definitive population model.

## Interpretation

- NHANES 2017–2018 is cross-sectional; coefficients are not causal effects.
- Two recalls do not estimate the full distribution of usual intake.
- Dietary recalls can contain underreporting, overreporting, correlated error, and within-person variation.
- Nutrient density controls for total reported energy only through a ratio and does not remove all dietary measurement error.
- Public-use masked design variables support valid public analyses but do not reproduce every internal NCHS design feature.
- Normal 95% confidence intervals are used for compact portfolio reporting.
- Multiple comparisons are not adjusted; subgroup results are descriptive.

The implementation is intended to be inspectable and educational. A publication-quality analysis would prespecify a protocol, consider multi-cycle pooling, evaluate influential weights and sparse domains, assess missing-data assumptions, and use a validated usual-intake model where the research question requires it.

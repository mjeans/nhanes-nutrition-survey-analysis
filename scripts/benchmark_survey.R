# Regenerate the independent reference with R survey; no NHANES rows involved.
suppressPackageStartupMessages(library(survey))
options(survey.lonely.psu = "fail")
d <- read.csv("tests/fixtures/survey_fixture.csv")
results <- list()
for (case in c("all", "sparse_domain", "missing_predictor")) {
  current <- d
  if (case == "missing_predictor") current$x[1] <- NA_real_
  current$keep <- if (case == "sparse_domain") current$x >= 1 else TRUE
  design <- svydesign(ids = ~psu, strata = ~stratum, weights = ~weight,
                      nest = TRUE, data = current)
  domain <- subset(design, keep)
  mean_fit <- svymean(~outcome, domain)
  model <- svyglm(outcome ~ x, domain, family = gaussian())
  represented <- unique(current[current$keep, c("stratum", "psu")])
  mean_df <- nrow(represented) - length(unique(represented$stratum))
  model_rows <- current[current$keep & !is.na(current$x), ]
  represented_model <- unique(model_rows[c("stratum", "psu")])
  model_df <- nrow(represented_model) - length(unique(represented_model$stratum)) - model$rank + 1
  results[[case]] <- list(
    mean = unname(coef(mean_fit)[1]), se = unname(SE(mean_fit)[1]),
    mean_df = mean_df, lower_95 = unname(coef(mean_fit)[1] - qt(.975, mean_df)*SE(mean_fit)[1]),
    upper_95 = unname(coef(mean_fit)[1] + qt(.975, mean_df)*SE(mean_fit)[1]),
    coefficients = unname(coef(model)), covariance = unname(vcov(model)),
    residual_df = model_df)
}
jsonlite::write_json(list(reference = paste("R", getRversion(), "survey", packageVersion("survey")),
                          cases = results), "tests/fixtures/survey_reference.json",
                     auto_unbox = TRUE, pretty = TRUE, digits = 15)
cat("Rebuilt independent survey reference\n")

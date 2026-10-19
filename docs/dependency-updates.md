# Validating dependency updates

`requirements.txt` pins the analysis packages. A dependency update must also reproduce the public-data analysis before it is merged. Passing the unit tests alone is not sufficient.

## Reproduce the proposed environment

Check out the proposed update branch and use Python 3.12 in an isolated environment:

```bash
python -m venv .venv
```

Activate it with `source .venv/bin/activate` on macOS/Linux or `.venv\Scripts\Activate.ps1` in Windows PowerShell. Then run:

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python scripts/run_analysis.py
git diff -- outputs assets
```

The analysis verifies the CDC source-file checksums before using either downloaded or cached files. Do not change the source manifest simply to make a failed check pass; investigate the source separately. Keep raw participant-level files in the ignored `data/raw/` directory.

## Review the regenerated results

- **Runtime metadata only:** `outputs/report.md` records the versions actually used. A package update can change this line even when every estimate and figure is unchanged. Regenerate and commit that report with the dependency update; do not manually assert an environment that has not been run.
- **Numerical or graphical differences:** inspect cohort counts, domain estimates, standard errors, confidence intervals, regression coefficients, and sensitivity results. Compare against the independent R `survey` reference tests and investigate the reason for each change before accepting new outputs.
- **Test failures:** resolve the underlying incompatibility or defer the update. Do not remove the benchmark tests or weaken the output check just to obtain a passing workflow.

Commit the reviewed generated outputs with the update. Rerun the analysis and check that it produces no further tracked-file differences:

```bash
python scripts/run_analysis.py
git diff --exit-code
git status --short
```

The final commands assume that the reviewed changes have already been committed and the checkout was otherwise clean. CI performs the same strict tracked-file comparison; no blanket exception is made for reports or figures. Merge only after the pull request's tests, full analysis, and deterministic-output check pass.

Existing versioned releases remain unchanged when a dependency update is merged to `main`.

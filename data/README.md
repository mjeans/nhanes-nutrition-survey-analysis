# Data provenance and governance

The analysis downloads deidentified public-use files directly from the U.S. Centers for Disease Control and Prevention, National Center for Health Statistics:

| File | Purpose | Documentation |
|---|---|---|
| `DEMO_J.XPT` | Age, sex, pregnancy status, income-to-poverty ratio, masked strata, and masked PSUs | [CDC/NCHS](https://wwwn.cdc.gov/nchs/data/nhanes/public/2017/datafiles/DEMO_J.htm) |
| `DR1TOT_J.XPT` | Day 1 energy, fiber, sodium, recall status, and two-day dietary weight | [CDC/NCHS](https://wwwn.cdc.gov/nchs/data/nhanes/public/2017/datafiles/DR1TOT_J.htm) |
| `DR2TOT_J.XPT` | Day 2 energy, fiber, sodium, and recall status | [CDC/NCHS](https://wwwn.cdc.gov/nchs/data/nhanes/public/2017/datafiles/DR2TOT_J.htm) |

Raw XPT files are cached under `data/raw/` and excluded from Git. The repository contains only aggregate generated outputs. No attempt is made to identify participants or combine these data with restricted sources.

NHANES is a complex, multistage probability sample of the U.S. civilian noninstitutionalized population. The analysis therefore uses the released dietary sample weights and masked design variables rather than treating records as a simple random sample.

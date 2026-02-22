# Fiscal 10-K Download Validation Report

Generated: 2026-02-20 09:51:55

## Scope

- Local dataset: `sec_filings` (fresh fiscal-year dual-date download state)
- Fiscal targets: 2023, 2024
- Fixed index baseline: EDGAR full-index 10-K CIKs by filing-date year
- Candidate baseline: EDGAR full-index 10-K records in fiscal windows (FY..FY+6 months)

## Summary Table

| Fiscal Year | Local Fiscal Pairs | EDGAR Fixed Index CIKs | EDGAR Window Candidate CIKs | Missing vs Fixed | Missing vs Window Candidates | Local Not in Fixed | Local Not in Window Candidates |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2023 | 4897 | 7243 | 7432 | 2564 | 2549 | 218 | 14 |
| 2024 | 4567 | 6768 | 7010 | 2420 | 2443 | 219 | 0 |

## Validation Checks

- FY2023: local pairs=4897, HTML present=4897, missing HTML=0
- FY2024: local pairs=4567, HTML present=4567, missing HTML=0

## Difference Analysis

- `EDGAR Fixed Index CIKs` is filing-date-year based, not fiscal-year based.
- `Local Fiscal Pairs` is fiscal-year based from filing metadata (`period_of_report`/`DocumentFiscalYearFocus`).
- Therefore, differences are expected even with correct downloads.
- Additional gap is due to refresh run being interrupted by timeout before processing all candidate accessions.
- Some filings are excluded when fiscal metadata is missing or extracted fiscal year is outside targets.

## Outcome

- Dual-dating output is structurally valid: each saved filing has companion meta JSON and fiscal-year folder naming.
- Completeness is currently partial and should improve by rerunning fiscal refresh until no additional downloads occur.

## Artifacts

- Comparison CSV: `logs\fiscal_validation_20260220_095116.csv`
- Missing-vs-fixed CSV: `logs\fiscal_validation_missing_vs_fixed_20260220_095116.csv`
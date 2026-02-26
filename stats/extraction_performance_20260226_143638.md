# Extraction Performance Report

Generated: 2026-02-26 14:57:54
Source folder: `sec_filings`

## 1. Item Extraction Summary

| Year | Filings | TOC Found | TOC Missing | Any Items Extracted | Item JSON | Missing Item JSON | Structure JSON | Avg TOC Items | Avg TOC Anchors | Avg Extracted Items | Filings with Item Errors | Filings Missing Expected Items |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2022 | 5381 | 5248 | 133 | 5248 | 5248 | 133 | 5248 | 21.07 | 20.75 | 21.07 | 178 | 5239 |
| 2023 | 4881 | 4771 | 110 | 4771 | 4771 | 110 | 4771 | 21.95 | 21.66 | 21.95 | 155 | 2013 |
| 2024 | 4625 | 4531 | 94 | 4531 | 4531 | 94 | 4531 | 22.27 | 22.01 | 22.27 | 145 | 1247 |

## 2. Item Coverage and Lengths

Coverage is shown in two ways:
- `X out of Y (TOC)` where Y is filings with TOC found for that year+filing.
- `Coverage % (Total)` where denominator is all filings for that year+filing.

See CSV for per-item coverage and word-length stats:
- `logs\item_coverage_20260226_143638.csv`

## 3. Structure Extraction Summary

See CSV for per-item structure stats (headings/bodies/depth/ratios):
- `logs\structure_stats_20260226_143638.csv`

## 4. Extra Items (Outside Regulated Scope)

No extra items found.

## 5. Artifacts

- Year summary CSV: `logs\extraction_performance_20260226_143638.csv`
- Item coverage CSV: `logs\item_coverage_20260226_143638.csv`
- Structure stats CSV: `logs\structure_stats_20260226_143638.csv`

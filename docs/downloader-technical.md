# Downloader Technical Guide

This document explains how `script/downloader.py` works, why it is implemented this way, and what edge cases it handles.

## Purpose

Downloader fetches SEC filings from EDGAR and stores them in a fiscal-year-oriented folder structure.

It is designed for two use cases:
- Real download mode
- List-only validation mode (`--list-only`)

## Core Idea: Dual Dating

A filing has at least two important dates:
- Filing date (when it was filed to EDGAR)
- Report period / fiscal-year metadata (what year the report belongs to)

If you only use filing date year, fiscal-year analysis is biased. Many companies file year-end reports in the next calendar year.

Downloader solves this by:
1. Finding candidate records from EDGAR full index using filing-date windows.
2. Downloading candidate filing HTML.
3. Reading fiscal metadata in filing content.
4. Keeping only records whose fiscal year matches target `--year`.

## Input and Candidate Selection

### Inputs

- `--filing`: filing type code (`10k`, `10q`, etc.)
- `--year`: target fiscal years
- `--lookahead_months`: filing-date window extension (default 12)
- Optional company filters: `--ticker` or `--cik`

### Candidate pool

For each fiscal year `Y`, downloader considers filing-date windows from:
- `Y-01-01` to `Y + lookahead_months`

It loads full-index years required by those windows, deduplicates by accession, and filters records by date window and optional company filter.

## Fiscal-Year Validation

After downloading a candidate filing, downloader extracts:
- `dei:DocumentFiscalYearFocus`
- `dei:DocumentPeriodEndDate`

Rules:
- Prefer fiscal-year field when available.
- If missing, infer from period-end year.
- Keep the filing only if fiscal year is in target `--year`.

## Output Structure

```text
{output_dir}/{cik}/{fiscal_year}/{filing}/
  {cik}_{fiscal_year}_{filing}.htm|html
  {cik}_{fiscal_year}_{filing}_meta.json
```

Meta JSON includes source info, accession, filing date, period_of_report, and extracted DEI tags.

## Progress and Runtime Visibility

Downloader prints:
- Per-iteration result lines
- Running progress with elapsed / expected time / ETA

Per-iteration examples:
- `result=downloaded`
- `result=skipped_exists`
- `result=failed_download`
- `result=missing_fiscal_metadata`
- `result=skipped_outside_target_fy`

## Run Reports

### List-only mode

Generates:
- `logs/list_only_<form>_<timestamp>.csv`
- `stats/list_only_<form>_<timestamp>.md`

The markdown includes a note:
- `search filings looking ahead {lookahead_months} months`

### Download mode

Generates:
- `logs/download_run_<form>_<timestamp>.csv`
- `stats/download_run_<form>_<timestamp>.md`

Per-year metrics include:
- downloaded
- skipped_exists
- missing_fiscal_metadata
- failed_download
- skipped_outside_target_fy

## CIK-Ticker Mapping

Downloader updates annual mapping files for extractor filtering:
- `_meta/cik_ticker_map_edgar.csv`
- `_meta/cik_ticker_map.csv` (legacy-compatible)

Fields:
- fiscal_year
- cik
- ticker
- source
- updated_at

## Practical Considerations

### SEC request policy

EDGAR access should respect SEC rate guidance. In code, request pacing is controlled by:
- `script/config.py` `REQUEST_DELAY`
- `REQUEST_TIMEOUT`

`REQUEST_DELAY` controls request rate; timeout prevents hanging requests.

### Why list-only exists

For large runs, list-only mode lets you verify candidate volume and yearly counts before spending hours on downloads.

## Known Limitations

- Fiscal metadata is extracted from filing HTML. If not present/usable, those records are counted as missing metadata and not assigned to target fiscal year.
- EDGAR filings can have format variability; retries and boundary checks reduce, but do not eliminate, occasional failures.

## Typical Commands

Download:

```bash
python script/downloader.py --filing 10k --year 2023 2024 --output_dir sec_filings --user_agent "Org (email@domain.com)"
```

List-only:

```bash
python script/downloader.py --filing 10k --year 2023 2024 --output_dir sec_filings --list-only --user_agent "Org (email@domain.com)"
```

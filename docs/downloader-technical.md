# Downloader Technical Guide

This document explains how `script/downloader.py` works after the submission-text refactor.

## Purpose

Downloader fetches SEC submission `.txt` files from EDGAR and stores them in a fiscal-year-oriented folder structure.

It is designed for two use cases:
- real download mode
- list-only validation mode (`--list-only`)

## Core Idea: Filing Date Plus Report Period

A filing has two separate pieces of timing information:
- filing date: when EDGAR received the filing
- report period: which fiscal period the filing belongs to

The downloader now treats both as required checks:

1. use filing date to build the candidate pool through a configurable lookahead window
2. download the submission `.txt`
3. read `PERIOD OF REPORT` / `CONFORMED PERIOD OF REPORT` from the submission header
4. keep the filing only if:
   - the extracted fiscal year is in the requested `--year` set
   - the filing date also falls inside that extracted fiscal year's lookahead window

This prevents a filing from being accepted just because it was in a broad initial candidate window.

## Input and Candidate Selection

### Inputs

- `--filing`: filing type code (`10k`, `10q`, etc.)
- `--year`: target fiscal years
- `--lookahead_months`: filing-date window extension (default 12)
- optional company filters: `--ticker` or `--cik`

### Candidate pool

For each fiscal year `Y`, downloader considers filing-date windows from:
- `Y-01-01`
- through `Y + lookahead_months`

It loads the needed EDGAR full-index years, deduplicates by accession, and filters records by filing date and optional company filter.

## Submission Download Strategy

For each surviving candidate accession, downloader performs one EDGAR content request:

- download the submission text:
  - `.../{accession}.txt`

The submission `.txt` is the canonical artifact now. The downloader no longer fetches filing HTML first and no longer depends on iXBRL namespace tags for fiscal-year classification.

## Report-Period Extraction

Fiscal-year validation is driven by the submission header line:

- `CONFORMED PERIOD OF REPORT: YYYYMMDD`
- `PERIOD OF REPORT: YYYYMMDD`

The matcher is intentionally permissive about separators and small label variations, so it can catch forms such as:

- `CONFORMED PERIOD OF REPORT`
- `PERIOD OF REPORT`
- `CONFORMED_PERIOD_OF_REPORT`
- `PERIOD-OF-REPORT`

If no usable report-period header is found, the filing is counted as `missing_fiscal_metadata`.

## Output Structure

```text
{output_dir}/{cik}/{fiscal_year}/{filing}/
  {cik}_{fiscal_year}_{filing}.txt
  {cik}_{fiscal_year}_{filing}_meta.json
```

Meta JSON includes:
- source info
- accession number
- filing date
- `period_of_report`
- `tags_found`
- ticker symbols found in the submission text

## Progress and Runtime Visibility

Downloader prints:
- per-iteration result lines
- running progress with elapsed time / expected total / ETA

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

Downloader updates:
- `_meta/cik_ticker_map_edgar.csv`
- `_meta/cik_ticker_map.csv` (legacy-compatible)

Fields:
- fiscal_year
- cik
- ticker
- source
- updated_at

## Practical Considerations

### Why the submission `.txt` is the canonical download

The EDGAR full index already points to the submission text path. Using that file:
- reduces SEC requests compared with detail-page then HTML download flow
- keeps the SEC header and all attached documents together
- lets the extractor later choose the primary filing HTML from the saved submission container

### SEC request policy

EDGAR access pacing is still controlled by:
- `script/config.py` `REQUEST_DELAY`
- `REQUEST_TIMEOUT`

## Known Limitations

- Fiscal-year assignment now depends on report-period header availability in the submission text. If the header is absent or malformed, the filing is not assigned.
- The downloader does not inspect document narrative text or iXBRL date tags as fallback anymore.

## Typical Commands

Download:

```bash
python script/downloader.py --filing 10k --year 2023 2024 --output_dir sec_filings --user_agent "Org (email@domain.com)"
```

List-only:

```bash
python script/downloader.py --filing 10k --year 2023 2024 --output_dir sec_filings --list-only --user_agent "Org (email@domain.com)"
```

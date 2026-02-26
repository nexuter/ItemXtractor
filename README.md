# ItemXtractor

EDGAR-based pipeline to:
- download SEC filings by fiscal-year windows
- extract filing items using TOC-driven boundaries
- optionally extract heading/body structure from extracted items

Current architecture is split by step:
- `script/downloader.py`: download only
- `script/extractor.py`: extraction only
- `script/stat.py`: stats/reporting utilities

## What This Project Does

1. Download filings from EDGAR with dual-date logic.
2. Save filings under fiscal-year folders.
3. Extract item-level content from downloaded filings.
4. Extract structured heading/body sections from item outputs.

## Folder Layout

Downloaded filings are stored as:

```text
{output_dir}/{cik}/{fiscal_year}/{filing}/
  {cik}_{fiscal_year}_{filing}.htm|html
  {cik}_{fiscal_year}_{filing}_meta.json
```

Item extraction output is saved next to each filing:

```text
{cik}_{fiscal_year}_{filing}_item.json
{cik}_{fiscal_year}_{filing}_str.json
```

## Install

```bash
pip install -r requirements.txt
```

## Downloader

`script/downloader.py` is EDGAR-only.

```text
usage: downloader.py [-h] [--ticker TICKERS [TICKERS ...] | --cik CIKS [CIKS ...]]
                     --filing FILING
                     --year YEARS [YEARS ...]
                     --output_dir OUTPUT_DIR
                     [--lookahead_month LOOKAHEAD_MONTHS]
                     [--overwrite]
                     [--list-only]
                     --user_agent USER_AGENT
```

### Key behavior

- `--year` means fiscal year target(s), not filing-date year.
- Downloader searches EDGAR index records in fiscal-year windows using `filing_date`.
- It validates fiscal year from filing metadata (for example `DocumentFiscalYearFocus` / `DocumentPeriodEndDate`).
- If `--list-only` is used, no filings are downloaded; only list/report outputs are generated.

### Examples

Download 10-K fiscal years 2023 and 2024:

```bash
python script/downloader.py --filing 10k --year 2023 2024 --output_dir sec_filings --user_agent "Your Org (email@domain.com)"
```

List-only dry run (no download):

```bash
python script/downloader.py --filing 10k --year 2023 2024 --output_dir sec_filings --list-only --user_agent "Your Org (email@domain.com)"
```

### Downloader outputs

- Mapping tables:
  - `sec_filings/_meta/cik_ticker_map_edgar.csv`
  - `sec_filings/_meta/cik_ticker_map.csv` (legacy-compatible)
- List-only reports:
  - `logs/list_only_<form>_<timestamp>.csv`
  - `stats/list_only_<form>_<timestamp>.md`
- Download-run reports:
  - `logs/download_run_<form>_<timestamp>.csv`
  - `stats/download_run_<form>_<timestamp>.md`

## Extractor

`script/extractor.py` processes already-downloaded filings.

```text
usage: extractor.py [-h]
                    [--ticker TICKERS [TICKERS ...]]
                    [--cik CIKS [CIKS ...]]
                    [--filing FILING]
                    [--year YEARS [YEARS ...]]
                    --filing_dir FILING_DIR
                    --task {item,structure}
                    [--overwrite]
                    [--progress_every PROGRESS_EVERY]
```

### Examples

Extract items for all CIKs under `sec_filings`:

```bash
python script/extractor.py --filing_dir sec_filings --filing 10-K --task item
```

Extract structures from existing item outputs:

```bash
python script/extractor.py --filing_dir sec_filings --filing 10-K --task structure
```

Year filter:

```bash
python script/extractor.py --filing_dir sec_filings --filing 10-K --year 2024 --task item
```

Filter by CIK/ticker:

```bash
python script/extractor.py --filing_dir sec_filings --filing 10-K --task item --cik 0000001750
python script/extractor.py --filing_dir sec_filings --filing 10-K --task item --ticker AAPL
```

Show frequent progress updates with elapsed/ETA:

```bash
python script/extractor.py --filing_dir sec_filings --filing 10-K --task item --overwrite --progress_every 25
```

## Notes

- Item extraction is TOC-driven. If TOC is not detected, extraction for that filing is skipped.
- Extraction only keeps regulated item scope from `script/config.py`.
- Existing output files are skipped unless `--overwrite` is set.
- `--task structure` reuses existing `*_item.json`. It only runs item extraction first if `*_item.json` is missing.
- Combined TOC rows like `Items 1 and 2` are supported. When both map to one section anchor, item boundaries are aligned so Item 1 and Item 2 represent the same combined section.
- Terminal marker rule: cut when `None.` / `Not applicable.` appears first after item title; do not cut when it appears later in item text.

## Stats / Reporting

`script/stat.py` generates per-year markdown reports (no CSV outputs).

Outputs:
- `stats/extraction_stat_<year>_<timestamp>.md`

Run:

```bash
python script/stat.py --folder sec_filings
python script/stat.py --folder sec_filings --year 2024
```

Each report includes:
- Yearly TOC/item coverage stats
- Per-item coverage and length stats (avg/min/max word count)
- Structure stats (headings/bodies/depth/ratios)
- Filings with item errors (and error detail)
- Filings missing expected items (with missing list)
- Filings missing TOC (CIK list)

## Validation

Boundary-focused validator:

```bash
python tests/validate_extraction.py --filing_dir sec_filings --filing 10-K --year 2024 --limit 20
```

This compares extracted `text_content` against source HTML segments using first/last word windows and writes:
- `logs/extraction_validation_<timestamp>.csv`
- `stats/extraction_validation_<timestamp>.md`

## Technical Docs

- `docs/downloader-technical.md`
- `docs/extractor-technical.md`

These docs explain implementation details, decision logic, and resolved edge cases in plain language.

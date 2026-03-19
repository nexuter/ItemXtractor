# ItemXtractor

EDGAR-based pipeline to:
- download SEC submission `.txt` files by fiscal-year windows
- extract filing items from the primary HTML document embedded in each submission
- optionally extract heading/body structure from extracted items

Current architecture is split by step:
- `script/downloader.py`: download only
- `script/extractor.py`: extraction only
- `script/stat.py`: stats/reporting utilities

## What This Project Does

1. Pull candidate filings from EDGAR full index using filing-date windows.
2. Download the SEC submission `.txt` for each candidate accession.
3. Read `PERIOD OF REPORT` from the submission header to identify the filing fiscal year.
4. Keep only filings whose fiscal year is requested and whose filing date fits that fiscal year's lookahead window.
5. During extraction, parse `<DOCUMENT>` blocks inside the saved submission `.txt`, choose the primary filing HTML, backfill ticker info only when iXBRL `dei:TradingSymbol` is present, and run TOC-driven item/structure extraction.

## Folder Layout

Downloaded filings are stored as:

```text
{output_dir}/{cik}/{fiscal_year}/{filing}/
  {cik}_{fiscal_year}_{filing}.txt
  {cik}_{fiscal_year}_{filing}_meta.json
```

Extraction output is saved next to each submission:

```text
{cik}_{fiscal_year}_{filing}_item.json
{cik}_{fiscal_year}_{filing}_str.json
```

Optional extractor artifacts:

```text
{cik}_{fiscal_year}_{filing}.html
{cik}_{fiscal_year}_{filing}_images/
  {item}_{index}.{ext}
```

Extractor-managed ticker map:

```text
{output_dir}/_meta/cik_ticker_map.csv
```

## Install

```bash
pip install -r requirements.txt
```

## Downloader

`script/downloader.py` is EDGAR-only.

```text
usage: downloader.py [-h] [--cik CIKS [CIKS ...]]
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
- Candidate records come from EDGAR full index, filtered by filing date using the requested lookahead window.
- Final acceptance uses both:
  - `PERIOD OF REPORT` / `CONFORMED PERIOD OF REPORT` parsed from the submission `.txt`
  - filing-date window validation for the extracted fiscal year
- If `--list-only` is used, no filings are downloaded; only list/report outputs are generated.
- If the submission text does not expose a recognizable report-period header, the filing is counted as `missing_fiscal_metadata`.

### Examples

Download 10-K fiscal years 2023 and 2024:

```bash
python script/downloader.py --filing 10k --year 2023 2024 --output_dir sec_filings --user_agent "Your Org (email@domain.com)"
```

List-only dry run:

```bash
python script/downloader.py --filing 10k --year 2023 2024 --output_dir sec_filings --list-only --user_agent "Your Org (email@domain.com)"
```

### Downloader outputs

- List-only reports:
  - `logs/list_only_<form>_<timestamp>.csv`
  - `stats/list_only_<form>_<timestamp>.md`
- Download-run reports:
  - `logs/download_run_<form>_<timestamp>.csv`
  - `stats/download_run_<form>_<timestamp>.md`

## Extractor

`script/extractor.py` processes already-downloaded submission `.txt` files.

```text
usage: extractor.py [-h]
                    [--cik CIKS [CIKS ...]]
                    [--filing FILING]
                    [--year YEARS [YEARS ...]]
                    --filing_dir FILING_DIR
                    --task {item,structure}
                    [--overwrite]
                    [--html]
                    [--image]
                    [--progress_every PROGRESS_EVERY]
```

### Examples

Extract items for all 10-K submissions under `sec_filings`:

```bash
python script/extractor.py --filing_dir sec_filings --filing 10-K --task item
```

Extract structures and save the primary filing HTML beside each submission:

```bash
python script/extractor.py --filing_dir sec_filings --filing 10-K --task structure --html
```

Save item images resolved from submission documents:

```bash
python script/extractor.py --filing_dir sec_filings --filing 10-Q --task item --image
```

### Notes

- The extractor parses SEC `<DOCUMENT>` blocks and selects the main filing HTML from the submission container.
- Ticker mapping is extractor-owned. It only backfills `cik_ticker_map.csv` and `ticker_symbols` in filing metadata when `dei:TradingSymbol` exists in the selected filing HTML.
- Non-iXBRL filings are skipped for ticker extraction.
- TOC detection is still required. If no TOC is found, extraction for that filing is skipped.
- Extraction only keeps regulated item scope from `script/config.py`.
- Existing output files are skipped unless `--overwrite` is set.
- `--task structure` reuses existing `*_item.json` when possible.
- 10-Q scope now includes both Part I and Part II items. To avoid collisions, 10-Q item keys are part-qualified:
  - `I_1`, `I_2`, `I_3`, `I_4`
  - `II_1`, `II_1A`, `II_2`, `II_3`, `II_4`, `II_5`, `II_6`

## Stats / Reporting

`script/stat.py` generates per-year markdown reports.

Outputs:
- `stats/extraction_stat_<year>_<timestamp>.md`
- `stats/extraction_stat_overall_<timestamp>.md`

Run:

```bash
python script/stat.py --folder sec_filings
python script/stat.py --folder sec_filings --year 2024
```

The report now includes ticker coverage:
- how many filings have at least one ticker in `*_meta.json`
- yearly ticker percentage across all filings in scope

## Validation

Boundary-focused validator:

```bash
python tests/validate_extraction.py --filing_dir sec_filings --filing 10-K --year 2024 --limit 20
```

This compares extracted `text_content` against source HTML segments and writes:
- `logs/extraction_validation_<timestamp>.csv`
- `stats/extraction_validation_<timestamp>.md`

## Technical Docs

- `docs/downloader-technical.md`
- `docs/item-extraction-technical.md`
- `docs/structure-extraction-technical.md`

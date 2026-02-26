# Extractor Technical Guide

This document explains how `script/extractor.py` and extraction modules work, including design choices and edge cases resolved during validation.

## Purpose

Extractor reads downloaded filing HTML and produces:
- Item-level outputs (`*_item.json`)
- Optional structure outputs (`*_str.json`)

It does not download filings.

## Why TOC-Driven Extraction

SEC filings vary in formatting. Item headings can appear as:
- `Item 1. Business`
- `ITEM 1 BUSINESS`
- `1. Business`
- compact inline-XBRL variants

Using only plain text heading regex across the whole filing creates many boundary errors.

Extractor uses TOC as the primary anchor source because:
- TOC is the most reliable index of official item boundaries in most 10-K filings.
- TOC links/anchors usually map to exact HTML positions.
- It avoids false starts from repeated headings elsewhere.

## High-Level Flow

1. Load filing HTML.
2. Parse TOC.
3. Keep in-scope regulated items from `script/config.py`.
4. Compute item start/end positions.
5. Extract item HTML and text.
6. Save JSON.
7. If `--task structure`, parse heading/body hierarchy from item HTML.

When task is `structure`:
- If `*_item.json` exists, extractor reuses it.
- If missing, extractor creates `*_item.json` first, then builds `*_str.json`.

## TOC Parsing Strategy

Parser combines multiple methods:
- TOC table parsing
- TOC link parsing (important for inline-XBRL formats)
- guarded structural fallback

Important behavior:
- TOC is still required for extraction.
- Parser first uses explicit TOC marker regions, and can also recover TOC from beginning-region tables/links when marker text is missing but TOC structure is clear.
- Link-based parsing can recover anchors when table rows are non-standard.
- Anchored entries are not overwritten by weaker unanchored rows.

## Item Boundary Strategy

Primary boundary logic:
- Start at current item anchor (or fallback heading when anchor missing).
- End at next item anchor.
- If next anchor is missing, use next item heading fallback within bounded range.
- Preserve TOC appearance order for boundaries (not only numeric item sort), which is critical for combined rows like `Items 1 and 2`.
- If adjacent TOC items share the same anchor, they are treated as one combined section boundary; both items end at the next distinct item.

This prevents item spillover to filing end.

## Text Normalization Strategy

Extractor applies generic cleanup rules to avoid overfitting a single filing:
- remove zero-width/control artifacts
- normalize smart quotes and dash variants to ASCII where applicable
- remove line artifacts like standalone `Table of Contents` headers
- remove page markers
- keep valid numeric tokens that are part of real content

## Terminal-Statement Trimming

Current policy (simple and deterministic):
- Cut when `Not applicable.` or `None.` appears first after the item title.
- Do not cut when `Not applicable.` or `None.` appears later in the item text.

This keeps behavior predictable across many filings and avoids case-by-case overfitting.

## Real Cases Found and Resolved

### Case 1: TOC exists but parser skipped filing

Example pattern:
- TOC rendered as index-style links in header/compact row format.

Fix:
- Added/strengthened link-based TOC parsing and anchor merge behavior.

### Case 2: PART rows with item in same row

Example rows:
- `PART I. 1. Business ...`
- `PART II. 5. Market ...`
- `PART III. 10. Directors ...`

Fix:
- TOC row parsing now supports multi-item patterns and part-prefixed rows.

### Case 3: Missing anchors for some items caused drops

Symptoms:
- Items like `1`, `7`, `9` missing.

Fix:
- Do not require anchor at selection stage.
- Use heading-based fallback start/end detection for missing-anchor items.

### Case 4: Item spillover to filing end

Symptoms:
- `1B` or `9A` contains signatures/exhibits and everything to end.

Fix:
- End-boundary fallback uses next heading candidates when next anchor missing.

### Case 5: Noise in text content

Symptoms:
- Unicode artifacts (`\u200b`, smart quotes), bullets, page numbers, TOC fragments.

Fix:
- Generic normalization and artifact filtering in text extraction pipeline.

### Case 6: Terminal statements and trailing junk

Symptoms:
- `Item 16 ... Not applicable. 94 ...`
- `Item 16 ... None. 125 ... INDEX TO EXHIBITS ...`

Fix:
- Apply first-marker rule (`None.` / `Not applicable.`) and trim at marker when it appears first after item heading.
- Preserve text when marker appears later (for example `None of ...` in the middle).

### Case 7: Combined rows (`Items 1 and 2`) and boundary mismatch

Symptoms:
- One filing captured both item numbers, another captured only item `2`.
- Item `2` could spill into following sections (`1A`, `1B`, `1C`) when boundaries were computed in numeric order.

Fix:
- TOC number parsing explicitly supports plural combined rows (`Items X and Y`).
- Boundary computation uses TOC appearance order.
- Same-anchor sibling items are grouped for boundary purposes so Item 1 and Item 2 are aligned to the same section range.

## Output Format

### Item JSON

Contains:
- filing identity metadata
- parsed TOC entries used for extraction
- extracted item map
  - `item_number`
  - `item_title`
  - `html_content`
  - `text_content`

### Structure JSON

Contains hierarchical heading/body blocks parsed from item HTML.

### Stats / Reporting

`script/stat.py` scans a filings folder and generates per-year markdown reports:
- Yearly TOC/item coverage stats
- Per-item length stats (avg/min/max word count)
- Structure stats (avg/min/max headings, bodies, depth, and heading/body ratio)
- Filings with item errors and per-item error detail
- Filings missing expected items
- Filings missing TOC (CIK list)

Artifacts:
- `stats/extraction_stat_<year>_<timestamp>.md`

## Command Usage

Item extraction:

```bash
python script/extractor.py --filing_dir sec_filings --filing 10-K --task item --overwrite
```

Structure extraction:

```bash
python script/extractor.py --filing_dir sec_filings --filing 10-K --task structure --overwrite
```

Company filter:

```bash
python script/extractor.py --filing_dir sec_filings --filing 10-K --task item --cik 0000003499
```

Year filter:

```bash
python script/extractor.py --filing_dir sec_filings --filing 10-K --year 2024 --task item
```

Progress frequency:

```bash
python script/extractor.py --filing_dir sec_filings --filing 10-K --task item --progress_every 25
```

## Validation Workflow

Boundary-focused validation script:

```bash
python tests/validate_extraction.py --filing_dir sec_filings --filing 10-K --year 2024 --limit 1000
```

Outputs:
- `logs/extraction_validation_<timestamp>.csv`
- `stats/extraction_validation_<timestamp>.md`

Validation compares extracted text boundaries to source HTML segments using first/last token windows with normalization and ordered/overlap matching to reduce layout-based false positives.

## What Extractor Does Not Do

- It does not download filings.
- It does not infer items without TOC policy approval.
- It does not force a global title template; each filing TOC/title style is preserved.

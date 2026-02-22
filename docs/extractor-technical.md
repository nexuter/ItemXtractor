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

## TOC Parsing Strategy

Parser combines multiple methods:
- TOC table parsing
- TOC link parsing (important for inline-XBRL formats)
- guarded structural fallback

Important behavior:
- Explicit TOC markers are required to proceed.
- Link-based parsing can recover anchors when table rows are non-standard.
- Anchored entries are not overwritten by weaker unanchored rows.

## Item Boundary Strategy

Primary boundary logic:
- Start at current item anchor (or fallback heading when anchor missing).
- End at next item anchor.
- If next anchor is missing, use next item heading fallback within bounded range.

This prevents item spillover to filing end.

## Text Normalization Strategy

Extractor applies generic cleanup rules to avoid overfitting a single filing:
- remove zero-width/control artifacts
- normalize smart quotes and dash variants to ASCII where applicable
- remove line artifacts like standalone `Table of Contents` headers
- remove page markers
- keep valid numeric tokens that are part of real content

## Terminal-Statement Trimming

For items whose valid content is effectively empty, extractor trims early when terminal statements appear near the beginning:
- `Not applicable...`
- `None...`

This avoids accidental inclusion of trailing page/footer/index sections.

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

### Case 6: Terminal statements with trailing junk

Symptoms:
- `Item 16 ... Not applicable. 94 ...`
- `Item 16 ... None. 125 ... INDEX TO EXHIBITS ...`

Fix:
- Early terminal trimming after item heading context.

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

## What Extractor Does Not Do

- It does not download filings.
- It does not infer items without TOC policy approval.
- It does not force a global title template; each filing TOC/title style is preserved.

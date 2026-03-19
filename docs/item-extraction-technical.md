# Item Extraction Technical Guide

This document explains how item extraction works in the submission-text pipeline.

## Purpose

Item extraction reads a saved SEC submission `.txt`, selects the primary filing HTML from its `<DOCUMENT>` blocks, and outputs:
- `*_item.json` containing item HTML + text
- optional saved filing HTML (`--html`)
- optional extracted item images (`--image`)

It does not download filings.

## High-Level Flow

1. Load submission `.txt`
2. Parse SEC `<DOCUMENT>` blocks
3. Choose the primary filing HTML document
4. Parse TOC from that HTML
5. Keep in-scope items from `script/config.py`
6. Compute item boundaries
7. Extract item HTML + text
8. Save `{cik}_{year}_{filing}_item.json`

## Why TOC-Driven Extraction Still Matters

Even though the pipeline now starts from submission text instead of standalone filing HTML, the actual item extraction step still works on the filing HTML document itself.

SEC filings vary in item heading formats:
- `Item 1. Business`
- `ITEM 1 BUSINESS`
- `1. Business`
- compact inline XBRL variants

TOC anchors remain the most reliable boundary signals when present.

## Submission Parsing Strategy

The extractor parses each submission `.txt` into document blocks using:
- `<DOCUMENT>`
- `<TYPE>`
- `<SEQUENCE>`
- `<FILENAME>`
- `<DESCRIPTION>`
- `<TEXT>`

The main filing HTML is selected by scoring document candidates using:
- form match (`10-K`, `10-Q`, etc.)
- sequence number
- HTML-like filename
- HTML-like payload content

## TOC Parsing Strategy

Parser combines multiple methods:
- TOC table parsing
- TOC link parsing
- guarded structural fallback

Rules:
- TOC is required. If no TOC is found, extraction is skipped.
- anchored entries are not overwritten by weaker unanchored rows
- TOC appearance order is preserved

## 10-Q Part-Aware Keys

10-Q filings reuse item numbers across Part I and Part II, so plain item keys would collide.

The extractor now uses part-qualified keys:
- `I_1`, `I_2`, `I_3`, `I_4`
- `II_1`, `II_1A`, `II_2`, `II_3`, `II_4`, `II_5`, `II_6`

The parser assigns these keys during TOC parsing and normalizes missing part context where possible.

## Item Boundary Strategy

Primary boundary logic:
- start at current item anchor, or fallback heading if anchor is missing
- end at next item anchor
- if next anchor is missing, use next item heading fallback within a bounded range
- same-anchor siblings such as `Items 1 and 2` share the same boundary

## Text Normalization Strategy

Generic cleanup:
- remove zero-width/control artifacts
- normalize smart quotes and dash variants
- remove page markers
- drop TOC fragments and `Table of Contents` lines

Terminal marker trimming:
- cut when `Not applicable.` or `None.` appears first after item title
- do not cut when it appears later in the item text

## Optional HTML Saving

If `--html` is provided, the extractor writes the selected primary filing HTML beside the submission text:

```text
{cik}_{fiscal_year}_{filing}.html
```

This is useful for debugging selection quality and validating extracted boundaries.

## Optional Image Saving

If `--image` is provided, the extractor:
- scans `<img>` tags found in extracted item HTML
- resolves image references against other submission `<DOCUMENT>` blocks
- saves decodable payloads under:

```text
{cik}_{fiscal_year}_{filing}_images/
  {item}_{index}.{ext}
```

Supported cases include:
- `data:` URIs
- uuencoded payloads
- base64-like payloads
- plain text fallback when the image document is not binary-encoded

## Output Format

`*_item.json` includes:
- filing identity metadata
- selected TOC entries
- saved image count
- extracted item map:
  - `item_number`
  - `item_title`
  - `html_content`
  - `text_content`

## Command Usage

Extract items:

```bash
python script/extractor.py --filing_dir sec_filings --filing 10-K --task item --overwrite
```

Extract items and save HTML:

```bash
python script/extractor.py --filing_dir sec_filings --filing 10-K --task item --html
```

Extract 10-Q items and save images:

```bash
python script/extractor.py --filing_dir sec_filings --filing 10-Q --task item --image
```

## What Item Extraction Does Not Do

- It does not download filings.
- It does not classify fiscal year from document narrative.
- It does not keep every submission attachment; it only selects the primary filing HTML plus optional image payloads needed by extracted items.

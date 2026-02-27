# Item Extraction Technical Guide

This document explains how item extraction works and why the pipeline uses TOC‑driven boundaries.

## Purpose

Item extraction reads filing HTML and outputs:
- `*_item.json` containing item HTML + text
- TOC entries used for boundary selection

It does not download filings.

## Why TOC‑Driven Extraction

SEC filings vary in item heading formats:
- `Item 1. Business`
- `ITEM 1 BUSINESS`
- `1. Business`
- compact inline‑XBRL variants

Parsing headings across the entire document causes boundary errors. TOC anchors are the most stable and reliable item boundary references when present.

## High‑Level Flow

1. Load filing HTML
2. Parse TOC
3. Keep in‑scope items from `script/config.py`
4. Compute item boundaries
5. Extract item HTML + text
6. Save `{cik}_{year}_{filing}_item.json`

## TOC Parsing Strategy

Parser combines multiple methods:
- TOC table parsing
- TOC link parsing (important for inline‑XBRL formats)
- guarded structural fallback

Rules:
- TOC is required. If no TOC is found, extraction is skipped.
- Anchored entries are not overwritten by weaker unanchored rows.
- TOC appearance order is preserved (do not sort by item number).

### Example: TOC Link Recovery

Some filings use index‑style links without a clear `Table of Contents` header. Link parsing recovers anchors from `<a href="#ITEM1">` and similar links.

## Item Boundary Strategy

Primary boundary logic:
- Start at current item anchor (or fallback heading if anchor missing).
- End at next item anchor.
- If next anchor is missing, use next item heading fallback within a bounded range.
- Same‑anchor siblings (e.g., `Items 1 and 2`) share the same boundary.

### Example: Combined Rows

TOC row:
```
Items 1 and 2 … [same anchor]
```

Boundary result:
- Item 1 and Item 2 use the same HTML span
- Both end at the next distinct item anchor

## Text Normalization Strategy

Generic cleanup:
- remove zero‑width/control artifacts
- normalize smart quotes and dash variants
- remove page markers
- drop TOC fragments and `Table of Contents` lines
- keep valid numeric tokens that are part of real content

## Terminal Marker Trimming

Deterministic rule:
- Cut when `Not applicable.` or `None.` appears first after item title.
- Do not cut when it appears later in the item text.

### Example

```
Item 16. Form 10‑K Summary
Not applicable. 94
```

Trimmed to:
```
Item 16. Form 10‑K Summary
Not applicable.
```

## Real Cases Found and Resolved

### Case 1: TOC exists but parser skipped filing

Pattern: index‑style TOC links in header or compact rows  
Fix: stronger link parsing + anchor merge behavior

### Case 2: PART rows with item in same row

Pattern:
`PART I. 1. Business ...`  
Fix: parse multi‑item rows and part‑prefixed rows

### Case 3: Missing anchors for some items

Fix: allow selection without anchor and fallback to heading‑based boundaries

### Case 4: Item spillover to filing end

Fix: end‑boundary fallback uses next heading candidates when next anchor missing

### Case 5: Combined `Items 1 and 2`

Fix: same‑anchor items share boundaries; order preserved

## Output Format

`*_item.json` includes:
- filing identity metadata
- parsed TOC entries used for extraction
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

Year scope:

```bash
python script/extractor.py --filing_dir sec_filings --filing 10-K --year 2024 --task item
```

## What Item Extraction Does Not Do

- It does not download filings.
- It does not infer items without TOC policy approval.
- It does not force a global title template.

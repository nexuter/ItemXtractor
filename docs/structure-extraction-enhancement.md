# Structure Extraction Enhancement Summary

## Overview
Structure extraction builds hierarchical heading/body trees from each item’s HTML.

## Current Behavior

### 1. **Hierarchical Detection**
- Headings are detected using multiple signals (bold/italic/underline/center, title‑case, item tokens).
- Level assignment is heuristic and allows deeper nesting when style indicates hierarchy.
- TOC‑derived item title becomes the layer‑1 root when available.

### 2. **Smart Structure Building**
The algorithm:
1. Collects block elements in document order
2. Classifies headings vs body using style + text heuristics
3. Builds a nested tree using a stack
4. Attaches body text to the nearest active heading

### 3. **Noise Filtering**
The extractor filters common non‑content lines:
- `Table of Contents`
- `PART I/II/III/IV`
- `TABLE 2.1:` style labels
- page numbers

### 4. **Split Bold Lead‑ins**
Some paragraphs begin with a bold phrase followed by normal text:
- Example: `Contracts. In March 2023, ...`
These are split into a heading (`Contracts`) and a body (rest of sentence).

### 5. **Bullet‑Only Bold**
Bulleted lines often have a bold bullet but normal text. These are treated as body, not headings.

## Usage

Extract structures from already extracted items:
```bash
python script/extractor.py --filing_dir sec_filings --filing 10-K --task structure
```

Outputs:
```
{cik}_{year}_{filing}_str.json
```

## Notes
- Structure depth is typically 2–3 in most filings.
- Output quality depends on the item HTML and styling consistency.

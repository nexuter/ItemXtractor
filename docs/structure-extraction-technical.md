# Structure Extraction Technical Guide

This document explains how structure extraction builds heading/body hierarchies from extracted item HTML.

## Purpose

Structure extraction reads `*_item.json` and outputs:
- `*_str.json` containing hierarchical heading/body trees

If item output is missing, the extractor first loads the submission `.txt`, reconstructs the primary filing HTML, and generates `*_item.json`.

## High-Level Flow

1. Load `*_item.json`, or build it from the submission `.txt`
2. Read each item's HTML
3. Collect candidate blocks (`h1..h6`, `p`, `li`, `div`, `table`)
4. Classify heading vs body using style and text heuristics
5. Build a nested structure using a stack
6. Attach body text to the nearest active heading

## Heading Detection Rules

Signals used:
- bold / italic / underline / center styles
- title-case shape
- explicit item-token headings

### 1. Item Root

When item title is known from the TOC, it becomes the layer-1 root.

### 2. Title-Case Headings

Long bold headings in title case are treated as layer-2.

### 3. Sentence-Style Headings

Bold sentences ending with `.` are treated as deeper headings when they read like lead-ins.

### 4. Bold Lead-Ins in Paragraphs

Paragraphs that start with a bold phrase followed by normal text are split into:
- heading
- body

### 5. Bullet-Only Bold

If only the bullet glyph is bold and the following text is not, the block is treated as body rather than heading.

## Noise Filtering

Filtered as non-content headings:
- `Table of Contents`
- `PART I/II/III/IV`
- `TABLE 2.1:` style labels
- page numbers

## Body Assignment

Body text is assigned to the nearest active heading on the stack. If a heading has no body before another heading starts, body remains `null`.

## Output Format

`*_str.json` contains:
- `type` (`heading`, `simple_text`)
- `layer` (depth)
- `heading`
- `body`
- `children`

## Relationship to the New Submission Pipeline

The structure extractor itself still works from item HTML, but that item HTML now originates from:
- submission `.txt`
- selected filing `<DOCUMENT>`
- TOC-based item extraction

So the end structure output is still item-centric, while the input artifact is now the saved submission container rather than a downloaded standalone filing HTML file.

## Command Usage

```bash
python script/extractor.py --filing_dir sec_filings --filing 10-K --task structure --overwrite
```

Save the reconstructed filing HTML during structure extraction:

```bash
python script/extractor.py --filing_dir sec_filings --filing 10-K --task structure --html
```

## Known Limitations

- depth is limited by detectable style differences
- tables are treated conservatively to avoid false headings
- if item extraction cannot find a TOC, structure extraction for that filing is skipped as well

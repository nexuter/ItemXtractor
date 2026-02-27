# Structure Extraction Technical Guide

This document explains how structure extraction builds heading/body hierarchies from item HTML.

## Purpose

Structure extraction reads `*_item.json` and outputs:
- `*_str.json` containing hierarchical heading/body trees

## High‑Level Flow

1. Load item HTML for each extracted item
2. Collect candidate blocks (`h1..h6`, `p`, `li`, `div`, `table`)
3. Classify heading vs body using style and text heuristics
4. Build a nested structure using a stack
5. Attach body text to the nearest active heading

## Heading Detection Rules

Signals used:
- bold/italic/underline/center styles
- title‑case shape
- explicit item tokens (`Item 1`, `Item 1A`, …)

### 1. Item Root

When item title is known (from TOC), it becomes layer‑1 root.

Example:
```
Item 7. Management's Discussion and Analysis ...
```

### 2. Title‑Case Headings

Long bold headings in title‑case are treated as layer‑2:
```
Privacy, Data Protection, Data Management, Artificial Intelligence, Resiliency, Information Security and Cybersecurity
```

### 3. Sentence‑Style Headings

Bold sentences ending with `.` are treated as layer‑3:
```
We are subject to significant government regulation...
```

### 4. Bold Lead‑Ins in Paragraphs

Paragraphs that start with a bold phrase followed by normal text are split:

```
Contracts. In March 2023, ...
```

Becomes:
- heading: `Contracts`
- body: `In March 2023, ...`

This also supports the case where the period is a separate span.

### 5. Bullet‑Only Bold

If only the bullet is bold (`•`) and text is normal weight, the line is treated as body (not heading).

## Noise Filtering

Filtered as non‑content headings:
- `Table of Contents`
- `PART I/II/III/IV`
- `TABLE 2.1:` style labels
- page numbers

## Body Assignment

Body text is assigned to the nearest heading on the stack. If a heading has no body before another heading starts, body remains `null`.

## Output Format

`*_str.json` contains:
- `type` (`heading`, `simple_text`)
- `layer` (depth)
- `heading`
- `body`
- `children`

## Examples

### Example A: Simple Nested Structure

```
Item 1. Business
  Business Segments
    Parts Supply
    Repair & Engineering
```

### Example B: Lead‑In Split

```
Talent Development. Equipping our people with the skills ...
```

Produces:
- heading: `Talent Development`
- body: `Equipping our people ...`

## Command Usage

```bash
python script/extractor.py --filing_dir sec_filings --filing 10-K --task structure --overwrite
```

If `*_item.json` is missing, item extraction runs first.

## Known Limitations

- Depth is limited by detectable style differences.
- Tables are treated as plain text to avoid false headings.

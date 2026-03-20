# Image Extraction Technical Guide

This document explains how optional image extraction works during `script/extractor.py` runs.

## Purpose

Image extraction saves filing images that appear inside extracted item HTML.

It is optional and only runs when `--image` is provided.

Outputs are stored beside the filing submission as:

```text
{cik}_{fiscal_year}_{filing}_images/
  {item}_{index}.{ext}
```

## When It Runs

Image extraction is part of the item-extraction flow:

1. load submission `.txt`
2. parse `<DOCUMENT>` blocks
3. select the primary filing HTML
4. extract in-scope items
5. inspect extracted item HTML for `<img>` tags
6. resolve and save matching image payloads

If item extraction is skipped, image extraction does not run.

## Source of Image Data

Filing HTML can reference images in several ways:

- embedded `data:` URIs
- relative file paths that point to other submission `<DOCUMENT>` blocks
- alternate encoded payloads stored inside the submission container

The extractor does not fetch images from the network one by one. It resolves them from the already-saved submission `.txt` and its parsed `<DOCUMENT>` attachments.

## Resolution Strategy

For each `<img>` tag found in extracted item HTML, the extractor:

1. reads the image `src`
2. normalizes the reference
3. tries to match it to a parsed submission document
4. decodes the payload when possible
5. writes the image to disk using an item-scoped filename

This keeps image extraction deterministic and tied to the same submission artifact used for text extraction.

## Naming Convention

Saved image filenames use:

- `{item}`: extracted item key such as `1`, `1A`, `I_1`, `II_6`
- `{index}`: appearance order within that item
- `{ext}`: original or inferred file extension

Examples:

- `1_1.png`
- `1A_2.jpg`
- `II_1_3.gif`

## Supported Payload Types

The extractor currently handles several common SEC attachment patterns:

- `data:` URIs embedded directly in HTML
- uuencoded image payloads
- base64-like payloads
- plain-text document payloads that can be written directly when already decoded

If decoding fails, that image is skipped rather than stopping the full filing extraction.

## Scope Rules

Only images referenced inside extracted item HTML are saved.

This means:

- not every attachment in the submission is exported
- exhibits that are never referenced by extracted items are ignored
- saved images are scoped to the regulated item content we actually keep

## Relationship to HTML Saving

`--html` and `--image` are independent:

- `--html` saves the selected primary filing HTML
- `--image` saves referenced image payloads from extracted items

They can be used together or separately.

## Typical Commands

Save item images for 10-K filings:

```bash
python script/extractor.py --filing_dir sec_filings --filing 10-K --task item --image
```

Save both filing HTML and item images:

```bash
python script/extractor.py --filing_dir sec_filings --filing 10-Q --task item --html --image
```

## Known Limitations

- Images are only saved for successfully extracted items.
- Broken or non-decodable image references are skipped.
- Non-item attachments are not exported just because they exist in the submission.

"""
Extraction-only pipeline.

Reads downloaded SEC submission .txt files from filing_dir and performs:
- item extraction -> *_item.json
- structure extraction -> *_str.json
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from script.config import ITEMS_10K, ITEMS_10Q
from src.extractor import ItemExtractor
from src.parser import SECParser
from src.structure_extractor import StructureExtractor
from src.submission_parser import (
    build_document_lookup,
    resolve_image_document,
    select_primary_html_document,
    parse_submission_documents,
)


ITEM_SCOPE_BY_FILING = {
    "10-K": set(ITEMS_10K.keys()),
    "10-KA": set(ITEMS_10K.keys()),
    "10-Q": set(ITEMS_10Q.keys()),
    "10-QA": set(ITEMS_10Q.keys()),
}

_PART_ORDER = {"I": 1, "II": 2, "III": 3, "IV": 4}


def _item_sort_key(item_num: str) -> tuple[int, int, str]:
    token = (item_num or "").strip().upper()
    part_rank = 0
    bare = token
    match = re.match(r"^([IVX]+)_(\d+[A-Z]?)$", token)
    if match:
        part_rank = _PART_ORDER.get(match.group(1), 99)
        bare = match.group(2)

    i = 0
    while i < len(bare) and bare[i].isdigit():
        i += 1
    if i == 0:
        return (part_rank, 9999, bare)
    return (part_rank, int(bare[:i]), bare[i:])


def _load_cik_ticker_map(map_path: Path) -> Dict[str, set[str]]:
    out: Dict[str, set[str]] = {}
    if not map_path.exists():
        return out
    with map_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            ticker = str(r.get("ticker", "")).strip().upper()
            cik = str(r.get("cik", "")).strip().zfill(10)
            if not ticker or not cik:
                continue
            out.setdefault(ticker, set()).add(cik)
    return out


def _resolve_ciks_from_args(
    filing_dir: Path,
    tickers: Optional[List[str]],
    ciks: Optional[List[str]],
) -> set[str]:
    target_ciks: set[str] = set()
    for c in ciks or []:
        token = c.strip()
        if token:
            target_ciks.add(token.zfill(10))

    if tickers:
        source_map = filing_dir / "_meta" / "cik_ticker_map_edgar.csv"
        legacy_map = filing_dir / "_meta" / "cik_ticker_map.csv"
        ticker_map = _load_cik_ticker_map(source_map)
        if not ticker_map and legacy_map.exists():
            ticker_map = _load_cik_ticker_map(legacy_map)
        for t in tickers:
            sym = t.strip().upper()
            if not sym:
                continue
            target_ciks.update(ticker_map.get(sym, set()))
    return target_ciks


def _list_filing_files(
    filing_dir: Path,
    target_ciks: set[str],
    filing_filter: Optional[str],
    year_filter: Optional[set[str]],
) -> List[Path]:
    submission_files: List[Path] = []

    if target_ciks:
        cik_dirs = [filing_dir / t for t in sorted(target_ciks)]
    else:
        cik_dirs = [p for p in filing_dir.iterdir() if p.is_dir()]

    for cik_dir in cik_dirs:
        if not cik_dir.exists() or not cik_dir.is_dir():
            continue
        for year_dir in cik_dir.iterdir():
            if not year_dir.is_dir():
                continue
            if year_filter and year_dir.name not in year_filter:
                continue
            for form_dir in year_dir.iterdir():
                if not form_dir.is_dir():
                    continue
                if filing_filter and form_dir.name.upper() != filing_filter.upper():
                    continue
                for f in form_dir.iterdir():
                    if f.is_file() and f.suffix.lower() == ".txt":
                        submission_files.append(f)
    submission_files.sort()
    return submission_files


def _parse_path_parts(path: Path, filing_dir: Path) -> Dict[str, str]:
    rel = path.relative_to(filing_dir)
    parts = rel.parts
    cik = parts[0] if len(parts) >= 1 else ""
    year = parts[1] if len(parts) >= 2 else ""
    filing = parts[2] if len(parts) >= 3 else ""
    return {"cik": cik, "year": year, "filing": filing}


def _load_submission_context(txt_path: Path, filing_dir: Path) -> Optional[Dict[str, object]]:
    meta = _parse_path_parts(txt_path, filing_dir)
    filing_type = meta["filing"].upper()
    submission_text = txt_path.read_text(encoding="utf-8", errors="ignore")
    documents = parse_submission_documents(submission_text)
    main_doc = select_primary_html_document(documents, filing_type)
    if not main_doc or not (main_doc.text or "").strip():
        return None
    document_lookup = build_document_lookup(documents)
    return {
        "meta": meta,
        "submission_text": submission_text,
        "documents": documents,
        "document_lookup": document_lookup,
        "main_document": main_doc,
        "html_content": main_doc.text,
    }


def _save_extracted_html(
    txt_path: Path,
    html_content: str,
    overwrite: bool,
) -> Path:
    html_path = txt_path.with_suffix(".html")
    if overwrite or not html_path.exists():
        html_path.write_text(html_content, encoding="utf-8")
    return html_path


def _save_item_images(
    *,
    txt_path: Path,
    extracted: Dict[str, Dict[str, object]],
    document_lookup: Dict[str, object],
    overwrite: bool,
) -> int:
    image_root = txt_path.with_name(f"{txt_path.stem}_images")
    saved = 0

    for item_num, item_data in extracted.items():
        if not isinstance(item_data, dict):
            continue
        item_html = item_data.get("html_content")
        if not isinstance(item_html, str) or not item_html.strip():
            continue

        soup = BeautifulSoup(item_html, "html.parser")
        seen_srcs = set()
        image_index = 1
        for img in soup.find_all("img"):
            src = (img.get("src") or "").strip()
            if not src or src in seen_srcs:
                continue
            seen_srcs.add(src)
            payload, ext = resolve_image_document(src, document_lookup)
            if payload is None:
                continue
            image_root.mkdir(parents=True, exist_ok=True)
            safe_item = re.sub(r"[^A-Za-z0-9]+", "_", item_num).strip("_") or "item"
            extension = ext if ext.startswith(".") else f".{ext}" if ext else ""
            out_path = image_root / f"{safe_item}_{image_index}{extension}"
            if overwrite or not out_path.exists():
                out_path.write_bytes(payload)
            saved += 1
            image_index += 1

    return saved


def _extract_items_for_file(
    *,
    txt_path: Path,
    filing_dir: Path,
    parser: SECParser,
    item_extractor: ItemExtractor,
    overwrite: bool,
    save_html: bool,
    save_images: bool,
) -> Optional[Path]:
    base_name = txt_path.stem
    item_out = txt_path.with_name(f"{base_name}_item.json")
    context = _load_submission_context(txt_path, filing_dir)
    if context is None:
        return None

    html_content = str(context["html_content"])
    if save_html:
        _save_extracted_html(txt_path, html_content, overwrite)

    meta = context["meta"]
    filing_type = str(meta["filing"]).upper()
    toc_items = parser.parse_toc(html_content, filing_type)
    if not toc_items:
        return None

    in_scope = ITEM_SCOPE_BY_FILING.get(filing_type)
    if in_scope:
        selected = {k: v for k, v in toc_items.items() if k in in_scope}
    else:
        selected = dict(toc_items)
    if not selected:
        return None

    extracted = {}
    for item_num in sorted(selected.keys(), key=_item_sort_key):
        try:
            extracted[item_num] = item_extractor.extract_item(html_content, item_num, selected)
        except Exception as e:
            extracted[item_num] = {"error": str(e)}

    saved_images = 0
    if save_images:
        saved_images = _save_item_images(
            txt_path=txt_path,
            extracted=extracted,
            document_lookup=context["document_lookup"],
            overwrite=overwrite,
        )

    out = {
        "cik": meta["cik"],
        "year": meta["year"],
        "filing": meta["filing"],
        "source_file": txt_path.name,
        "source_document": getattr(context["main_document"], "filename", ""),
        "toc_items": selected,
        "saved_images": saved_images,
        "items": extracted,
    }
    if overwrite or not item_out.exists():
        item_out.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return item_out


def _extract_structure_for_file(
    *,
    txt_path: Path,
    filing_dir: Path,
    parser: SECParser,
    item_extractor: ItemExtractor,
    structure_extractor: StructureExtractor,
    overwrite: bool,
    save_html: bool,
    save_images: bool,
) -> Optional[Path]:
    base_name = txt_path.stem
    str_out = txt_path.with_name(f"{base_name}_str.json")

    context = _load_submission_context(txt_path, filing_dir)
    if context is None:
        return None
    if save_html:
        _save_extracted_html(txt_path, str(context["html_content"]), overwrite)

    item_out = txt_path.with_name(f"{base_name}_item.json")
    item_payload = None
    if item_out.exists() and not overwrite:
        try:
            item_payload = json.loads(item_out.read_text(encoding="utf-8"))
        except Exception:
            item_payload = None

    if item_payload is None:
        item_path = _extract_items_for_file(
            txt_path=txt_path,
            filing_dir=filing_dir,
            parser=parser,
            item_extractor=item_extractor,
            overwrite=overwrite,
            save_html=save_html,
            save_images=save_images,
        )
        if not item_path or not item_path.exists():
            return None
        item_payload = json.loads(item_path.read_text(encoding="utf-8"))
    elif save_images:
        _save_item_images(
            txt_path=txt_path,
            extracted=item_payload.get("items", {}),
            document_lookup=context["document_lookup"],
            overwrite=overwrite,
        )

    structures = {}
    for item_num, item_data in item_payload.get("items", {}).items():
        if not isinstance(item_data, dict):
            continue
        if "html_content" not in item_data:
            continue
        try:
            structures[item_num] = structure_extractor.extract_structure(
                item_data["html_content"],
                root_heading=item_data.get("item_title"),
            )
        except Exception as e:
            structures[item_num] = {"error": str(e)}

    out = {
        "cik": item_payload.get("cik"),
        "year": item_payload.get("year"),
        "filing": item_payload.get("filing"),
        "source_file": item_payload.get("source_file"),
        "source_document": item_payload.get("source_document"),
        "structures": structures,
    }
    if overwrite or not str_out.exists():
        str_out.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return str_out


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract items or structures from downloaded SEC submission text files.")
    parser.add_argument("--ticker", nargs="+", dest="tickers", default=None, help="Ticker symbol filter(s).")
    parser.add_argument("--cik", nargs="+", dest="ciks", default=None, help="CIK folder filter(s).")
    parser.add_argument("--filing", default=None, help="Filing folder filter (e.g., 10-K).")
    parser.add_argument("--year", nargs="+", dest="years", default=None, help="Year folder filter(s), e.g. 2023 2024.")
    parser.add_argument("--filing_dir", required=True, help="Root folder where filings are stored.")
    parser.add_argument("--task", required=True, choices=["item", "structure"], help="Extraction task.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite extraction outputs.")
    parser.add_argument("--html", action="store_true", help="Save the extracted main filing HTML beside each submission .txt.")
    parser.add_argument("--image", action="store_true", help="Save item images resolved from submission documents.")
    parser.add_argument(
        "--progress_every",
        type=int,
        default=25,
        help="Print progress every N filings (default: 25).",
    )
    args = parser.parse_args()

    filing_dir = Path(args.filing_dir)
    if not filing_dir.exists() or not filing_dir.is_dir():
        raise FileNotFoundError(f"filing_dir not found: {filing_dir}")

    sec_parser = SECParser()
    item_extractor = ItemExtractor()
    structure_extractor = StructureExtractor()

    target_ciks = _resolve_ciks_from_args(filing_dir, args.tickers, args.ciks)
    year_filter = {str(y).strip() for y in (args.years or []) if str(y).strip()}
    if args.tickers and not target_ciks and not args.ciks:
        print(
            "No CIK match found for provided ticker(s) in "
            "filing_dir/_meta/cik_ticker_map_edgar.csv"
        )

    submission_files = _list_filing_files(
        filing_dir,
        target_ciks,
        args.filing,
        year_filter if year_filter else None,
    )
    print(f"Found filings: {len(submission_files)}")

    done = 0
    skipped = 0
    started_at = time.time()
    total = len(submission_files)
    for i, txt_file in enumerate(submission_files, start=1):
        if args.task == "item":
            out = _extract_items_for_file(
                txt_path=txt_file,
                filing_dir=filing_dir,
                parser=sec_parser,
                item_extractor=item_extractor,
                overwrite=args.overwrite,
                save_html=args.html,
                save_images=args.image,
            )
        else:
            out = _extract_structure_for_file(
                txt_path=txt_file,
                filing_dir=filing_dir,
                parser=sec_parser,
                item_extractor=item_extractor,
                structure_extractor=structure_extractor,
                overwrite=args.overwrite,
                save_html=args.html,
                save_images=args.image,
            )
        if out:
            done += 1
        else:
            skipped += 1

        if total > 0 and (i == 1 or i % max(args.progress_every, 1) == 0 or i == total):
            elapsed = time.time() - started_at
            rate = i / elapsed if elapsed > 0 else 0.0
            remaining = (total - i) / rate if rate > 0 else 0.0
            print(
                f"Progress {i}/{total} ({(i/total)*100:.1f}%) "
                f"done={done} skipped={skipped} "
                f"elapsed={elapsed/60:.1f}m eta={remaining/60:.1f}m",
                flush=True,
            )

    print(f"Completed. done={done} skipped={skipped}")


if __name__ == "__main__":
    main()

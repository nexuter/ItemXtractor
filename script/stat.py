"""
Extraction performance report generator for current pipeline layout.

Scans filing folders:
  {cik}/{year}/{filing}/{cik}_{year}_{filing}.htm|html
  {cik}_{year}_{filing}_item.json
  {cik}_{year}_{filing}_str.json
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from script.config import ITEMS_10K, ITEMS_10Q


EXPECTED_ITEMS_BY_FILING: Dict[str, Set[str]] = {
    "10-K": set(ITEMS_10K.keys()),
    "10-KA": set(ITEMS_10K.keys()),
    "10-Q": set(ITEMS_10Q.keys()),
    "10-QA": set(ITEMS_10Q.keys()),
}


def _safe_int_year(text: str) -> Optional[int]:
    return int(text) if text.isdigit() else None


def _word_count(text: str) -> int:
    return len([w for w in re.split(r"\s+", (text or "").strip()) if w])


def _walk_structure(nodes: List[dict]) -> Tuple[int, int, int]:
    """
    Return (heading_count, body_count, max_depth).
    max_depth is the max layer value encountered for heading nodes.
    """
    heading_count = 0
    body_count = 0
    max_depth = 0
    stack = list(nodes or [])
    while stack:
        node = stack.pop()
        if node.get("type") == "heading":
            heading_count += 1
            max_depth = max(max_depth, int(node.get("layer") or 0))
        if (node.get("body") or "").strip():
            body_count += 1
        stack.extend(node.get("children") or [])
    return heading_count, body_count, max_depth


def _iter_filing_htmls(root: Path):
    # root/{cik}/{year}/{filing}/{base}.htm|html
    for cik_dir in root.iterdir():
        if not cik_dir.is_dir() or not cik_dir.name.isdigit():
            continue
        cik = cik_dir.name
        for year_dir in cik_dir.iterdir():
            if not year_dir.is_dir():
                continue
            year = _safe_int_year(year_dir.name)
            if year is None:
                continue
            for filing_dir in year_dir.iterdir():
                if not filing_dir.is_dir():
                    continue
                filing = filing_dir.name.upper()
                for html_path in filing_dir.iterdir():
                    if html_path.is_file() and html_path.suffix.lower() in {".htm", ".html"}:
                        yield cik, year, filing, html_path


def _load_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return None


def build_report(folder: Path) -> Tuple[Path, Path, Path, Path]:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    logs_dir = Path("logs")
    stats_dir = Path("stats")
    logs_dir.mkdir(parents=True, exist_ok=True)
    stats_dir.mkdir(parents=True, exist_ok=True)

    year_stats = defaultdict(lambda: {
        "filings_total": 0,
        "filings_toc_found": 0,
        "filings_toc_missing": 0,
        "filings_with_any_extracted_items": 0,
        "item_json_present": 0,
        "item_json_missing": 0,
        "str_json_present": 0,
        "toc_items_sum": 0,
        "toc_anchors_sum": 0,
        "extracted_items_sum": 0,
        "filings_with_item_errors": 0,
        "filings_missing_expected_items": 0,
    })

    # (year, filing, item) -> count of filings where item was extracted
    item_coverage = defaultdict(int)
    # (year, filing, item) -> [count, sum_words, min_words, max_words]
    item_lengths = defaultdict(lambda: [0, 0, None, None])
    # (year, filing) -> filings count
    filing_counts = defaultdict(int)
    # (year, filing) -> filings where TOC was found (proxy: item json exists)
    filing_toc_found_counts = defaultdict(int)

    # Track extra items (outside expected set)
    extra_items = defaultdict(set)  # (year, filing) -> set[item]

    # Structure stats per item
    # (year, filing, item) -> dict of aggregations
    structure_stats = defaultdict(lambda: {
        "count": 0,
        "head_sum": 0,
        "head_min": None,
        "head_max": None,
        "body_sum": 0,
        "body_min": None,
        "body_max": None,
        "depth_sum": 0,
        "depth_min": None,
        "depth_max": None,
        "ratio_sum": 0.0,
        "ratio_min": None,
        "ratio_max": None,
    })

    html_list = list(_iter_filing_htmls(folder))
    total_html = len(html_list)
    for idx, (cik, year, filing, html_path) in enumerate(html_list, start=1):
        y = year_stats[year]
        y["filings_total"] += 1
        filing_counts[(year, filing)] += 1

        base = html_path.stem
        item_path = html_path.with_name(f"{base}_item.json")
        str_path = html_path.with_name(f"{base}_str.json")

        if str_path.exists():
            y["str_json_present"] += 1

        item_payload = _load_json(item_path)
        if not item_payload:
            y["item_json_missing"] += 1
            y["filings_toc_missing"] += 1
            continue

        y["item_json_present"] += 1
        y["filings_toc_found"] += 1
        filing_toc_found_counts[(year, filing)] += 1

        toc_items = item_payload.get("toc_items", {}) or {}
        items = item_payload.get("items", {}) or {}

        y["toc_items_sum"] += len(toc_items)
        y["toc_anchors_sum"] += sum(1 for v in toc_items.values() if isinstance(v, dict) and v.get("anchor"))
        y["extracted_items_sum"] += len(items)

        had_error = any(isinstance(v, dict) and "error" in v for v in items.values())
        if had_error:
            y["filings_with_item_errors"] += 1

        expected = EXPECTED_ITEMS_BY_FILING.get(filing, set())
        extracted_item_nums = {k for k in items.keys()}
        if extracted_item_nums:
            y["filings_with_any_extracted_items"] += 1

        if expected:
            missing_expected = expected - extracted_item_nums
            if missing_expected:
                y["filings_missing_expected_items"] += 1

        for item_num in extracted_item_nums:
            item_coverage[(year, filing, item_num)] += 1
            text_content = (items.get(item_num) or {}).get("text_content") or ""
            words = _word_count(text_content)
            agg = item_lengths[(year, filing, item_num)]
            agg[0] += 1
            agg[1] += words
            agg[2] = words if agg[2] is None else min(agg[2], words)
            agg[3] = words if agg[3] is None else max(agg[3], words)
            if expected and item_num not in expected:
                extra_items[(year, filing)].add(item_num)

        str_payload = _load_json(str_path)
        if str_payload:
            structures = (str_payload.get("structures") or {})
            for item_num, nodes in structures.items():
                head_cnt, body_cnt, depth = _walk_structure(nodes or [])
                ratio = (head_cnt / body_cnt) if body_cnt else float("inf")
                s = structure_stats[(year, filing, item_num)]
                s["count"] += 1
                s["head_sum"] += head_cnt
                s["head_min"] = head_cnt if s["head_min"] is None else min(s["head_min"], head_cnt)
                s["head_max"] = head_cnt if s["head_max"] is None else max(s["head_max"], head_cnt)
                s["body_sum"] += body_cnt
                s["body_min"] = body_cnt if s["body_min"] is None else min(s["body_min"], body_cnt)
                s["body_max"] = body_cnt if s["body_max"] is None else max(s["body_max"], body_cnt)
                s["depth_sum"] += depth
                s["depth_min"] = depth if s["depth_min"] is None else min(s["depth_min"], depth)
                s["depth_max"] = depth if s["depth_max"] is None else max(s["depth_max"], depth)
                s["ratio_sum"] += ratio if ratio != float("inf") else 0.0
                if ratio != float("inf"):
                    s["ratio_min"] = ratio if s["ratio_min"] is None else min(s["ratio_min"], ratio)
                    s["ratio_max"] = ratio if s["ratio_max"] is None else max(s["ratio_max"], ratio)

        if idx % 100 == 0 or idx == total_html:
            pct = (idx / total_html * 100.0) if total_html else 100.0
            print(f"[stat] processed {idx}/{total_html} filings ({pct:.1f}%)")

    # Year summary CSV
    year_csv = logs_dir / f"extraction_performance_{stamp}.csv"
    with year_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "year",
                "filings_total",
                "filings_toc_found",
                "filings_toc_missing",
                "filings_with_any_extracted_items",
                "item_json_present",
                "item_json_missing",
                "str_json_present",
                "avg_toc_items",
                "avg_toc_anchors",
                "avg_extracted_items",
                "filings_with_item_errors",
                "filings_missing_expected_items",
            ],
        )
        w.writeheader()
        for year in sorted(year_stats.keys()):
            y = year_stats[year]
            denom = max(y["item_json_present"], 1)
            w.writerow(
                {
                    "year": year,
                    "filings_total": y["filings_total"],
                    "filings_toc_found": y["filings_toc_found"],
                    "filings_toc_missing": y["filings_toc_missing"],
                    "filings_with_any_extracted_items": y["filings_with_any_extracted_items"],
                    "item_json_present": y["item_json_present"],
                    "item_json_missing": y["item_json_missing"],
                    "str_json_present": y["str_json_present"],
                    "avg_toc_items": round(y["toc_items_sum"] / denom, 2),
                    "avg_toc_anchors": round(y["toc_anchors_sum"] / denom, 2),
                    "avg_extracted_items": round(y["extracted_items_sum"] / denom, 2),
                    "filings_with_item_errors": y["filings_with_item_errors"],
                    "filings_missing_expected_items": y["filings_missing_expected_items"],
                }
            )

    # Item coverage CSV (with lengths)
    item_csv = logs_dir / f"item_coverage_{stamp}.csv"
    with item_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "year",
                "filing",
                "item",
                "filings_with_item",
                "filings_total",
                "filings_toc_found",
                "x_out_of_y",
                "coverage_pct_total",
                "coverage_pct_toc_found",
                "avg_words",
                "min_words",
                "max_words",
            ],
        )
        w.writeheader()
        for (year, filing, item), count in sorted(item_coverage.items(), key=lambda x: (x[0][0], x[0][1], x[0][2])):
            total = filing_counts.get((year, filing), 0)
            toc_found = filing_toc_found_counts.get((year, filing), 0)
            pct_total = (count / total * 100.0) if total else 0.0
            pct_toc = (count / toc_found * 100.0) if toc_found else 0.0
            agg = item_lengths[(year, filing, item)]
            avg_words = round(agg[1] / max(agg[0], 1), 2)
            w.writerow(
                {
                    "year": year,
                    "filing": filing,
                    "item": item,
                    "filings_with_item": count,
                    "filings_total": total,
                    "filings_toc_found": toc_found,
                    "x_out_of_y": f"{count}/{toc_found}",
                    "coverage_pct_total": round(pct_total, 2),
                    "coverage_pct_toc_found": round(pct_toc, 2),
                    "avg_words": avg_words,
                    "min_words": agg[2] or 0,
                    "max_words": agg[3] or 0,
                }
            )

    # Structure stats CSV
    structure_csv = logs_dir / f"structure_stats_{stamp}.csv"
    with structure_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "year",
                "filing",
                "item",
                "filings_with_structure",
                "avg_headings",
                "min_headings",
                "max_headings",
                "avg_bodies",
                "min_bodies",
                "max_bodies",
                "avg_depth",
                "min_depth",
                "max_depth",
                "avg_heading_body_ratio",
                "min_heading_body_ratio",
                "max_heading_body_ratio",
            ],
        )
        w.writeheader()
        for (year, filing, item), s in sorted(structure_stats.items()):
            count = max(s["count"], 1)
            w.writerow(
                {
                    "year": year,
                    "filing": filing,
                    "item": item,
                    "filings_with_structure": s["count"],
                    "avg_headings": round(s["head_sum"] / count, 2),
                    "min_headings": s["head_min"] or 0,
                    "max_headings": s["head_max"] or 0,
                    "avg_bodies": round(s["body_sum"] / count, 2),
                    "min_bodies": s["body_min"] or 0,
                    "max_bodies": s["body_max"] or 0,
                    "avg_depth": round(s["depth_sum"] / count, 2),
                    "min_depth": s["depth_min"] or 0,
                    "max_depth": s["depth_max"] or 0,
                    "avg_heading_body_ratio": round(s["ratio_sum"] / count, 2) if s["count"] else 0.0,
                    "min_heading_body_ratio": round(s["ratio_min"], 2) if s["ratio_min"] is not None else 0.0,
                    "max_heading_body_ratio": round(s["ratio_max"], 2) if s["ratio_max"] is not None else 0.0,
                }
            )

    # Markdown report
    md_path = stats_dir / f"extraction_performance_{stamp}.md"
    lines: List[str] = []
    lines.append("# Extraction Performance Report")
    lines.append("")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Source folder: `{folder}`")
    lines.append("")

    lines.append("## 1. Item Extraction Summary")
    lines.append("")
    lines.append("| Year | Filings | TOC Found | TOC Missing | Any Items Extracted | Item JSON | Missing Item JSON | Structure JSON | Avg TOC Items | Avg TOC Anchors | Avg Extracted Items | Filings with Item Errors | Filings Missing Expected Items |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")

    for year in sorted(year_stats.keys()):
        y = year_stats[year]
        denom = max(y["item_json_present"], 1)
        lines.append(
            "| {} | {} | {} | {} | {} | {} | {} | {} | {:.2f} | {:.2f} | {:.2f} | {} | {} |".format(
                year,
                y["filings_total"],
                y["filings_toc_found"],
                y["filings_toc_missing"],
                y["filings_with_any_extracted_items"],
                y["item_json_present"],
                y["item_json_missing"],
                y["str_json_present"],
                y["toc_items_sum"] / denom,
                y["toc_anchors_sum"] / denom,
                y["extracted_items_sum"] / denom,
                y["filings_with_item_errors"],
                y["filings_missing_expected_items"],
            )
        )

    lines.append("")
    lines.append("## 2. Item Coverage and Lengths")
    lines.append("")
    lines.append("Coverage is shown in two ways:")
    lines.append("- `X out of Y (TOC)` where Y is filings with TOC found for that year+filing.")
    lines.append("- `Coverage % (Total)` where denominator is all filings for that year+filing.")
    lines.append("")

    lines.append("See CSV for per-item coverage and word-length stats:")
    lines.append(f"- `{item_csv}`")

    lines.append("")
    lines.append("## 3. Structure Extraction Summary")
    lines.append("")
    lines.append("See CSV for per-item structure stats (headings/bodies/depth/ratios):")
    lines.append(f"- `{structure_csv}`")

    lines.append("")
    lines.append("## 4. Extra Items (Outside Regulated Scope)")
    lines.append("")
    if not extra_items:
        lines.append("No extra items found.")
    else:
        lines.append("| Year | Filing | Extra Items |")
        lines.append("|---|---|---|")
        for (year, filing), items in sorted(extra_items.items(), key=lambda x: (x[0][0], x[0][1])):
            lines.append(f"| {year} | {filing} | {', '.join(sorted(items))} |")

    lines.append("")
    lines.append("## 5. Artifacts")
    lines.append("")
    lines.append(f"- Year summary CSV: `{year_csv}`")
    lines.append(f"- Item coverage CSV: `{item_csv}`")
    lines.append(f"- Structure stats CSV: `{structure_csv}`")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path, year_csv, item_csv, structure_csv


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate extraction performance report for current pipeline outputs.")
    parser.add_argument("--folder", default="sec_filings", help="Root filings folder (default: sec_filings)")
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.exists() or not folder.is_dir():
        raise FileNotFoundError(f"Folder not found: {folder}")

    md_path, year_csv, item_csv, structure_csv = build_report(folder)
    print(f"Report generated: {md_path}")
    print(f"Year summary CSV: {year_csv}")
    print(f"Item coverage CSV: {item_csv}")
    print(f"Structure stats CSV: {structure_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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


def build_report(folder: Path) -> Tuple[Path, Path, Path]:
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
    # (year, filing) -> filings count
    filing_counts = defaultdict(int)
    # (year, filing) -> filings where TOC was found (proxy: item json exists)
    filing_toc_found_counts = defaultdict(int)

    # Track extra items (outside expected set)
    extra_items = defaultdict(set)  # (year, filing) -> set[item]

    for cik, year, filing, html_path in _iter_filing_htmls(folder):
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
            if expected and item_num not in expected:
                extra_items[(year, filing)].add(item_num)

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

    # Item coverage CSV
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
            ],
        )
        w.writeheader()
        for (year, filing, item), count in sorted(item_coverage.items(), key=lambda x: (x[0][0], x[0][1], x[0][2])):
            total = filing_counts.get((year, filing), 0)
            toc_found = filing_toc_found_counts.get((year, filing), 0)
            pct_total = (count / total * 100.0) if total else 0.0
            pct_toc = (count / toc_found * 100.0) if toc_found else 0.0
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
                }
            )

    # Markdown report
    md_path = stats_dir / f"extraction_performance_{stamp}.md"
    lines: List[str] = []
    lines.append("# Item Extraction Performance Report")
    lines.append("")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Source folder: `{folder}`")
    lines.append("")

    lines.append("## 1. Yearly Summary")
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
    lines.append("## 2. Coverage by Item")
    lines.append("")
    lines.append("Coverage is shown in two ways:")
    lines.append("- `X out of Y (TOC)` where Y is filings with TOC found for that year+filing.")
    lines.append("- `Coverage % (Total)` where denominator is all filings for that year+filing.")
    lines.append("")

    # Keep table readable: only 10-K and 10-Q style filings
    target_forms = {"10-K", "10-KA", "10-Q", "10-QA"}
    lines.append("| Year | Filing | Item | X out of Y (TOC) | Coverage % (TOC Found) | Coverage % (Total) |")
    lines.append("|---|---|---|---|---:|---:|")
    for (year, filing, item), count in sorted(item_coverage.items(), key=lambda x: (x[0][0], x[0][1], x[0][2])):
        if filing not in target_forms:
            continue
        total = filing_counts.get((year, filing), 0)
        toc_found = filing_toc_found_counts.get((year, filing), 0)
        pct_total = (count / total * 100.0) if total else 0.0
        pct_toc = (count / toc_found * 100.0) if toc_found else 0.0
        lines.append(f"| {year} | {filing} | {item} | {count}/{toc_found} | {pct_toc:.2f} | {pct_total:.2f} |")

    lines.append("")
    lines.append("## 3. Extra Items (Outside Regulated Scope)")
    lines.append("")
    if not extra_items:
        lines.append("No extra items found.")
    else:
        lines.append("| Year | Filing | Extra Items |")
        lines.append("|---|---|---|")
        for (year, filing), items in sorted(extra_items.items(), key=lambda x: (x[0][0], x[0][1])):
            lines.append(f"| {year} | {filing} | {', '.join(sorted(items))} |")

    lines.append("")
    lines.append("## 4. Artifacts")
    lines.append("")
    lines.append(f"- Year summary CSV: `{year_csv}`")
    lines.append(f"- Item coverage CSV: `{item_csv}`")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path, year_csv, item_csv


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate extraction performance report for current pipeline outputs.")
    parser.add_argument("--folder", default="sec_filings", help="Root filings folder (default: sec_filings)")
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.exists() or not folder.is_dir():
        raise FileNotFoundError(f"Folder not found: {folder}")

    md_path, year_csv, item_csv = build_report(folder)
    print(f"Report generated: {md_path}")
    print(f"Year summary CSV: {year_csv}")
    print(f"Item coverage CSV: {item_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

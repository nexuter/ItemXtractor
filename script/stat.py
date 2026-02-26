"""
Extraction performance report generator.

Produces per-year markdown reports under stats/:
  extraction_stat_{year}_{timestamp}.md
"""

from __future__ import annotations

import argparse
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


def _iter_filing_htmls(root: Path, years: Optional[Set[int]] = None):
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
            if years and year not in years:
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


def build_report(folder: Path, years: Optional[Set[int]] = None) -> List[Path]:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stats_dir = Path("stats")
    stats_dir.mkdir(parents=True, exist_ok=True)

    # Year-level aggregates
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

    # Detailed issue tracking
    item_errors = defaultdict(list)  # year -> list of (cik, filing, item, error)
    missing_expected = defaultdict(list)  # year -> list of (cik, filing, missing_items)
    missing_toc = defaultdict(list)  # year -> list of (cik, filing, html_name)

    # Structure stats per item
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

    html_list = list(_iter_filing_htmls(folder, years=years))
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
            missing_toc[year].append((cik, filing, html_path.name))
            continue

        y["item_json_present"] += 1
        y["filings_toc_found"] += 1
        filing_toc_found_counts[(year, filing)] += 1

        toc_items = item_payload.get("toc_items", {}) or {}
        items = item_payload.get("items", {}) or {}

        y["toc_items_sum"] += len(toc_items)
        y["toc_anchors_sum"] += sum(1 for v in toc_items.values() if isinstance(v, dict) and v.get("anchor"))
        y["extracted_items_sum"] += len(items)

        expected = EXPECTED_ITEMS_BY_FILING.get(filing, set())
        extracted_item_nums = {k for k in items.keys()}
        if extracted_item_nums:
            y["filings_with_any_extracted_items"] += 1

        had_error = False
        for item_num, payload in items.items():
            if isinstance(payload, dict) and payload.get("error"):
                had_error = True
                item_errors[year].append((cik, filing, item_num, str(payload.get("error"))))
        if had_error:
            y["filings_with_item_errors"] += 1

        if expected:
            missing = sorted(expected - extracted_item_nums)
            if missing:
                y["filings_missing_expected_items"] += 1
                missing_expected[year].append((cik, filing, ", ".join(missing)))

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

    # Build per-year markdowns
    outputs: List[Path] = []
    for year in sorted(year_stats.keys()):
        y = year_stats[year]
        denom = max(y["item_json_present"], 1)
        md_path = stats_dir / f"extraction_stat_{year}_{stamp}.md"
        lines: List[str] = []
        lines.append("# Extraction Performance Report")
        lines.append("")
        lines.append(f"Year: {year}")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Source folder: `{folder}`")
        lines.append("")

        lines.append("## 1. Item Extraction Summary")
        lines.append("")
        lines.append("| Filings | TOC Found | TOC Missing | Any Items Extracted | Item JSON | Missing Item JSON | Structure JSON | Avg TOC Items | Avg TOC Anchors | Avg Extracted Items | Filings with Item Errors | Filings Missing Expected Items |")
        lines.append("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        lines.append(
            "| {} | {} | {} | {} | {} | {} | {} | {:.2f} | {:.2f} | {:.2f} | {} | {} |".format(
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
        lines.append("| Filing | Item | X out of Y (TOC) | Coverage % (TOC Found) | Coverage % (Total) | Avg Words | Min Words | Max Words |")
        lines.append("|---|---|---|---:|---:|---:|---:|---:|")
        for (yy, filing, item), count in sorted(item_coverage.items(), key=lambda x: (x[0][0], x[0][1], x[0][2])):
            if yy != year:
                continue
            total = filing_counts.get((yy, filing), 0)
            toc_found = filing_toc_found_counts.get((yy, filing), 0)
            pct_total = (count / total * 100.0) if total else 0.0
            pct_toc = (count / toc_found * 100.0) if toc_found else 0.0
            agg = item_lengths[(yy, filing, item)]
            avg_words = round(agg[1] / max(agg[0], 1), 2)
            lines.append(
                f"| {filing} | {item} | {count}/{toc_found} | {pct_toc:.2f} | {pct_total:.2f} | {avg_words} | {agg[2] or 0} | {agg[3] or 0} |"
            )

        lines.append("")
        lines.append("## 3. Structure Extraction Stats")
        lines.append("")
        lines.append("| Filing | Item | Filings | Avg Headings | Min | Max | Avg Bodies | Min | Max | Avg Depth | Min | Max | Avg H/B | Min | Max |")
        lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for (yy, filing, item), s in sorted(structure_stats.items()):
            if yy != year:
                continue
            count = max(s["count"], 1)
            lines.append(
                "| {} | {} | {} | {:.2f} | {} | {} | {:.2f} | {} | {} | {:.2f} | {} | {} | {:.2f} | {} | {} |".format(
                    filing,
                    item,
                    s["count"],
                    s["head_sum"] / count,
                    s["head_min"] or 0,
                    s["head_max"] or 0,
                    s["body_sum"] / count,
                    s["body_min"] or 0,
                    s["body_max"] or 0,
                    s["depth_sum"] / count,
                    s["depth_min"] or 0,
                    s["depth_max"] or 0,
                    (s["ratio_sum"] / count) if s["count"] else 0.0,
                    round(s["ratio_min"], 2) if s["ratio_min"] is not None else 0.0,
                    round(s["ratio_max"], 2) if s["ratio_max"] is not None else 0.0,
                )
            )

        lines.append("")
        lines.append("## 4. Filings with Item Errors")
        lines.append("")
        lines.append("These are per-item extraction errors recorded in `*_item.json`.")
        if not item_errors.get(year):
            lines.append("None.")
        else:
            lines.append("| CIK | Filing | Item | Error |")
            lines.append("|---|---|---|---|")
            for cik, filing, item_num, err in item_errors[year]:
                lines.append(f"| {cik} | {filing} | {item_num} | {err} |")

        lines.append("")
        lines.append("## 5. Filings Missing Expected Items")
        lines.append("")
        lines.append("Expected item list is from `script/config.py`.")
        if not missing_expected.get(year):
            lines.append("None.")
        else:
            lines.append("| CIK | Filing | Missing Items |")
            lines.append("|---|---|---|")
            for cik, filing, missing in missing_expected[year]:
                lines.append(f"| {cik} | {filing} | {missing} |")

        lines.append("")
        lines.append("## 6. Filings Missing TOC")
        lines.append("")
        if not missing_toc.get(year):
            lines.append("None.")
        else:
            lines.append("| CIK | Filing | HTML |")
            lines.append("|---|---|---|")
            for cik, filing, html_name in missing_toc[year]:
                lines.append(f"| {cik} | {filing} | {html_name} |")

        lines.append("")
        lines.append("## 7. Extra Items (Outside Regulated Scope)")
        lines.append("")
        if not extra_items:
            lines.append("No extra items found.")
        else:
            lines.append("| Filing | Extra Items |")
            lines.append("|---|---|")
            for (yy, filing), items in sorted(extra_items.items(), key=lambda x: (x[0][0], x[0][1])):
                if yy != year:
                    continue
                lines.append(f"| {filing} | {', '.join(sorted(items))} |")

        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        outputs.append(md_path)

    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate extraction performance report for current pipeline outputs.")
    parser.add_argument("--folder", default="sec_filings", help="Root filings folder (default: sec_filings)")
    parser.add_argument("--year", nargs="+", type=int, help="Optional year(s) to scope the report")
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.exists() or not folder.is_dir():
        raise FileNotFoundError(f"Folder not found: {folder}")

    years = set(args.year) if args.year else None
    outputs = build_report(folder, years=years)
    for path in outputs:
        print(f"Report generated: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Run pdf-inspector's classifier on the corpus and compare OCR routing with the known answers.

Usage: python run_bench.py [corpus_dir] [results.json]
"""

import json
import statistics
import sys
import time
from importlib.metadata import version
from collections import defaultdict
from pathlib import Path

import pdf_inspector


def run(corpus: Path) -> list[dict]:
    rows = json.loads((corpus / "manifest.json").read_text())
    for row in rows:
        path = str(corpus / row["file"])
        start = time.perf_counter()
        cls = pdf_inspector.classify_pdf(path)
        row["classify_ms"] = round((time.perf_counter() - start) * 1000, 2)
        det = pdf_inspector.detect_pdf(path)
        row["pdf_type"] = cls.pdf_type
        row["confidence"] = round(cls.confidence, 3)
        row["ocr_pages"] = sorted(cls.pages_needing_ocr)
        row["detect_ocr_pages"] = sorted(p - 1 for p in det.pages_needing_ocr)
        row["reasons"] = {r.page: list(r.reasons) for r in det.ocr_reasons_by_page}
        expected = row["expected_ocr_pages"]
        row["routing_correct"] = None if expected is None else row["ocr_pages"] == expected
        missed = [] if expected is None else [p for p in expected if p not in row["ocr_pages"]]
        row["missed_pages"] = missed
    return rows


def summarize(rows: list[dict]) -> None:
    by_variant = defaultdict(list)
    for row in rows:
        by_variant[row["variant"]].append(row)
    print(f"pdf-inspector {version('pdf-inspector')}")
    print("| variant | files | pdf_type seen | routing matches expected | pages that needed OCR but were not routed | median classify ms |")
    print("|---|---|---|---|---|---|")
    for variant in ["text", "scan", "scan_stamp", "scan_layer", "mixed"]:
        group = by_variant.get(variant, [])
        if not group:
            continue
        types = sorted({r["pdf_type"] for r in group})
        if group[0]["expected_ocr_pages"] is None:
            correct = "n/a"
            missed = "n/a"
        else:
            correct = f"{sum(r['routing_correct'] for r in group)}/{len(group)}"
            missed = f"{sum(len(r['missed_pages']) for r in group)}/{sum(len(r['expected_ocr_pages']) for r in group)}"
        ms = statistics.median(r["classify_ms"] for r in group)
        print(f"| {variant} | {len(group)} | {', '.join(types)} | {correct} | {missed} | {ms:.1f} |")


def main() -> None:
    corpus = Path(sys.argv[1] if len(sys.argv) > 1 else "corpus")
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "results.json")
    rows = run(corpus)
    out.write_text(json.dumps(rows, indent=1))
    summarize(rows)


if __name__ == "__main__":
    main()

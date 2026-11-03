"""How much real, visible text can a scanned page carry before it stops being routed to OCR?

Each page is rendered to a 150 dpi image (so the whole body is pixels only), then the
first N words of the page's own text are drawn back on top as real, visible text in the
same positions, like a fax header, a typed cover note, or a form where only some fields
are typed. The body still needs OCR at every N short of the full page, so a page that
is not routed is a missed page.

Usage: python sweep.py [sources_dir] [sweep.json]
"""

import json
import sys
from pathlib import Path

import pdf_inspector
import pymupdf

from make_corpus import PAGES, scan_page

WORD_COUNTS = [0, 5, 8, 9, 10, 20, 40, 80, 160, 320]
LINE_COUNTS = [0, 1, 3, 5, 8, 9, 10, 15, 20, 30]


def overlay_words(page: pymupdf.Page, src_page: pymupdf.Page, n: int) -> int:
    words = src_page.get_text("words", sort=True)[:n]
    for x0, y0, x1, y1, word, *_ in words:
        size = max(4.0, (y1 - y0) * 0.8)
        page.insert_text((x0, y1 - (y1 - y0) * 0.2), word, fontsize=size)
    return len(words)


def overlay_lines(page: pymupdf.Page, src_page: pymupdf.Page, n: int) -> int:
    lines = []
    for block in src_page.get_text("dict", sort=True)["blocks"]:
        for line in block.get("lines", []):
            text = " ".join(span["text"] for span in line["spans"]).strip()
            if text:
                lines.append((line["bbox"], line["spans"][0]["size"], text))
    for (x0, y0, x1, y1), size, text in lines[:n]:
        page.insert_text((x0, y1 - (y1 - y0) * 0.2), text, fontsize=max(4.0, size))
    return min(n, len(lines))


def main() -> None:
    src_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "sources")
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "sweep.json")
    rows = []
    for src in sorted(src_dir.glob("*.pdf")):
        doc = pymupdf.open(src)
        for i in range(min(PAGES, doc.page_count)):
            total_words = len(doc[i].get_text("words"))
            for n in WORD_COUNTS:
                one = pymupdf.open()
                drawn = overlay_words(scan_page(one, doc[i]), doc[i], n)
                data = one.tobytes(garbage=3, deflate=True)
                cls = pdf_inspector.classify_pdf_bytes(data)
                det = pdf_inspector.detect_pdf_bytes(data)
                rows.append(
                    {
                        "mode": "words",
                        "source": src.stem,
                        "page": i,
                        "page_words": total_words,
                        "overlay_words": drawn,
                        "pdf_type": cls.pdf_type,
                        "routed_to_ocr": 0 in cls.pages_needing_ocr,
                        "reasons": [r for p in det.ocr_reasons_by_page for r in p.reasons],
                    }
                )
            total_lines = sum(len(b.get("lines", [])) for b in doc[i].get_text("dict")["blocks"])
            for n in LINE_COUNTS:
                one = pymupdf.open()
                drawn = overlay_lines(scan_page(one, doc[i]), doc[i], n)
                data = one.tobytes(garbage=3, deflate=True)
                cls = pdf_inspector.classify_pdf_bytes(data)
                rows.append(
                    {
                        "mode": "lines",
                        "source": src.stem,
                        "page": i,
                        "page_lines": total_lines,
                        "overlay_lines": drawn,
                        "pdf_type": cls.pdf_type,
                        "routed_to_ocr": 0 in cls.pages_needing_ocr,
                    }
                )
    out.write_text(json.dumps(rows, indent=1))

    words = [r for r in rows if r["mode"] == "words"]
    lines = [r for r in rows if r["mode"] == "lines"]
    print("Words drawn one at a time (one text operator each):")
    print("| visible words drawn over the scan | pages | routed to OCR | missed (not routed) | share of page text |")
    print("|---|---|---|---|---|")
    for n in WORD_COUNTS:
        group = [r for r in words if r["overlay_words"] == n]
        if not group:
            continue
        routed = sum(r["routed_to_ocr"] for r in group)
        share = sum(r["overlay_words"] / r["page_words"] for r in group) / len(group)
        print(f"| {n} | {len(group)} | {routed} | {len(group) - routed} | {share:.0%} |")

    print()
    print("Whole lines drawn as one string each (like a typed header or filled form fields):")
    print("| visible lines drawn over the scan | pages | routed to OCR | missed (not routed) | share of page lines |")
    print("|---|---|---|---|---|")
    for n in LINE_COUNTS:
        group = [r for r in lines if r["overlay_lines"] == n]
        if not group:
            continue
        routed = sum(r["routed_to_ocr"] for r in group)
        share = sum(r["overlay_lines"] / r["page_lines"] for r in group) / len(group)
        print(f"| {n} | {len(group)} | {routed} | {len(group) - routed} | {share:.0%} |")


if __name__ == "__main__":
    main()

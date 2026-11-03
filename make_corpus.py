"""Build scan variants of text PDFs so OCR routing can be checked against known answers.

For every PDF in sources/ the first PAGES pages are turned into five files:

  text        the original pages                      -> no page needs OCR
  scan        each page rendered to a 150 dpi image   -> every page needs OCR
  scan_stamp  the scan plus a small visible text stamp (Bates number + header),
              like a produced legal document          -> every page needs OCR
  scan_layer  the scan plus an invisible text layer (render mode 3),
              like OCRmyPDF output                    -> text is already there
  mixed       original pages with page 2 replaced by its scan -> only page 2

Usage: python make_corpus.py [sources_dir] [out_dir]
"""

import json
import sys
from pathlib import Path

import pymupdf

PAGES = 4
DPI = 150


def scan_page(out: pymupdf.Document, src_page: pymupdf.Page) -> pymupdf.Page:
    pix = src_page.get_pixmap(dpi=DPI, colorspace=pymupdf.csGRAY)
    page = out.new_page(width=src_page.rect.width, height=src_page.rect.height)
    page.insert_image(page.rect, stream=pix.tobytes("png"))
    return page


def add_invisible_layer(page: pymupdf.Page, src_page: pymupdf.Page) -> None:
    for x0, y0, x1, y1, word, *_ in src_page.get_text("words"):
        size = max(4.0, (y1 - y0) * 0.8)
        page.insert_text((x0, y1 - (y1 - y0) * 0.2), word, fontsize=size, render_mode=3)


def add_stamp(page: pymupdf.Page, doc_id: str, index: int) -> None:
    w, h = page.rect.width, page.rect.height
    page.insert_text((36, 24), "CONFIDENTIAL - PRODUCED IN DISCOVERY", fontsize=7)
    page.insert_text((w - 120, h - 18), f"ABC-{doc_id[-5:]}-{index + 1:04d}", fontsize=8)


def build(src: Path, out_dir: Path) -> list[dict]:
    doc = pymupdf.open(src)
    n = min(PAGES, doc.page_count)
    stem = src.stem
    rows = []

    variants = {}

    text = pymupdf.open()
    text.insert_pdf(doc, from_page=0, to_page=n - 1)
    variants["text"] = (text, [])

    scan = pymupdf.open()
    for i in range(n):
        scan_page(scan, doc[i])
    variants["scan"] = (scan, list(range(n)))

    stamp = pymupdf.open()
    for i in range(n):
        add_stamp(scan_page(stamp, doc[i]), stem, i)
    variants["scan_stamp"] = (stamp, list(range(n)))

    layer = pymupdf.open()
    for i in range(n):
        add_invisible_layer(scan_page(layer, doc[i]), doc[i])
    variants["scan_layer"] = (layer, None)

    mixed = pymupdf.open()
    for i in range(n):
        if i == 1:
            scan_page(mixed, doc[i])
        else:
            mixed.insert_pdf(doc, from_page=i, to_page=i)
    variants["mixed"] = (mixed, [1])

    for name, (variant, expected) in variants.items():
        path = out_dir / f"{stem}__{name}.pdf"
        variant.save(path, garbage=3, deflate=True)
        rows.append({"file": path.name, "source": stem, "variant": name, "pages": n, "expected_ocr_pages": expected})
    return rows


def main() -> None:
    src_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "sources")
    out_dir = Path(sys.argv[2] if len(sys.argv) > 2 else "corpus")
    out_dir.mkdir(exist_ok=True)
    rows = []
    for src in sorted(src_dir.glob("*.pdf")):
        rows.extend(build(src, out_dir))
    (out_dir / "manifest.json").write_text(json.dumps(rows, indent=1))
    print(f"wrote {len(rows)} files to {out_dir}")


if __name__ == "__main__":
    main()

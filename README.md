# ocr-routing-bench

I wanted to know how well [pdf-inspector](https://github.com/firecrawl/pdf-inspector) decides which PDF pages need OCR, so I built scan variants of real papers where the right answer is known and checked its routing against them.

## Setup

```sh
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
./fetch_sources.sh            # six arXiv papers, first 4 pages of each are used
.venv/bin/python make_corpus.py
.venv/bin/python run_bench.py # writes results.json
.venv/bin/python sweep.py     # writes sweep.json
.venv/bin/python -m pytest -q tests
```

Everything runs locally with pdf-inspector 1.25.2 from PyPI and PyMuPDF 2.1 (used only to build the test files). No OCR runtime is needed, since only classification is measured.

## Part 1: common scan shapes

`make_corpus.py` turns the first 4 pages of each paper into five files: the original pages, a 150 dpi grayscale scan, the scan plus a small visible stamp (a "CONFIDENTIAL" header and a Bates number), the scan plus an invisible OCR text layer (render mode 3, the shape OCRmyPDF produces), and the original with page 2 swapped for its scan.

| variant | files | pdf_type | routing matches expected | pages needing OCR that were not routed | median classify ms |
|---|---|---|---|---|---|
| text | 6 | text_based | 6/6 | 0/0 | 2.4 |
| scan | 6 | scanned | 6/6 | 0/24 | 1.0 |
| scan_stamp | 6 | image_based | 6/6 | 0/24 | 0.9 |
| scan_layer | 6 | image_based | n/a | n/a | 15.1 |
| mixed | 6 | mixed | 6/6 | 0/6 | 2.3 |

All 30 files were routed the way I expected. The scan with an invisible layer is routed to OCR with the reason `invisible_text_layer`, which matches the current design (issue #627 asks for an option to read that layer instead).

## Part 2: how much real text can sit on top of a scan

Real scans often carry some genuine text: a fax header, a typed cover note, filled form fields. `sweep.py` takes each of the 24 pages, renders it to an image, and draws the first N lines of the page's own text back on top as real, visible text in the same spots. The body below is still pixels only, so every page in this sweep needs OCR.

Lines drawn as one string each:

| visible lines over the scan | pages | routed to OCR | not routed | share of the page's lines |
|---|---|---|---|---|
| 0 | 24 | 24 | 0 | 0% |
| 1 | 24 | 24 | 0 | 2% |
| 5 | 24 | 24 | 0 | 8% |
| 9 | 24 | 24 | 0 | 14% |
| 10 | 24 | 0 | 24 | 16% |
| 20 | 24 | 0 | 24 | 32% |
| 30 | 23 | 0 | 23 | 45% |

Words drawn one at a time give the same cliff: 9 words over the scan are routed, 10 words (about 2% of the page) are classified `text_based` with no pages routed.

So the switch is a fixed count of 10 text operators on a page that has an image, and it does not depend on how much of the page the text covers. In `src/detector.rs` this is `min_text_ops_per_page.max(10)` for pages with images. Once every sampled page clears it, the document comes back `text_based`, and `process_pdf` returns only the overlaid text. For one page of the Transformer paper with 10 typed lines over the scan, the markdown had 89 words, while the page has 292.

This is the case described in [firecrawl/pdf-inspector#205](https://github.com/firecrawl/pdf-inspector/issues/205) (a full-page raster with a real header or footer short-circuits to `TextBased`). The sweep shows where the cliff is and that it is sharp.

## Limits

- The overlays are synthetic. Real fax headers or typed form fields may be drawn with fewer or more text operators per line than PyMuPDF's `insert_text`, which moves where a given document lands relative to the cliff, not the cliff itself.
- 24 pages from 6 papers, all English and single or two-column. I did not test forms, handwriting or non-Latin scripts.
- Only the lightweight classifier (`classify_pdf`, `detect_pdf`) is measured, not OCR quality.
- Timings are from a single run on an Apple Silicon laptop and are only a rough guide.

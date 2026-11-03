from pathlib import Path

import pdf_inspector
import pymupdf
import pytest

from make_corpus import add_invisible_layer, scan_page
from sweep import overlay_lines

SOURCE = Path(__file__).resolve().parent.parent / "sources" / "1706.03762.pdf"


@pytest.fixture(scope="module")
def page():
    return pymupdf.open(SOURCE)[2]


def scanned(page, lines=0, invisible=False):
    doc = pymupdf.open()
    out = scan_page(doc, page)
    if lines:
        overlay_lines(out, page, lines)
    if invisible:
        add_invisible_layer(out, page)
    return doc


def test_scan_has_no_text(page):
    assert scanned(page)[0].get_text().strip() == ""


def test_invisible_layer_is_hidden_but_extractable(page):
    doc = scanned(page, invisible=True)
    assert len(doc[0].get_text("words")) > 100


def test_overlay_draws_requested_lines(page):
    doc = scanned(page, lines=3)
    assert 0 < len(doc[0].get_text("words")) < 60


def test_plain_scan_is_routed_to_ocr(page):
    cls = pdf_inspector.classify_pdf_bytes(scanned(page).tobytes())
    assert cls.pages_needing_ocr == [0]


def test_nine_typed_lines_still_routed(page):
    cls = pdf_inspector.classify_pdf_bytes(scanned(page, lines=9).tobytes())
    assert cls.pages_needing_ocr == [0]


def test_ten_typed_lines_skip_ocr(page):
    # Documents the behavior measured in the README: the body is still pixels only.
    cls = pdf_inspector.classify_pdf_bytes(scanned(page, lines=10).tobytes())
    assert cls.pdf_type == "text_based"
    assert cls.pages_needing_ocr == []

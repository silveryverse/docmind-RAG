from app.pdf import _clean, _respace, extract
from tests.helpers import build_pdf, build_scanned_pdf


def test_clean_normalises_ligatures_and_whitespace():
    assert _clean("of\uFB01ce  revenue\n\nrose") == "office revenue rose"


def test_clean_keeps_hyphenated_codes_at_line_break():
    assert _clean("part number HX-\nSH2.") == "part number HX-SH2."


def test_clean_collapses_soft_hyphens():
    assert _clean("man\u00ADagement") == "management"


def test_respace_splits_glued_words_from_ocr():
    assert _respace("ApprovedbytheEmploymentCommittee") == "Approved by the Employment Committee"
    assert _respace("Effective1February2025") == "Effective 1 February 2025"
    # A real word must be left alone.
    assert _respace("Pellham") == "Pellham"


def test_extract_reads_text_pdf(tmp_path):
    path = build_pdf(tmp_path / "text.pdf", ["Shipping revenue rose 11.4% in fiscal 2025."])
    pages = extract(str(path))
    assert len(pages) == 1
    assert pages[0].ocr is False
    assert "11.4%" in pages[0].text


def test_extract_falls_back_to_ocr_for_image_only_pages(tmp_path):
    path = build_scanned_pdf(tmp_path / "scan.pdf", ["Total charge was 0.95 kg of R290 refrigerant."])
    pages = extract(str(path))
    assert pages[0].ocr is True
    # OCR is imperfect but must recover the distinctive values.
    assert "0.95" in pages[0].text and "R290" in pages[0].text
    assert pages[0].blocks[0].box[2] > pages[0].blocks[0].box[0]

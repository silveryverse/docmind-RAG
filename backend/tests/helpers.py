"""Small PDF builders used by tests."""

from pathlib import Path

import numpy as np
import pymupdf


def build_pdf(path: Path, paragraphs: list[str]) -> Path:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    html = "".join(f"<p>{p}</p>" for p in paragraphs)
    page.insert_htmlbox(pymupdf.Rect(60, 60, 535, 780), html, css="p { font-family: serif; font-size: 11pt; }")
    doc.set_metadata({"title": "Test document"})
    doc.save(path)
    return path


def build_scanned_pdf(path: Path, paragraphs: list[str]) -> Path:
    """Render text to an image and wrap it in a PDF with no text layer."""
    src = pymupdf.open()
    page = src.new_page(width=595, height=842)
    html = "".join(f"<p>{p}</p>" for p in paragraphs)
    page.insert_htmlbox(
        pymupdf.Rect(60, 60, 535, 780), html, css="p { font-family: serif; font-size: 13pt; }"
    )
    pix = page.get_pixmap(dpi=150, colorspace=pymupdf.csGRAY, alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).astype(np.int16)
    rng = np.random.default_rng(3)
    img = np.clip(img + rng.normal(0, 7, img.shape).astype(np.int16) - 4, 0, 255).astype(np.uint8)
    scan = pymupdf.Pixmap(pymupdf.csGRAY, pix.width, pix.height, img.tobytes(), False)

    out = pymupdf.open()
    out_page = out.new_page(width=595, height=842)
    out_page.insert_image(out_page.rect, pixmap=scan)
    out.save(path)
    return path

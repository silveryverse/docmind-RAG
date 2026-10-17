"""PDF text extraction with OCR fallback for scanned pages.

Each page is reduced to a list of text blocks with bounding boxes normalised to
0..1, so that chunks can carry the regions they came from for highlighting.
"""

import logging
import re
import unicodedata
from dataclasses import dataclass, field

import numpy as np
import pymupdf

from .config import get_settings

log = logging.getLogger(__name__)

_ocr_engine = None


@dataclass
class Block:
    text: str
    box: tuple[float, float, float, float]  # x0, y0, x1, y1 normalised


@dataclass
class PageContent:
    page_no: int  # 1-based
    width: float
    height: float
    ocr: bool
    blocks: list[Block] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n\n".join(b.text for b in self.blocks)


def _clean(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)  # ligatures such as "ﬁ" -> "fi"
    text = text.replace("\u00ad", "")  # soft hyphens
    # Keep hyphens at line breaks: they are far more often real ("HX-SH2",
    # "four-week") than typographic, and dropping a real one breaks matching.
    text = re.sub(r"-\n\s*", "-", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s*\n\s*", " ", text)
    return text.strip()


def _norm_box(rect, w: float, h: float) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = rect
    return (
        round(max(0.0, x0 / w), 4),
        round(max(0.0, y0 / h), 4),
        round(min(1.0, x1 / w), 4),
        round(min(1.0, y1 / h), 4),
    )


_GLUED = re.compile(r"[A-Za-z]{9,}")
_CAMEL = re.compile(r"[a-z][A-Z]")


def _respace(text: str) -> str:
    """OCR on italic/light text often drops word gaps ("ApprovedbytheCommittee").
    Split long glued tokens with a unigram word model, and separate letters
    from digits ("Page1", "1February")."""
    import wordninja

    def fix(m: re.Match) -> str:
        word = m.group(0)
        parts = wordninja.split(word)
        if len(parts) < 2:
            return word
        # Only accept a split that produces real words, not fragments of a name.
        if (_CAMEL.search(word) or len(word) >= 14) and all(len(p) > 1 or p.lower() in "ai" for p in parts):
            return " ".join(parts)
        return word

    text = _GLUED.sub(fix, text)
    text = re.sub(r"(?<=[a-z])(?=\d)", " ", text)
    text = re.sub(r"(?<=\d)(?=[A-Z][a-z])", " ", text)
    text = re.sub(r"(?<=\d\.)(?=[A-Z])", " ", text)  # "2.Attendance" -> "2. Attendance"
    return text


def _get_ocr():
    global _ocr_engine
    if _ocr_engine is None:
        from rapidocr_onnxruntime import RapidOCR

        _ocr_engine = RapidOCR()
    return _ocr_engine


def _run_ocr(page: pymupdf.Page, dpi: int):
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    result, _ = _get_ocr()(img)
    return result or [], pix


def _ocr_page(page: pymupdf.Page, dpi: int) -> list[Block]:
    # The recogniser drops word spaces when glyphs are much larger or smaller
    # than it was trained on, so normalise the median line height to ~32 px.
    result, pix = _run_ocr(page, dpi)
    if result:
        heights = sorted(max(p[1] for p in q) - min(p[1] for p in q) for q, _, _ in result)
        median = heights[len(heights) // 2]
        if median > 0 and not 24 <= median <= 42:
            better = int(min(400, max(72, dpi * 32 / median)))
            result, pix = _run_ocr(page, better)
    if not result:
        return []

    lines = []
    for quad, text, conf in result:
        if float(conf) < 0.5 or not text.strip():
            continue
        xs = [p[0] for p in quad]
        ys = [p[1] for p in quad]
        lines.append((min(xs), min(ys), max(xs), max(ys), text.strip()))

    lines.sort(key=lambda l: (round(l[1] / 8), l[0]))

    # Merge OCR lines into paragraph-like blocks using vertical gaps.
    blocks: list[Block] = []
    cur: list[tuple] = []

    def flush():
        if not cur:
            return
        x0 = min(l[0] for l in cur)
        y0 = min(l[1] for l in cur)
        x1 = max(l[2] for l in cur)
        y1 = max(l[3] for l in cur)
        text = _respace(_clean(" ".join(l[4] for l in cur)))
        blocks.append(Block(text, _norm_box((x0, y0, x1, y1), pix.width, pix.height)))
        cur.clear()

    for line in lines:
        if cur:
            prev = cur[-1]
            line_h = max(prev[3] - prev[1], 1)
            same_row = abs(line[1] - prev[1]) < line_h * 0.5
            gap = line[1] - prev[3]
            if not same_row and gap > line_h * 0.9:
                flush()
        cur.append(line)
    flush()
    return blocks


def extract(path: str, progress=None) -> list[PageContent]:
    settings = get_settings()
    pages: list[PageContent] = []
    with pymupdf.open(path) as doc:
        total = doc.page_count
        for i, page in enumerate(doc):
            w, h = page.rect.width, page.rect.height
            blocks: list[Block] = []
            for b in page.get_text("blocks", sort=True):
                x0, y0, x1, y1, text, _, btype = b
                if btype != 0:
                    continue
                text = _clean(text)
                if text:
                    blocks.append(Block(text, _norm_box((x0, y0, x1, y1), w, h)))

            char_count = sum(len(b.text) for b in blocks)
            used_ocr = False
            if char_count < settings.ocr_min_chars:
                if progress:
                    progress(f"OCR page {i + 1} of {total}")
                try:
                    ocr_blocks = _ocr_page(page, settings.ocr_dpi)
                except Exception:  # OCR must never abort ingestion
                    log.exception("OCR failed on page %s", i + 1)
                    ocr_blocks = []
                if sum(len(b.text) for b in ocr_blocks) > char_count:
                    blocks, used_ocr = ocr_blocks, True
            elif progress and i % 10 == 0:
                progress(f"Reading page {i + 1} of {total}")

            pages.append(PageContent(i + 1, w, h, used_ocr, blocks))
    return pages


def title_of(path: str, pages: list[PageContent]) -> str | None:
    with pymupdf.open(path) as doc:
        meta_title = (doc.metadata or {}).get("title") or ""
    if meta_title.strip() and len(meta_title) < 200:
        return meta_title.strip()
    if pages and pages[0].blocks:
        first = pages[0].blocks[0].text
        if 3 < len(first) < 120:
            return first
    return None


def render_page(path: str, page_no: int, width_px: int = 1100) -> bytes:
    with pymupdf.open(path) as doc:
        page = doc[page_no - 1]
        zoom = width_px / page.rect.width
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        return pix.tobytes("png")

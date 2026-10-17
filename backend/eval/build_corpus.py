"""Render the synthetic corpus to PDF. Scanned documents are rasterised,
lightly degraded and stored as image-only pages so they require OCR."""

import html
import sys
from pathlib import Path

import numpy as np
import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from corpus import DOCUMENTS  # noqa: E402

OUT = Path(__file__).resolve().parent / "corpus"

CSS = """
body { font-family: serif; font-size: 10.5pt; line-height: 1.45; color: #111; }
h1 { font-size: 20pt; margin: 0 0 2pt 0; }
h2 { font-size: 13pt; margin: 14pt 0 4pt 0; }
h3 { font-size: 11pt; margin: 10pt 0 2pt 0; }
p  { margin: 0 0 7pt 0; text-align: justify; }
.sub { font-size: 10pt; color: #444; margin-bottom: 10pt; }
.sig { font-style: italic; margin-top: 12pt; }
table { border-collapse: collapse; margin: 6pt 0 10pt 0; width: 100%; }
td, th { border: 0.5pt solid #777; padding: 3pt 5pt; font-size: 9.5pt; text-align: left; }
th { background: #eee; }
"""


def page_html(blocks) -> str:
    out = []
    for kind, content in blocks:
        if kind == "table":
            head, *rows = content
            out.append("<table><tr>" + "".join(f"<th>{html.escape(c)}</th>" for c in head) + "</tr>")
            for r in rows:
                out.append("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in r) + "</tr>")
            out.append("</table>")
        elif kind in ("sub", "sig"):
            out.append(f'<p class="{kind}">{html.escape(content)}</p>')
        elif kind in ("h1", "h2", "h3"):
            out.append(f"<{kind}>{html.escape(content)}</{kind}>")
        else:
            out.append(f"<p>{html.escape(content)}</p>")
    return "".join(out)


def render_text_pdf(doc_spec) -> pymupdf.Document:
    doc = pymupdf.open()
    for i, blocks in enumerate(doc_spec["pages"], 1):
        page = doc.new_page(width=595, height=842)  # A4
        page.insert_htmlbox(pymupdf.Rect(60, 60, 535, 790), page_html(blocks), css=CSS)
        page.insert_text((60, 815), f"{doc_spec['title']}  |  Page {i}", fontsize=7.5, color=(0.4, 0.4, 0.4))
    doc.set_metadata({"title": doc_spec["title"]})
    return doc


def degrade_to_scan(src: pymupdf.Document, seed: int = 7) -> pymupdf.Document:
    rng = np.random.default_rng(seed)
    out = pymupdf.open()
    for page in src:
        pix = page.get_pixmap(dpi=150, colorspace=pymupdf.csGRAY, alpha=False)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).astype(np.int16)
        img = img + rng.normal(0, 9, img.shape).astype(np.int16) - 6  # sensor noise, slightly dark paper
        img = np.clip(img, 0, 255).astype(np.uint8)
        scan = pymupdf.Pixmap(pymupdf.csGRAY, pix.width, pix.height, img.tobytes(), False)
        new = out.new_page(width=page.rect.width, height=page.rect.height)
        new.insert_image(new.rect, pixmap=scan)
    return out


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for spec in DOCUMENTS:
        doc = render_text_pdf(spec)
        if spec["scanned"]:
            doc = degrade_to_scan(doc)
        path = OUT / spec["filename"]
        doc.save(path, garbage=4, deflate=True)
        print(f"wrote {path} ({doc.page_count} pages{', image-only' if spec['scanned'] else ''})")


if __name__ == "__main__":
    main()

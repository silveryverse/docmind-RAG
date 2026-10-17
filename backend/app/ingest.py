import hashlib
import json
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pgvector import Vector

from . import pdf
from .chunking import chunk_pages
from .config import get_settings
from .db import connection
from .embeddings import embed_passages

log = logging.getLogger(__name__)

# One worker: embedding/OCR are CPU-bound and already use multiple threads internally.
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ingest")


class DuplicateDocument(Exception):
    def __init__(self, document_id: str):
        self.document_id = document_id


def _set(doc_id: str, **fields) -> None:
    cols = ", ".join(f"{k} = %({k})s" for k in fields)
    with connection() as conn:
        conn.execute(f"UPDATE documents SET {cols} WHERE id = %(id)s", {**fields, "id": doc_id})


def save_upload(filename: str, data: bytes) -> str:
    settings = get_settings()
    sha = hashlib.sha256(data).hexdigest()
    with connection() as conn:
        row = conn.execute("SELECT id FROM documents WHERE sha256 = %s", (sha,)).fetchone()
    if row:
        raise DuplicateDocument(str(row["id"]))

    doc_id = str(uuid.uuid4())
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    path = settings.upload_dir / f"{doc_id}.pdf"
    path.write_bytes(data)
    with connection() as conn:
        conn.execute(
            """INSERT INTO documents (id, filename, sha256, file_path, size_bytes, status, progress)
               VALUES (%s, %s, %s, %s, %s, 'queued', 'Waiting to start')""",
            (doc_id, filename, sha, str(path), len(data)),
        )
    return doc_id


def process(doc_id: str) -> None:
    settings = get_settings()
    with connection() as conn:
        row = conn.execute("SELECT file_path FROM documents WHERE id = %s", (doc_id,)).fetchone()
    if not row:
        return
    path = row["file_path"]
    try:
        _set(doc_id, status="processing", progress="Reading pages", error=None)
        pages = pdf.extract(path, progress=lambda msg: _set(doc_id, progress=msg))
        if not any(p.blocks for p in pages):
            raise ValueError("No readable text found, even after OCR.")

        chunks = chunk_pages(pages, settings.chunk_target_chars, settings.chunk_max_chars)
        _set(doc_id, progress=f"Embedding {len(chunks)} passages")
        vectors = embed_passages([c.text for c in chunks])

        with connection() as conn, conn.transaction():
            conn.execute("DELETE FROM pages WHERE document_id = %s", (doc_id,))
            conn.execute("DELETE FROM chunks WHERE document_id = %s", (doc_id,))
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO pages (document_id, page_no, width, height, ocr, text) VALUES (%s,%s,%s,%s,%s,%s)",
                    [(doc_id, p.page_no, p.width, p.height, p.ocr, p.text) for p in pages],
                )
                cur.executemany(
                    """INSERT INTO chunks (document_id, page_no, ord, text, boxes, embedding)
                       VALUES (%s,%s,%s,%s,%s,%s)""",
                    [
                        (doc_id, c.page_no, c.ord, c.text, json.dumps(c.boxes), Vector(v.tolist()))
                        for c, v in zip(chunks, vectors)
                    ],
                )
            conn.execute(
                """UPDATE documents SET status='ready', progress=NULL, title=%s, page_count=%s,
                   ocr_pages=%s, chunk_count=%s, ready_at=now() WHERE id=%s""",
                (
                    pdf.title_of(path, pages),
                    len(pages),
                    sum(p.ocr for p in pages),
                    len(chunks),
                    doc_id,
                ),
            )
        log.info("Indexed %s: %d pages, %d chunks", doc_id, len(pages), len(chunks))
    except Exception as exc:
        log.exception("Ingestion failed for %s", doc_id)
        _set(doc_id, status="failed", progress=None, error=str(exc)[:500])


def enqueue(doc_id: str) -> None:
    _executor.submit(process, doc_id)


def ingest_file_sync(path: Path) -> str:
    """Used by the CLI / evaluation harness."""
    try:
        doc_id = save_upload(path.name, path.read_bytes())
    except DuplicateDocument as dup:
        return dup.document_id
    process(doc_id)
    return doc_id


def resume_pending() -> None:
    with connection() as conn:
        rows = conn.execute(
            "SELECT id FROM documents WHERE status IN ('queued','processing') ORDER BY created_at"
        ).fetchall()
    for r in rows:
        enqueue(str(r["id"]))

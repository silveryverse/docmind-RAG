import logging
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import ingest, pdf
from .config import get_settings
from .db import close_db, connection, init_db
from .rag import answer_question

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    ingest.resume_pending()
    yield
    close_db()


app = FastAPI(title="DocMind", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

DOC_COLUMNS = """id, filename, title, size_bytes, status, progress, error, page_count,
                 ocr_pages, chunk_count, created_at, ready_at"""


def _doc_or_404(doc_id: str) -> dict:
    with connection() as conn:
        row = conn.execute(
            f"SELECT {DOC_COLUMNS}, file_path FROM documents WHERE id = %s", (doc_id,)
        ).fetchone()
    if not row:
        raise HTTPException(404, "Document not found")
    return row


def _public(row: dict) -> dict:
    row = dict(row)
    row.pop("file_path", None)
    row["id"] = str(row["id"])
    return row


@app.get("/api/health")
def health():
    with connection() as conn:
        conn.execute("SELECT 1")
    return {
        "status": "ok",
        "llm_provider": settings.resolved_provider,
        "model": {
            "openai": settings.openai_model,
            "anthropic": settings.anthropic_model,
        }.get(settings.resolved_provider),
        "embed_model": settings.embed_model,
        "rerank": settings.rerank_enabled,
    }


@app.get("/api/documents")
def list_documents():
    with connection() as conn:
        rows = conn.execute(f"SELECT {DOC_COLUMNS} FROM documents ORDER BY created_at DESC").fetchall()
    return [_public(r) for r in rows]


@app.post("/api/documents", status_code=201)
async def upload_document(file: UploadFile = File(...)):
    name = Path(file.filename or "document.pdf").name
    data = await file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File exceeds {settings.max_upload_mb} MB limit")
    if not data.startswith(b"%PDF"):
        raise HTTPException(415, "Only PDF files are supported")
    try:
        doc_id = await run_in_threadpool(ingest.save_upload, name, data)
    except ingest.DuplicateDocument as dup:
        raise HTTPException(409, {"message": "This file has already been uploaded", "id": dup.document_id})
    ingest.enqueue(doc_id)
    return _public(_doc_or_404(doc_id))


@app.get("/api/documents/{doc_id}")
def get_document(doc_id: str):
    return _public(_doc_or_404(doc_id))


@app.delete("/api/documents/{doc_id}", status_code=204)
def delete_document(doc_id: str):
    row = _doc_or_404(doc_id)
    with connection() as conn:
        conn.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
    Path(row["file_path"]).unlink(missing_ok=True)
    return Response(status_code=204)


@app.post("/api/documents/{doc_id}/reindex", status_code=202)
def reindex_document(doc_id: str):
    _doc_or_404(doc_id)
    with connection() as conn:
        conn.execute(
            "UPDATE documents SET status='queued', progress='Waiting to start', error=NULL WHERE id=%s",
            (doc_id,),
        )
    ingest.enqueue(doc_id)
    return {"id": doc_id, "status": "queued"}


@app.get("/api/documents/{doc_id}/file")
def document_file(doc_id: str):
    row = _doc_or_404(doc_id)
    return FileResponse(row["file_path"], media_type="application/pdf", filename=row["filename"])


@app.get("/api/documents/{doc_id}/pages/{page_no}")
def page_info(doc_id: str, page_no: int):
    with connection() as conn:
        row = conn.execute(
            "SELECT page_no, width, height, ocr, text FROM pages WHERE document_id=%s AND page_no=%s",
            (doc_id, page_no),
        ).fetchone()
    if not row:
        raise HTTPException(404, "Page not found")
    return row


@app.get("/api/documents/{doc_id}/pages/{page_no}/image")
def page_image(doc_id: str, page_no: int, width: int = Query(1100, ge=200, le=2400)):
    row = _doc_or_404(doc_id)
    if row["page_count"] and not 1 <= page_no <= row["page_count"]:
        raise HTTPException(404, "Page not found")
    png = pdf.render_page(row["file_path"], page_no, width)
    return Response(png, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    document_ids: list[str] | None = None


@app.post("/api/ask")
async def ask(req: AskRequest):
    try:
        result = await run_in_threadpool(answer_question, req.question.strip(), req.document_ids or None)
    except RuntimeError as exc:
        raise HTTPException(502, str(exc))
    return asdict(result)


# Serve the built frontend if present (single-process deployment).
_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _dist.is_dir():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")

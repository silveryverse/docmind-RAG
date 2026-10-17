"""Integration tests: real Postgres + pgvector, real embedding and rerank models.

Run with:  pytest -m integration
Skip with: pytest -m "not integration"
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.db import connection, init_db
from app.ingest import ingest_file_sync, process
from app.main import app
from tests.helpers import build_pdf

pytestmark = pytest.mark.integration

FACTS = [
    "The Kakapo Reservoir holds 4.2 million cubic metres of water.",
    "Maintenance of the Kakapo Reservoir is carried out by the Tui Engineering Company.",
    "The annual inspection of the spillway is due every November.",
]


@pytest.fixture(scope="module")
def indexed_doc(tmp_path_factory):
    init_db()
    path = build_pdf(tmp_path_factory.mktemp("docs") / "kakapo.pdf", FACTS)
    doc_id = ingest_file_sync(path)
    yield doc_id
    with connection() as conn:
        conn.execute("DELETE FROM documents WHERE id = %s", (doc_id,))


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_document_is_ready_and_indexed(indexed_doc):
    with connection() as conn:
        row = conn.execute(
            "SELECT status, page_count, chunk_count FROM documents WHERE id = %s", (indexed_doc,)
        ).fetchone()
    assert row["status"] == "ready"
    assert row["page_count"] == 1
    assert row["chunk_count"] >= 1


def test_relevant_passage_ranks_first(indexed_doc):
    from app.retrieval import has_evidence, search

    hits = search("How much water does the Kakapo Reservoir hold?", [indexed_doc])
    assert hits, "expected at least one passage"
    assert "4.2 million" in hits[0].text
    assert has_evidence(hits) is True


def test_off_topic_question_is_gated(indexed_doc):
    from app.retrieval import has_evidence, search

    hits = search("Who won the 2018 FIFA World Cup final?", [indexed_doc])
    assert has_evidence(hits) is False


def test_document_scope_excludes_other_documents(indexed_doc):
    from app.retrieval import search

    hits = search("Kakapo Reservoir", [str(uuid.uuid4())])
    assert hits == []


def test_ask_endpoint_answers_with_citations(indexed_doc, client):
    res = client.post("/api/ask", json={"question": "Who maintains the Kakapo Reservoir?",
                                       "document_ids": [indexed_doc]})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["answerable"] is True
    assert body["citations"], body
    assert all(c["document_id"] == indexed_doc for c in body["citations"])
    assert "Tui" in body["answer"]


def test_ask_endpoint_refuses_out_of_scope_question(indexed_doc, client):
    res = client.post("/api/ask", json={"question": "What is the capital of Australia?",
                                       "document_ids": [indexed_doc]})
    assert res.status_code == 200
    body = res.json()
    assert body["answerable"] is False
    assert body["citations"] == []
    assert body["refusal_reason"] == "no_relevant_passages"


def test_health_and_document_routes(indexed_doc, client):
    assert client.get("/api/health").json()["status"] == "ok"
    docs = client.get("/api/documents").json()
    assert any(d["id"] == indexed_doc for d in docs)
    assert client.get(f"/api/documents/{indexed_doc}").json()["status"] == "ready"


def test_page_image_is_rendered(indexed_doc, client):
    res = client.get(f"/api/documents/{indexed_doc}/pages/1/image?width=400")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    assert res.content.startswith(b"\x89PNG")


def test_upload_rejects_non_pdf(client):
    res = client.post("/api/documents", files={"file": ("evil.txt", b"not a pdf", "text/plain")})
    assert res.status_code == 415


def test_upload_reports_duplicate(indexed_doc, client):
    with connection() as conn:
        path = conn.execute("SELECT file_path, filename FROM documents WHERE id=%s", (indexed_doc,)).fetchone()
    with open(path["file_path"], "rb") as fh:
        res = client.post("/api/documents", files={"file": (path["filename"], fh, "application/pdf")})
    assert res.status_code == 409
    assert res.json()["detail"]["id"] == indexed_doc


def test_failed_ingest_records_an_error(tmp_path):
    path = tmp_path / "empty.pdf"
    import pymupdf

    doc = pymupdf.open()
    doc.new_page()
    doc.save(path)
    doc_id = ingest_file_sync(path)
    with connection() as conn:
        row = conn.execute("SELECT status, error FROM documents WHERE id=%s", (doc_id,)).fetchone()
    assert row["status"] == "failed"
    assert row["error"]
    with connection() as conn:
        conn.execute("DELETE FROM documents WHERE id = %s", (doc_id,))


def test_reindex_clears_previous_chunks(indexed_doc):
    with connection() as conn:
        before = conn.execute("SELECT count(*) AS n FROM chunks WHERE document_id=%s", (indexed_doc,)).fetchone()["n"]
    process(indexed_doc)
    with connection() as conn:
        after = conn.execute("SELECT count(*) AS n FROM chunks WHERE document_id=%s", (indexed_doc,)).fetchone()["n"]
    assert after == before >= 1

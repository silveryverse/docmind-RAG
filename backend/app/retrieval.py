"""Hybrid retrieval: pgvector cosine + Postgres full-text, fused with RRF,
then re-scored with a cross-encoder."""

from dataclasses import dataclass, field

from pgvector import Vector

from .config import get_settings
from .db import connection
from .embeddings import embed_query, rerank

RRF_K = 60


@dataclass
class Passage:
    chunk_id: int
    document_id: str
    filename: str
    title: str | None
    page_no: int
    text: str
    boxes: list = field(default_factory=list)
    similarity: float = 0.0
    rerank_score: float | None = None
    fused: float = 0.0


def _doc_filter(document_ids: list[str] | None) -> tuple[str, list]:
    if document_ids:
        return "AND c.document_id = ANY(%s::uuid[])", [document_ids]
    return "", []


def search(question: str, document_ids: list[str] | None = None, top_k: int | None = None) -> list[Passage]:
    settings = get_settings()
    top_k = top_k or settings.top_k
    n = settings.candidates
    qvec = Vector(embed_query(question).tolist())
    where, params = _doc_filter(document_ids)

    cols = """c.id, c.document_id, d.filename, d.title, c.page_no, c.text, c.boxes,
              1 - (c.embedding <=> %s) AS similarity"""
    dense_sql = f"""
        SELECT {cols}
        FROM chunks c JOIN documents d ON d.id = c.document_id
        WHERE d.status = 'ready' {where}
        ORDER BY c.embedding <=> %s LIMIT %s
    """
    # Natural-language questions rarely match with AND semantics, so OR the
    # stemmed terms and let ts_rank reward chunks that cover more of them.
    sparse_sql = f"""
        WITH q AS (
            SELECT to_tsquery('english',
                   replace(plainto_tsquery('english', %s)::text, ' & ', ' | ')) AS q
        )
        SELECT {cols}
        FROM chunks c JOIN documents d ON d.id = c.document_id, q
        WHERE d.status = 'ready' AND c.tsv @@ q.q {where}
        ORDER BY ts_rank_cd(c.tsv, q.q, 32) DESC LIMIT %s
    """
    with connection() as conn:
        dense = conn.execute(dense_sql, [qvec, *params, qvec, n]).fetchall()
        sparse = conn.execute(sparse_sql, [question, qvec, *params, n]).fetchall()

    pool: dict[int, Passage] = {}
    for ranked in (dense, sparse):
        for rank, r in enumerate(ranked):
            p = pool.get(r["id"])
            if p is None:
                p = pool[r["id"]] = Passage(
                    chunk_id=r["id"],
                    document_id=str(r["document_id"]),
                    filename=r["filename"],
                    title=r["title"],
                    page_no=r["page_no"],
                    text=r["text"],
                    boxes=r["boxes"],
                    similarity=float(r["similarity"]),
                )
            p.fused += 1.0 / (RRF_K + rank + 1)

    candidates = sorted(pool.values(), key=lambda p: p.fused, reverse=True)[: n]
    if settings.rerank_enabled and candidates:
        scores = rerank(question, [p.text for p in candidates])
        for p, s in zip(candidates, scores):
            p.rerank_score = s
        candidates.sort(key=lambda p: p.rerank_score, reverse=True)
    return candidates[:top_k]


def has_evidence(passages: list[Passage]) -> bool:
    """Cheap pre-LLM gate. The LLM performs the stricter, semantic check."""
    if not passages:
        return False
    s = get_settings()
    best = passages[0]
    if best.rerank_score is not None:
        return best.rerank_score >= s.min_rerank_score
    return best.similarity >= s.min_vector_similarity

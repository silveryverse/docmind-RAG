import threading

import numpy as np

from .config import get_settings

_lock = threading.Lock()
_embedder = None
_reranker = None

# BGE v1.5 retrieval works best with this instruction on the query side only.
_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


def _get_embedder():
    global _embedder
    with _lock:
        if _embedder is None:
            from fastembed import TextEmbedding

            s = get_settings()
            _embedder = TextEmbedding(s.embed_model, cache_dir=str(s.cache_dir))
    return _embedder


def _get_reranker():
    global _reranker
    with _lock:
        if _reranker is None:
            from fastembed.rerank.cross_encoder import TextCrossEncoder

            s = get_settings()
            _reranker = TextCrossEncoder(s.rerank_model, cache_dir=str(s.cache_dir))
    return _reranker


def embed_passages(texts: list[str]) -> list[np.ndarray]:
    return list(_get_embedder().embed(texts, batch_size=32))


def embed_query(text: str) -> np.ndarray:
    prefix = _QUERY_PREFIX if "bge" in get_settings().embed_model.lower() else ""
    return next(iter(_get_embedder().embed([prefix + text])))


def rerank(query: str, passages: list[str]) -> list[float]:
    if not passages:
        return []
    return [float(s) for s in _get_reranker().rerank(query, passages, batch_size=32)]


def warmup() -> None:
    embed_query("warmup")
    if get_settings().rerank_enabled:
        rerank("warmup", ["warmup"])

# app/retrieval/multimodal_retrieval.py — northstar-bank
# Full retrieval pipeline: vector ANN + FTS → RRF fusion → Cohere rerank.

import cohere
from app.utils.db import get_connection
from app.utils.openai_client import get_openai_client
from config import (
    COHERE_API_KEY,
    COHERE_RERANK_MODEL,
    OPENAI_EMBEDDING_MODEL,
    OPENAI_EMBEDDING_DIMS,
    RERANK_TOP_N,
    RELEVANCE_THRESHOLD,
    RETRIEVAL_TOP_K,
    RRF_K,
)

_cohere_client: cohere.Client | None = None


def _get_cohere_client() -> cohere.Client:
    global _cohere_client
    if _cohere_client is None:
        _cohere_client = cohere.Client(api_key=COHERE_API_KEY)
    return _cohere_client


def _embed_query(text: str) -> list[float]:
    response = get_openai_client().embeddings.create(
        model=OPENAI_EMBEDDING_MODEL,
        input=text,
        dimensions=OPENAI_EMBEDDING_DIMS,
    )
    return response.data[0].embedding


def _rerank_chunks(query: str, chunks: list[dict], top_n: int) -> list[dict]:
    if not chunks:
        return []
    response = _get_cohere_client().rerank(
        model=COHERE_RERANK_MODEL,
        query=query,
        documents=[chunk["content"] for chunk in chunks],
        top_n=top_n,
    )
    reranked = []
    for hit in response.results:
        chunk = chunks[hit.index].copy()
        chunk["score"] = hit.relevance_score
        reranked.append(chunk)
    return reranked


def retrieve(query: str) -> list[dict]:
    """Return reranked chunks for a query."""
    vec = _vector_search(query)
    fts = _fts_search(query)
    fused = _rrf_fusion(vec, fts)
    return _rerank(query, fused)


def _vector_search(query: str, top_k: int = RETRIEVAL_TOP_K) -> list[dict]:
    embedding_str = "[" + ",".join(str(val) for val in _embed_query(query)) + "]"
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT chunk_id, content, content_type, source_file, section,
                       page_number, element_type,
                       1 - (embedding <=> %s::vector) AS score
                FROM   rag.chunks
                WHERE  embedding IS NOT NULL
                ORDER  BY embedding <=> %s::vector
                LIMIT  %s
            """,
                (embedding_str, embedding_str, top_k),
            )
            cols = [col_desc[0] for col_desc in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def _fts_search(query: str, top_k: int = RETRIEVAL_TOP_K) -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT chunk_id, content, content_type, source_file, section,
                       page_number, element_type,
                       ts_rank(content_tsvector, plainto_tsquery('english', %s)) AS score
                FROM   rag.chunks
                WHERE  content_tsvector @@ plainto_tsquery('english', %s)
                ORDER  BY score DESC
                LIMIT  %s
            """,
                (query, query, top_k),
            )
            cols = [col_desc[0] for col_desc in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def _rrf_fusion(vector_results: list[dict], fts_results: list[dict]) -> list[dict]:
    scores: dict[str, float] = {}
    chunks_by_id: dict[str, dict] = {}
    for rank, chunk in enumerate(vector_results, start=1):
        cid = str(chunk["chunk_id"])
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (RRF_K + rank)
        chunks_by_id[cid] = chunk
    for rank, chunk in enumerate(fts_results, start=1):
        cid = str(chunk["chunk_id"])
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (RRF_K + rank)
        chunks_by_id.setdefault(cid, chunk)
    result = []
    for cid in sorted(scores, key=lambda x: scores[x], reverse=True):
        chunk = chunks_by_id[cid].copy()
        chunk["score"] = scores[cid]
        result.append(chunk)
    return result


def _rerank(query: str, chunks: list[dict]) -> list[dict]:
    if not chunks:
        return []
    reranked = _rerank_chunks(query, chunks, top_n=RERANK_TOP_N)
    return [chunk for chunk in reranked if chunk["score"] >= RELEVANCE_THRESHOLD]

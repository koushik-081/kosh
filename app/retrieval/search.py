from pgvector import Vector
from pydantic import BaseModel

from app.llm import embed
from app.models import Locator
from app.store import connect

RRF_K = 60  # standard constant for Reciprocal Rank Fusion


class SearchResult(BaseModel):
    id: int
    collection: str
    text: str
    locator: Locator
    score: float


def search(query: str, collection: str | None = None, k: int = 5, pool: int = 20) -> list[SearchResult]:
    """Hybrid search: meaning (vectors) + exact words (keywords), merged with RRF.

    collection=None searches every collection. pool is how many candidates
    each method returns before merging.
    """
    query_vector = Vector(embed([query])[0])
    with connect() as conn:
        by_meaning = conn.execute(
            """
            SELECT id FROM chunks
            WHERE %(collection)s::text IS NULL OR collection = %(collection)s
            ORDER BY embedding <=> %(vector)s
            LIMIT %(pool)s
            """,
            {"collection": collection, "vector": query_vector, "pool": pool},
        ).fetchall()
        by_keyword = conn.execute(
            """
            SELECT id FROM chunks, websearch_to_tsquery('english', %(query)s) q
            WHERE tsv @@ q AND (%(collection)s::text IS NULL OR collection = %(collection)s)
            ORDER BY ts_rank_cd(tsv, q) DESC
            LIMIT %(pool)s
            """,
            {"collection": collection, "query": query, "pool": pool},
        ).fetchall()

        scores: dict[int, float] = {}
        for ranking in (by_meaning, by_keyword):
            for rank, (chunk_id,) in enumerate(ranking, start=1):
                scores[chunk_id] = scores.get(chunk_id, 0.0) + 1 / (RRF_K + rank)
        top_ids = sorted(scores, key=scores.get, reverse=True)[:k]
        if not top_ids:
            return []

        rows = conn.execute(
            "SELECT id, collection, text, locator FROM chunks WHERE id = ANY(%s)", (top_ids,)
        ).fetchall()

    by_id = {r[0]: r for r in rows}
    return [
        SearchResult(
            id=cid,
            collection=by_id[cid][1],
            text=by_id[cid][2],
            locator=Locator(**by_id[cid][3]),
            score=round(scores[cid], 4),
        )
        for cid in top_ids
    ]

from functools import lru_cache
from pathlib import Path

from fastembed.rerank.cross_encoder import TextCrossEncoder

from app.config import get_settings
from app.retrieval.search import SearchResult, search


@lru_cache
def _reranker() -> TextCrossEncoder:
    cache = Path.home() / ".cache" / "fastembed"  # default is /tmp, which is wiped on reboot
    return TextCrossEncoder(model_name=get_settings().rerank_model, cache_dir=str(cache))


def rerank(query: str, results: list[SearchResult], k: int = 5) -> list[SearchResult]:
    """Re-order results by reading the question and each chunk together; keep the best k."""
    if not results:
        return []
    scores = list(_reranker().rerank(query, [r.text for r in results]))
    ranked = sorted(zip(results, scores), key=lambda pair: pair[1], reverse=True)[:k]
    return [r.model_copy(update={"score": round(float(s), 3)}) for r, s in ranked]


def retrieve(query: str, collection: str | None = None, k: int = 5, candidates: int = 20) -> list[SearchResult]:
    """Hybrid search for a wide pool of candidates, then rerank down to the best k."""
    return rerank(query, search(query, collection, k=candidates), k)

import re
from pathlib import Path

from app.config import get_settings
from app.llm import chat
from app.retrieval.search import SearchResult

PROMPTS = Path(__file__).resolve().parents[2] / "prompts"


def grade(question: str, sources: list[SearchResult]) -> list[SearchResult]:
    """Keep the sources that help answer the question.

    The reranker score decides the clear cases for free; only the unclear middle
    goes to the fast LLM, because every LLM call costs ~15 s on a CPU.
    """
    s = get_settings()
    sure = [r for r in sources if r.score >= s.relevant_score]
    unsure = [r for r in sources if s.irrelevant_score < r.score < s.relevant_score]
    return sure + _llm_grade(question, unsure)


def _llm_grade(question: str, sources: list[SearchResult]) -> list[SearchResult]:
    """Ask the fast model which sources actually help answer the question; return only those."""
    if not sources:
        return []
    numbered = "\n\n".join(f"[{i}] {s.text[:800]}" for i, s in enumerate(sources, start=1))
    reply = chat(
        [
            {"role": "system", "content": (PROMPTS / "grade.md").read_text()},
            {"role": "user", "content": f"Question: {question}\n\nSources:\n\n{numbered}"},
        ],
        fast=True,
    )
    keep = {int(n) for n in re.findall(r"\d+", reply)}
    return [s for i, s in enumerate(sources, start=1) if i in keep]


def rewrite(question: str) -> str:
    """Ask the fast model for a better search query when the first search found nothing useful."""
    reply = chat(
        [
            {"role": "system", "content": (PROMPTS / "rewrite.md").read_text()},
            {"role": "user", "content": f"Question: {question}\nQuery:"},
        ],
        fast=True,
    )
    return reply.strip().removeprefix("Query:").strip().strip('"').splitlines()[0]
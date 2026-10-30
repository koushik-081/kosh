import re

from pathlib import Path
from app.generation.answer import CITATION, REFUSAL
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

CODE_BLOCK = re.compile(r"```.*?```", re.DOTALL)
def verify(answer_text: str, sources: list[SearchResult]) -> list[str]:
    """Return the statements in the answer that the sources do not support.

    Code blocks are checked line by line against the source text, no LLM needed.
    Each sentence gets its own YES/NO question to the answer model: the 3b flagged
    6 of 8 true sentences, the 7b none (but it misses about half of the made-up ones).
    The sources go first and never change, so Ollama reuses its prompt cache.
    """
    if not sources or answer_text.strip().startswith(REFUSAL):
        return []
    unsupported = [code for code in CODE_BLOCK.findall(answer_text) if not _code_in_sources(code, sources)]
    numbered = "\n\n".join(f"[{i}] {s.text}" for i, s in enumerate(sources, start=1))
    system = (PROMPTS / "verify.md").read_text()
    for sentence in _sentences(answer_text):
        reply = chat(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": f"Sources:\n\n{numbered}\n\nSentence: {sentence}"},
            ]
        )
        if reply.strip().upper().startswith("NO"):
            unsupported.append(sentence)
    return unsupported


def _sentences(text: str) -> list[str]:
    """The prose of an answer split into sentences, without code blocks or [n] markers."""
    prose = CITATION.sub("", CODE_BLOCK.sub("\n", text))
    sentences = (s.strip(" -*\t") for s in re.split(r"(?<=[.!?])\s+|\n+", prose))
    return [s for s in sentences if len(s) > 20]


def _code_in_sources(code: str, sources: list[SearchResult], share: float = 0.8) -> bool:
    """True if most lines of the code block appear word for word in the sources."""
    flat = lambda t: " ".join(t.split())  # ignore indentation and line breaks
    haystack = flat(" ".join(s.text for s in sources))
    lines = [flat(line) for line in code.strip("`").splitlines()[1:] if flat(line)]
    return bool(lines) and sum(line in haystack for line in lines) / len(lines) >= share
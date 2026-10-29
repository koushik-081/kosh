import re
from pathlib import Path

from pydantic import BaseModel

from app.llm import chat
from app.retrieval.search import SearchResult

PROMPT_FILE = Path(__file__).resolve().parents[2] / "prompts" / "answer.md"
CITATION = re.compile(r"\[(\d+)\]")
REFUSAL = "I don't know based on the available sources."  # same sentence as in prompts/answer.md


class Citation(BaseModel):
    number: int
    link: str
    section: str | None


class Answer(BaseModel):
    text: str
    citations: list[Citation]  # sources the answer actually cited, in order
    invalid_citations: list[int]  # numbers the LLM made up (no such source)


def build_messages(question: str, sources: list[SearchResult]) -> list[dict]:
    """System prompt with the rules, user message with numbered sources + the question."""
    numbered = "\n\n".join(
        f"[{i}] ({s.locator.section or s.locator.uri})\n{s.text}" for i, s in enumerate(sources, start=1)
    )
    return [
        {"role": "system", "content": PROMPT_FILE.read_text()},
        {"role": "user", "content": f"Sources:\n\n{numbered}\n\nQuestion: {question}"},
    ]


def check_citations(text: str, sources: list[SearchResult]) -> Answer:
    """Find the [n] markers in the answer and match them to real sources."""
    cited = list(dict.fromkeys(int(n) for n in CITATION.findall(text)))  # unique, in order
    valid = [n for n in cited if 1 <= n <= len(sources)]
    return Answer(
        text=text,
        citations=[
            Citation(number=n, link=sources[n - 1].locator.deep_link(), section=sources[n - 1].locator.section)
            for n in valid
        ],
        invalid_citations=[n for n in cited if n not in valid],
    )


def answer(question: str, sources: list[SearchResult]) -> Answer:
    return check_citations(chat(build_messages(question, sources)), sources)

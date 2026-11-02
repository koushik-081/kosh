import operator
from collections.abc import Iterator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agent.steps import grade, rewrite
from app.config import get_settings
from app.retrieval.rerank import retrieve
from app.retrieval.search import SearchResult


class AgentState(TypedDict, total=False):
    question: str  # what the user asked (never changes)
    collection: str | None
    k: int
    query: str  # what we search for (changes when rewritten)
    attempts: int  # how many rewrites so far
    tried: Annotated[list[str], operator.add]  # every query searched so far
    graded: Annotated[list[int], operator.add]  # ids of chunks already graded, never graded twice
    sources: list[SearchResult]  # latest search results
    relevant: list[SearchResult]  # everything that passed grading so far, best first
    steps: Annotated[list[str], operator.add]  # human-readable trace; each node appends to it


def search_node(state: AgentState) -> dict:
    sources = retrieve(state["query"], state["collection"], state["k"])
    return {"sources": sources, "tried": [state["query"]],
            "steps": [f"🔎 Searched \"{state['query']}\": {len(sources)} chunks"]}


def grade_node(state: AgentState) -> dict:
    new = [r for r in state["sources"] if r.id not in state["graded"]]
    kept = grade(state["question"], new)
    # keep what earlier attempts found too, without duplicates, best reranker score first
    merged = {r.id: r for r in state.get("relevant", []) + kept}
    relevant = sorted(merged.values(), key=lambda r: r.score, reverse=True)[: state["k"]]
    sure = sum(r.score >= get_settings().relevant_score for r in kept)
    return {
        "relevant": relevant,
        "graded": [r.id for r in new],
        "steps": [f"⚖️ Graded {len(new)} new chunks: kept {len(kept)} ({sure} clearly relevant)"],
    }


def rewrite_node(state: AgentState) -> dict:
    query = rewrite(state["question"], state["tried"])
    return {"query": query, "attempts": state["attempts"] + 1, "steps": [f"✏️ Rewrote the query to \"{query}\""]}


def refuse_node(state: AgentState) -> dict:
    return {"steps": [f"🚫 Nothing relevant found after {state['attempts']} rewrites, so Kosh will not guess"]}


def after_grading(state: AgentState) -> str:
    """The decision point: answer, try again with a better query, or give up honestly.

    Answer as soon as anything passed grading (the reranker was sure, or the LLM said YES).
    Otherwise try a better query; when out of retries, refuse instead of guessing.
    """
    if state["relevant"]:
        return "answer"
    if state["attempts"] < get_settings().max_retries:
        return "rewrite"
    return "refuse"


def _build():
    g = StateGraph(AgentState)
    g.add_node("search", search_node)
    g.add_node("grade", grade_node)
    g.add_node("rewrite", rewrite_node)
    g.add_node("refuse", refuse_node)
    g.add_edge(START, "search")
    g.add_edge("search", "grade")
    g.add_conditional_edges("grade", after_grading, {"answer": END, "rewrite": "rewrite", "refuse": "refuse"})
    g.add_edge("rewrite", "search")
    g.add_edge("refuse", END)
    return g.compile()


GRAPH = _build()


def research(question: str, collection: str | None = None, k: int = 4) -> Iterator[AgentState]:
    """Run search -> grade -> (rewrite -> search ...) and yield the state after every step.

    The last state yielded holds `relevant`: the sources to answer from (empty = refuse).
    """
    start: AgentState = {"question": question, "collection": collection, "k": k,
                         "query": question, "attempts": 0, "tried": [], "graded": [], "steps": []}
    yield from GRAPH.stream(start, stream_mode="values")
import json
from collections.abc import Iterator
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.generation.answer import Answer, build_messages, check_citations
from app.llm import chat, chat_stream
from app.retrieval.rerank import retrieve
from app.retrieval.search import SearchResult
from app.store import connect

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
app = FastAPI(title="Kosh", description="Self-correcting knowledge engine")
app.mount("/files", StaticFiles(directory=DATA_DIR), name="files")  # lets PDF citations open in the browser


class QueryRequest(BaseModel):
    question: str
    collection: str | None = None  # None = search every collection
    k: int = 4
    stream: bool = False


class QueryResponse(BaseModel):
    answer: Answer
    sources: list[SearchResult]


@app.get("/health")
def health() -> dict:
    with connect() as conn:
        chunks = conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
    return {"status": "ok", "chunks": chunks}


@app.post("/search")
def search_endpoint(req: QueryRequest) -> list[SearchResult]:
    return retrieve(req.question, req.collection, req.k)

@app.get("/collections")
def collections() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT collection, count(DISTINCT document_id), count(*)
            FROM chunks GROUP BY collection ORDER BY collection
            """
        ).fetchall()
    return [{"name": name, "documents": docs, "chunks": chunks} for name, docs, chunks in rows]

@app.post("/query", response_model=None)
def query(req: QueryRequest) -> QueryResponse | StreamingResponse:
    sources = retrieve(req.question, req.collection, req.k)
    messages = build_messages(req.question, sources)
    if not req.stream:
        return QueryResponse(answer=check_citations(chat(messages), sources), sources=sources)
    return StreamingResponse(_stream_answer(messages, sources), media_type="text/event-stream")


def _stream_answer(messages: list[dict], sources: list[SearchResult]) -> Iterator[str]:
    """Server-Sent Events: sources first, then the answer token by token, then the checked citations."""
    yield _event("sources", [s.model_dump() for s in sources])
    text = ""
    for token in chat_stream(messages):
        text += token
        yield _event("token", token)
    yield _event("done", check_citations(text, sources).model_dump())


def _event(name: str, data) -> str:
    return f"event: {name}\ndata: {json.dumps(data)}\n\n"

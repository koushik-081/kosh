import json
from collections.abc import Iterator
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.agent.graph import AgentState, research
from app.generation.answer import REFUSAL, Answer, build_messages, check_citations
from app.llm import chat, chat_stream
from app.observability.tracing import setup_tracing
from app.retrieval.rerank import retrieve
from app.retrieval.search import SearchResult
from app.store import connect, delete_document, list_documents, save_chunks
from app.agent.steps import verify
from app.guardrails.input import check_question
from app.guardrails.pii import mask
from app.ingest.auto import load_any
from app.history import add_message, delete_chat, get_messages, list_chats, new_chat

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
EVAL_DIR = DATA_DIR.parent / "eval"
app = FastAPI(title="Kosh", description="Self-correcting knowledge engine")
setup_tracing()
app.mount("/files", StaticFiles(directory=DATA_DIR), name="files")  # lets PDF citations open in the browser


class QueryRequest(BaseModel):
    question: str
    collection: str | None = None  # None = search every collection
    k: int = 4
    stream: bool = False


class QueryResponse(BaseModel):
    answer: Answer
    sources: list[SearchResult]
    steps: list[str]  # what the agent did, in order
    unsupported: list[str]  # parts of the answer the self-check could not find in the sources

class IngestRequest(BaseModel):
    source: str  # web page, GitHub repo or YouTube URL
    collection: str
    path: str = ""  # GitHub only: just this folder

class NewChat(BaseModel):
    title: str


class Message(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    details: dict = {}  # steps, sources, citations, unsupported

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

@app.get("/documents")
def documents(collection: str) -> list[dict]:
    return list_documents(collection)


@app.delete("/documents")
def remove_document(collection: str, document_id: str) -> dict:
    return {"removed": delete_document(collection, document_id)}


@app.post("/ingest")
def ingest(req: IngestRequest) -> dict:
    """Read, chunk, embed and store a URL. Slow on CPU: a big GitHub repo takes minutes."""
    try:
        chunks = load_any(req.source, req.collection, req.path)
    except Exception as e:  # bad URL, no transcript, private repo...
        raise HTTPException(400, f"Could not read {req.source}: {e}")
    return {"found": len(chunks), "added": save_chunks(chunks)}


@app.post("/ingest/pdf")
async def ingest_pdf(collection: str, name: str, request: Request) -> dict:
    """The PDF's bytes are the request body; it is saved under data/uploads so citations can open it."""
    if not name.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files can be uploaded")
    target = Path("data/uploads") / Path(name).name  # relative, like CLI paths, so /files links work
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(await request.body())
    try:
        chunks = await run_in_threadpool(load_any, str(target), collection)
    except Exception as e:
        raise HTTPException(400, f"Could not read {name}: {e}")
    return {"found": len(chunks), "added": await run_in_threadpool(save_chunks, chunks)}


@app.get("/quality")
def quality() -> dict:
    """The latest eval report (eval/report.md) and every question's result from eval/results/."""
    report = EVAL_DIR / "report.md"
    questions = [
        json.loads(line) | {"mode": f.stem}
        for f in sorted((EVAL_DIR / "results").glob("*.jsonl"))
        for line in f.open()
    ]
    return {"report": report.read_text() if report.exists() else None, "questions": questions}

@app.get("/chats")
def chats() -> list[dict]:
    return list_chats()


@app.post("/chats")
def create_chat(req: NewChat) -> dict:
    return {"id": new_chat(req.title)}


@app.get("/chats/{chat_id}")
def chat_messages(chat_id: int) -> list[dict]:
    return get_messages(chat_id)


@app.post("/chats/{chat_id}/messages")
def save_message(chat_id: int, msg: Message) -> dict:
    add_message(chat_id, msg.role, msg.content, msg.details)
    return {"ok": True}


@app.delete("/chats/{chat_id}")
def remove_chat(chat_id: int) -> dict:
    delete_chat(chat_id)
    return {"ok": True}

@app.post("/query", response_model=None)
def query(req: QueryRequest) -> QueryResponse | StreamingResponse:
    if req.stream:
        return StreamingResponse(_stream_answer(req), media_type="text/event-stream")
    if blocked := check_question(req.question):
        text = _blocked_message(blocked)
        return QueryResponse(answer=check_citations(text, []), sources=[], steps=[f"🛡️ Blocked: {blocked}"], unsupported=[])
    state: AgentState = {}
    for state in research(req.question, req.collection, req.k):
        pass  # run the agent to the end; we only need the final state
    sources = state["relevant"]
    text = chat(build_messages(req.question, sources)) if sources else REFUSAL
    unsupported = verify(text, sources)
    return QueryResponse(
        answer=check_citations(text, sources),
        sources=sources,
        steps=state["steps"] + [_check_step(unsupported)],
        unsupported=unsupported,
    )


def _stream_answer(req: QueryRequest) -> Iterator[str]:
    """Server-Sent Events: each agent step live, then the sources, the answer token by token, the citations."""
    state: AgentState = {}
    if blocked := check_question(req.question):
        yield _event("step", f"🛡️ Blocked: {blocked}")
        yield _event("sources", [])
        yield _event("token", _blocked_message(blocked))
        yield _event("done", check_citations(_blocked_message(blocked), []).model_dump())
        yield _event("check", [])
        return
    shown = 0
    for state in research(req.question, req.collection, req.k):
        for step in state["steps"][shown:]:
            yield _event("step", step)
        shown = len(state["steps"])

    sources = state["relevant"]
    yield _event("sources", [s.model_dump() | {"text": mask(s.text)} for s in sources])
    if not sources:
        yield _event("token", REFUSAL)
        yield _event("done", check_citations(REFUSAL, []).model_dump())
        return
    text = ""
    for token in chat_stream(build_messages(req.question, sources)):
        text += token
        yield _event("token", token)
    yield _event("done", check_citations(text, sources).model_dump())
    unsupported = verify(text, sources)
    yield _event("step", _check_step(unsupported))
    yield _event("check", unsupported)

def _blocked_message(reason: str) -> str:
    return f"Kosh did not answer this, because {reason}. Please ask a question about your sources."

def _check_step(unsupported: list[str]) -> str:
    if not unsupported:
        return "✅ Self-check: everything in the answer was found in the sources"
    return f"⚠️ Self-check: {len(unsupported)} part(s) of the answer were not found in the sources"


def _event(name: str, data) -> str:
    return f"event: {name}\ndata: {json.dumps(data)}\n\n"

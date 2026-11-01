"""Answer every test question in one mode and record how it went, one JSON line per question.

naive = search + rerank + answer (Day 3). agent = the LangGraph loop (Day 5).
Safe to stop and restart: questions already in the results file are skipped.

Run:  uv run python -m eval.run --mode naive
      uv run python -m eval.run --mode agent
"""
import argparse
import json
import time
from pathlib import Path

from app.agent.graph import research
from app.agent.steps import CODE_BLOCK, _sentences, verify
from app.generation.answer import REFUSAL, build_messages, check_citations
from app.llm import chat
from app.retrieval.rerank import retrieve

EVAL_DIR = Path(__file__).resolve().parent
JUDGE = EVAL_DIR.parent / "prompts" / "judge.md"


def find_sources(question: str, collection: str, mode: str, k: int) -> list:
    if mode == "naive":
        return retrieve(question, collection, k)
    state = {}
    for state in research(question, collection, k):
        pass
    return state["relevant"]


def is_correct(question: str, reference: str, text: str) -> bool:
    """Ask the answer model whether the answer agrees with the reference answer."""
    reply = chat([
        {"role": "system", "content": JUDGE.read_text()},
        {"role": "user", "content": f"Question: {question}\n\nReference: {reference}\n\nAnswer: {text}"},
    ])
    return reply.strip().upper().startswith("YES")


def run_one(item: dict, mode: str, k: int) -> dict:
    start = time.time()
    sources = find_sources(item["question"], item["collection"], mode, k)
    text = chat(build_messages(item["question"], sources)) if sources else REFUSAL
    refused = text.strip().startswith(REFUSAL)
    result = check_citations(text, sources)
    unsupported = verify(text, sources)
    return {
        "question": item["question"],
        "should_refuse": item["should_refuse"],
        "refused": refused,
        "gold_retrieved": item["chunk_id"] in [s.id for s in sources],
        "correct": None if item["should_refuse"] or refused else is_correct(item["question"], item["answer"], text),
        "citations": len(result.citations),
        "invalid_citations": len(result.invalid_citations),
        "statements": 0 if refused else len(_sentences(text)) + len(CODE_BLOCK.findall(text)),
        "unsupported": len(unsupported),
        "seconds": round(time.time() - start, 1),  # includes the self-check, not the judge
        "answer": text,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["naive", "agent"], required=True)
    parser.add_argument("-i", "--testset", default=str(EVAL_DIR / "testset.jsonl"))
    parser.add_argument("-k", type=int, default=4)
    args = parser.parse_args()

    out = EVAL_DIR / "results" / f"{args.mode}.jsonl"
    out.parent.mkdir(exist_ok=True)
    done = {json.loads(line)["question"] for line in out.open()} if out.exists() else set()
    items = [json.loads(line) for line in open(args.testset)]

    for n, item in enumerate(items, start=1):
        if item["question"] in done:
            continue
        row = run_one(item, args.mode, args.k)
        with out.open("a") as f:
            f.write(json.dumps(row) + "\n")
        verdict = "refused" if row["refused"] else f"correct={row['correct']}"
        print(f"{n}/{len(items)}  {row['seconds']}s  {verdict}  {item['question'][:70]}", flush=True)


if __name__ == "__main__":
    main()
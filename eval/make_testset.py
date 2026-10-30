"""Build the evaluation set: questions written from random chunks, plus questions Kosh should refuse.

Run:  uv run python -m eval.make_testset -c fastapi -n 15
"""
import argparse
import json
import random
import re
from pathlib import Path

from app.llm import chat
from app.store import connect

EVAL_DIR = Path(__file__).resolve().parent
PROMPT = EVAL_DIR.parent / "prompts" / "testset.md"

# Off-topic for every collection: the right answer is a refusal
NEGATIVES = [
    "How do I define a model with Django's ORM?",
    "What is the default port of a Redis server?",
    "How do I configure horizontal pod autoscaling in Kubernetes?",
    "Who won the 2022 FIFA World Cup?",
    "How do I write a for loop in Rust?",
    "What is the capital of Australia?",
]
VAGUE = re.compile(r"\b(the|this) (passage|text|snippet|document|section|code above)\b", re.IGNORECASE)


def write_question(text: str) -> tuple[str, str] | None:
    """Ask the answer model for one question + answer about a chunk; None if it skips or replies badly."""
    reply = chat([{"role": "system", "content": PROMPT.read_text()}, {"role": "user", "content": text[:3000]}])
    match = re.search(r"Question:\s*(.+?)\s*Answer:\s*(.+)", reply, re.DOTALL)
    if not match or VAGUE.search(match[1]):
        return None
    return match[1].strip(), match[2].strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--collection", required=True)
    parser.add_argument("-n", type=int, default=15, help="how many generated questions")
    parser.add_argument("--seed", type=int, default=7, help="same seed = same chunks picked")
    parser.add_argument("-o", "--out", default=str(EVAL_DIR / "testset.jsonl"))
    args = parser.parse_args()

    with connect() as conn:
        rows = conn.execute(
            "SELECT id, text, locator->>'section' FROM chunks WHERE collection = %s AND length(text) > 400 ORDER BY id",
            (args.collection,),
        ).fetchall()
    random.Random(args.seed).shuffle(rows)

    items = []
    for chunk_id, text, section in rows:
        if len(items) == args.n:
            break
        qa = write_question(text)
        if qa is None:
            print(f"  skipped chunk {chunk_id}")
            continue
        items.append({"question": qa[0], "answer": qa[1], "collection": args.collection,
                      "chunk_id": chunk_id, "section": section, "should_refuse": False})
        print(f"{len(items)}/{args.n}  {qa[0]}")
    items += [{"question": q, "answer": None, "collection": args.collection,
               "chunk_id": None, "section": None, "should_refuse": True} for q in NEGATIVES]

    with open(args.out, "w") as f:
        f.writelines(json.dumps(item) + "\n" for item in items)
    print(f"\n{len(items)} questions ({len(NEGATIVES)} should be refused) written to {args.out}")


if __name__ == "__main__":
    main()
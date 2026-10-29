import argparse

from app.ingest.github import load_github
from app.generation.answer import answer
from app.ingest.pdf import load_pdf
from app.ingest.web import load_web
from app.ingest.youtube import load_youtube
from app.retrieval.rerank import retrieve
from app.retrieval.search import search
from app.store import save_chunks


def main() -> None:
    parser = argparse.ArgumentParser(prog="kosh")
    commands = parser.add_subparsers(dest="command", required=True)

    ingest = commands.add_parser("ingest", help="add a PDF file or a web page to a collection")
    ingest.add_argument("source", help="a .pdf file, a GitHub repo URL, a YouTube video URL, or a web page URL")
    ingest.add_argument("-c", "--collection", required=True)
    ingest.add_argument("--path", default="", help="GitHub only: ingest just this folder of the repo")

    find = commands.add_parser("search", help="find the chunks that best match a question")
    find.add_argument("query")
    find.add_argument("-c", "--collection", help="search only this collection (default: all)")
    find.add_argument("-k", type=int, default=5, help="how many results")
    find.add_argument("--no-rerank", action="store_true", help="hybrid search only, skip the reranker")
	
    ask = commands.add_parser("ask", help="answer a question with citations")
    ask.add_argument("question")
    ask.add_argument("-c", "--collection", help="ask only this collection (default: all)")
    ask.add_argument("-k", type=int, default=4, help="how many chunks to give the LLM")

    args = parser.parse_args()
    if args.command == "ingest":
        if "youtube.com/" in args.source or "youtu.be/" in args.source:
            chunks = load_youtube(args.source, args.collection)
        elif args.source.startswith("https://github.com/"):
            chunks = load_github(args.source, args.collection, args.path)
        elif args.source.startswith(("http://", "https://")):
            chunks = load_web(args.source, args.collection)
        else:
            chunks = load_pdf(args.source, args.collection)
        print(f"{len(chunks)} chunks found, embedding...")
        added = save_chunks(chunks, on_progress=lambda done, total: print(f"  {done}/{total}", end="\r", flush=True))
        print(f"\n{added} new ones saved")
    elif args.command == "ask":
        result = answer(args.question, retrieve(args.question, args.collection, args.k))
        print(result.text)
        print("\nSources:")
        for c in result.citations:
            print(f"  [{c.number}] {c.section or ''}  {c.link}")
        if result.invalid_citations:
            print(f"  warning: the answer cited sources that don't exist: {result.invalid_citations}")
    else:
        find_chunks = search if args.no_rerank else retrieve
        for i, r in enumerate(find_chunks(args.query, args.collection, args.k), start=1):
            print(f"\n[{i}] score {r.score}  {r.locator.section or ''}")
            print(f"    {r.locator.deep_link()}")
            print("    " + r.text[:300].replace("\n", " "))


if __name__ == "__main__":
    main()

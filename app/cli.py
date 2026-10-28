import argparse

from app.ingest.pdf import load_pdf
from app.ingest.web import load_web
from app.retrieval.search import search
from app.store import save_chunks


def main() -> None:
    parser = argparse.ArgumentParser(prog="kosh")
    commands = parser.add_subparsers(dest="command", required=True)

    ingest = commands.add_parser("ingest", help="add a PDF file or a web page to a collection")
    ingest.add_argument("source", help="path to a .pdf file, or an http(s) URL")
    ingest.add_argument("-c", "--collection", required=True)

    find = commands.add_parser("search", help="find the chunks that best match a question")
    find.add_argument("query")
    find.add_argument("-c", "--collection", help="search only this collection (default: all)")
    find.add_argument("-k", type=int, default=5, help="how many results")

    args = parser.parse_args()
    if args.command == "ingest":
        if args.source.startswith(("http://", "https://")):
            chunks = load_web(args.source, args.collection)
        else:
            chunks = load_pdf(args.source, args.collection)
        print(f"{len(chunks)} chunks found, {save_chunks(chunks)} new ones saved")
    else:
        for i, r in enumerate(search(args.query, args.collection, args.k), start=1):
            print(f"\n[{i}] score {r.score}  {r.locator.section or ''}")
            print(f"    {r.locator.deep_link()}")
            print("    " + r.text[:300].replace("\n", " "))


if __name__ == "__main__":
    main()

from pathlib import Path

import pymupdf

from app.ingest.chunking import split_text
from app.models import Chunk, Locator


def load_pdf(path: str | Path, collection: str) -> list[Chunk]:
    """Read a PDF page by page and return chunks that remember their page and section."""
    path = Path(path)
    doc = pymupdf.open(path)
    sections = _section_per_page(doc)
    title = doc.metadata.get("title") or path.stem

    chunks: list[Chunk] = []
    for page in doc:
        page_no = page.number + 1  # PyMuPDF counts from 0, people count from 1
        for text in split_text(_page_text(page)):
            chunks.append(
                Chunk(
                    collection=collection,
                    document_id=f"pdf:{path.name}",
                    chunk_index=len(chunks),
                    text=text,
                    locator=Locator(
                        source_type="pdf",
                        uri=str(path),
                        page=page_no,
                        section=sections.get(page_no),
                    ),
                    metadata={"title": title, "page_count": doc.page_count},
                )
            )
    doc.close()
    return chunks


def _page_text(page: pymupdf.Page) -> str:
    """Text of one page, one paragraph per text block, separated by blank lines."""
    blocks = page.get_text("blocks", flags=pymupdf.TEXT_DEHYPHENATE)
    paragraphs = [" ".join(b[4].split()) for b in blocks if b[6] == 0]  # b[6] == 0: text, not image
    return "\n\n".join(p for p in paragraphs if p)


def _section_per_page(doc: pymupdf.Document) -> dict[int, str]:
    """Map each page to the first heading on it (or, if none, the latest heading before it)."""
    headings = {}
    for _level, title, page_no in doc.get_toc():
        headings.setdefault(page_no, title)
    result: dict[int, str] = {}
    current = None
    for page_no in range(1, doc.page_count + 1):
        current = headings.get(page_no, current)
        if current:
            result[page_no] = current
    return result

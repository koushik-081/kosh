import re

import trafilatura
from lxml import html as lxml_html

from app.ingest.chunking import split_text
from app.models import Chunk, Locator

HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


def load_web(url: str, collection: str) -> list[Chunk]:
    """Fetch a web page, keep only the main content, and chunk it section by section."""
    page_html = trafilatura.fetch_url(url)
    if not page_html:
        raise ValueError(f"Could not download {url}")
    markdown = trafilatura.extract(
        page_html, output_format="markdown", include_formatting=True, include_tables=True
    )
    if not markdown:
        raise ValueError(f"No readable text found on {url}")
    anchors = _heading_anchors(page_html)
    title = _clean(trafilatura.extract_metadata(page_html).title or url)

    chunks: list[Chunk] = []
    for section_path, anchor, text in _sections(markdown, anchors):
        for piece in split_text(text):
            chunks.append(
                Chunk(
                    collection=collection,
                    document_id=f"web:{url}",
                    chunk_index=len(chunks),
                    text=piece,
                    locator=Locator(source_type="web", uri=url, anchor=anchor, section=section_path),
                    metadata={"title": title},
                )
            )
    return chunks


def _sections(markdown: str, anchors: dict[str, str]):
    """Yield (heading path, anchor, text) for each heading's section of the page."""
    path: list[str] = []
    anchor = None
    lines: list[str] = []
    for line in markdown.splitlines():
        match = HEADING.match(line)
        if match:
            if lines:
                yield " > ".join(path) or None, anchor, "\n".join(lines)
            level, heading = len(match.group(1)), _clean(match.group(2))
            path = path[: level - 1] + [heading]
            anchor = anchors.get(heading.lower(), anchor)  # no id? keep the parent's anchor
            lines = [heading]
        else:
            lines.append(line)
    if lines:
        yield " > ".join(path) or None, anchor, "\n".join(lines)


def _heading_anchors(page_html: str) -> dict[str, str]:
    """Map heading text -> its HTML id, so citations can jump to url#id."""
    tree = lxml_html.fromstring(page_html)
    anchors = {}
    for h in tree.xpath("//h1[@id]|//h2[@id]|//h3[@id]|//h4[@id]"):
        anchors.setdefault(_clean(h.text_content()).lower(), h.get("id"))
    return anchors


def _clean(heading: str) -> str:
    """Strip markdown marks and the ¶ permalink symbol from a heading."""
    return " ".join(re.sub(r"[*`¶#]", "", heading).split())

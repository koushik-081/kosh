import re
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def split_text(text: str, max_chars: int = 1200, overlap: int = 200) -> list[str]:
    """Split text into chunks of at most ~max_chars.

    Breaks on blank lines (paragraphs) first, then on sentences, so a chunk
    rarely cuts a thought in half. Each chunk starts with the last ~overlap
    characters of the previous one, so a fact on the border is in both.
    """
    pieces: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        pieces.extend([para] if len(para) <= max_chars else _split_long(para, max_chars))

    chunks: list[str] = []
    current = ""
    for piece in pieces:
        if current and len(current) + len(piece) + 2 > max_chars:
            chunks.append(current)
            tail = _tail(current, overlap)
            current = f"{tail}\n\n{piece}" if tail and len(tail) + len(piece) + 2 <= max_chars else piece
        else:
            current = f"{current}\n\n{piece}" if current else piece
    if current:
        chunks.append(current)
    return chunks


def _split_long(paragraph: str, max_chars: int) -> list[str]:
    """Split one long paragraph on sentence ends; hard-split very long sentences on spaces."""
    parts: list[str] = []
    current = ""
    for sentence in SENTENCE_END.split(paragraph):
        while len(sentence) > max_chars:
            cut = sentence.rfind(" ", 0, max_chars)
            cut = cut if cut > 0 else max_chars
            parts.append(sentence[:cut])
            sentence = sentence[cut:].strip()
        if current and len(current) + len(sentence) + 1 > max_chars:
            parts.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}" if current else sentence
    if current:
        parts.append(current)
    return parts


def _tail(text: str, size: int) -> str:
    """Last ~size characters of text, starting at a word boundary."""
    if len(text) <= size:
        return text
    tail = text[-size:]
    space = tail.find(" ")
    return tail[space + 1 :] if space != -1 else ""
